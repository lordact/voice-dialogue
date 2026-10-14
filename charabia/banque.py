"""Banque de grains par profil : syllabes (consonne + voyelle) et vocalises.

Chaque syllabe est rendue à la hauteur de base du profil, en six formes :
plat / monte / descend, en version normale et longue (fins de phrase). Le séquenceur
les rejoue avec un `pitch_scale` (comme AudioStreamPlayer de Godot) pour dessiner la
mélodie. Rendu déterministe : même profil -> mêmes fichiers.
"""
import json, os, zlib, subprocess, tempfile, wave
import numpy as np
from noyau import SR, VOYELLES, Timbre, voyelle, consonne, timbre_depuis
import vocalises

FORMES = {  # (rapport de fin de glissé, facteur de longueur)
    'plat': (1.0, 1.0), 'monte': (1.12, 1.0), 'descend': (.89, 1.0),
    'plat_long': (.98, 1.7), 'monte_long': (1.24, 1.7), 'descend_long': (.8, 1.75)}
ASCII = {'é': 'ee'}


RMS_REF = 10 ** (-16 / 20)
DECALAGE_VOYELLE = {'a': 0, 'o': -1, 'on': -1.5, 'e': -1.5, 'ee': -1.5, 'eu': -2, 'i': -3, 'u': -3}
CIBLE_VOCALISE = {'rire': -2, 'rire_moqueur': -3, 'rire_nerveux': -6, 'soupir': -7, 'hmm_reflexion': -5,
                  'hmm_doute': -5, 'hmm_accord': -5, 'euh': -4, 'inspiration_surprise': -5, 'ooh': -2,
                  'oh_decu': -4, 'ah': -3, 'hein': -3, 'pfff': -7, 'grogne': -3, 'tss': -9,
                  'reniflement': -13, 'baillement': -5}


def _voyelle_de(nom):
    tete = nom.split('_')[0] if not nom.startswith('_') else nom[1:].split('_')[0]
    for c in ('ch', 'p', 'b', 't', 'd', 'k', 'm', 'n', 'l', 's', 'f', 'r'):
        if tete.startswith(c) and tete[len(c):] in DECALAGE_VOYELLE:
            return tete[len(c):]
    return tete


def _caler(s, cible, debut=0):
    """Met le signal à la sonie (RMS) cible, mesurée sur la partie voisée ; écrête doucement."""
    partie = s[debut:] if len(s) - debut > 200 else s
    rms = np.sqrt(np.mean(partie ** 2)) + 1e-9
    out = s * (cible / rms)
    return np.tanh(out * 1.2) / 1.2 if np.max(np.abs(out)) > .8 else out


def nom_syllabe(c, v, forme):
    return '%s%s_%s' % (c or '_', ASCII.get(v, v), forme)


def _graine(*parts):
    return zlib.crc32('|'.join(map(str, parts)).encode())


def charger_profils(chemin):
    return json.load(open(chemin, encoding='utf-8'))['profils']


class BanqueProfil:
    """Grains d'un profil, en mémoire (float, 44,1 kHz) ; exportable en OGG pour Godot."""

    def __init__(self, pid, p):
        self.pid, self.p = pid, p
        self.f0 = float(p['f0'])
        self.t = timbre_depuis(p.get('timbre', {}))
        self.syllabes = {}   # nom -> (signal, attaque en s)
        self.vocalises = {}  # type -> [signal, signal]
        self._rendre()

    def _rendre(self):
        p, t = self.p, self.t
        brut_s, brut_v = {}, {}
        for c in p['consonnes']:
            for v in p['voyelles']:
                for forme, (ratio, k) in FORMES.items():
                    rng = np.random.default_rng(_graine(self.pid, c, v, forme))
                    cons = consonne(c, self.f0, rng, t)
                    voy = voyelle(p['syllabe'] * k, self.f0, self.f0 * ratio, VOYELLES[v], rng, t)
                    brut_s[nom_syllabe(c, v, forme)] = (np.concatenate([cons, voy]), len(cons) / SR)
        for typ, fn in vocalises.TYPES.items():
            brut_v[typ] = [fn(self.f0, t, np.random.default_rng(_graine(self.pid, typ, k)), p) for k in range(2)]
        # Sonie : chaque grain est calé sur une cible (les voyelles ouvertes restent un peu plus
        # fortes que les fermées, comme dans la parole). Sans ce calage, une harmonique qui tombe
        # pile sur un formant rend certaines syllabes 20 dB plus fortes que d'autres.
        self.syllabes = {}
        for nom, (s, a) in brut_s.items():
            debut = int(a * SR)
            cible = RMS_REF * 10 ** (DECALAGE_VOYELLE.get(_voyelle_de(nom), -2) / 20)
            self.syllabes[nom] = (_caler(s, cible, debut), a)
        self.vocalises = {k: [_caler(s, RMS_REF * 10 ** (CIBLE_VOCALISE.get(k, -4) / 20)) for s in l]
                          for k, l in brut_v.items()}

    def exporter(self, dossier, sr_sortie=32000, format_='wav', qualite=3):
        """Écrit les grains + un index JSON (durée, attaque) pour le lecteur Godot.
        WAV par défaut : Godot l'importe en QOA, et jouer un grain ne coûte presque rien.
        (En OGG, chaque grain instancie un décodeur Vorbis : ~1 ms par grain, mesuré.)"""
        os.makedirs(dossier, exist_ok=True)
        index = {'profil': self.pid, 'f0': self.f0, 'sr': sr_sortie, 'format': format_, 'syllabes': {}, 'vocalises': {}}
        ecrire = (lambda c, s: ecrire_wav(c, _reechantillonner(s, sr_sortie), sr_sortie)) if format_ == 'wav' \
            else (lambda c, s: _ecrire_ogg(c, s, sr_sortie, qualite))
        for nom, (s, a) in self.syllabes.items():
            ecrire(os.path.join(dossier, nom + '.' + format_), s)
            index['syllabes'][nom] = {'duree': round(len(s) / SR, 4), 'attaque': round(a, 4)}
        for typ, l in self.vocalises.items():
            for k, s in enumerate(l):
                ecrire(os.path.join(dossier, '%s_%d.%s' % (typ, k, format_)), s)
            index['vocalises'][typ] = [round(len(s) / SR, 4) for s in l]
        json.dump(index, open(os.path.join(dossier, 'index.json'), 'w'), indent=1)
        return index


def _reechantillonner(sig, sr):
    if sr == SR:
        return sig
    from math import gcd
    from scipy.signal import resample_poly
    g = gcd(sr, SR)
    return resample_poly(sig, sr // g, SR // g)


def _ecrire_ogg(chemin, sig, sr, qualite):
    with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
        tmp = f.name
    ecrire_wav(tmp, sig)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', tmp, '-ar', str(sr), '-c:a', 'libvorbis',
                    '-q:a', str(qualite), chemin], check=True)
    os.remove(tmp)


def ecrire_wav(chemin, sig, sr=SR):
    sig = np.asarray(sig)
    canaux = 1 if sig.ndim == 1 else sig.shape[1]
    with wave.open(chemin, 'wb') as w:
        w.setnchannels(canaux); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes((np.clip(sig, -1, 1) * 32767).astype('<i2').tobytes())
