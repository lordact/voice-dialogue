"""Banque de grains par profil : syllabes (consonne + voyelle) et vocalises.

Style mélodieux : chaque syllabe est rendue à hauteur fixe (celle du profil), en trois
longueurs (court, plat, long). La mélodie n'est plus « cuite » dans les grains : le lecteur
fait glisser la hauteur pendant la lecture (pitch de début -> pitch de fin), ce qui lie
les syllabes entre elles. Attaques et relâches plus douces pour enchaîner sans trou.
Rendu déterministe : même profil -> mêmes fichiers.
"""
import json, os, zlib, subprocess, tempfile, wave
import numpy as np
from dataclasses import replace
from noyau import SR, VOYELLES, DIPHTONGUES, GLISSES, Timbre, voyelle, consonne, timbre_depuis
import vocalises

FORMES = {'court': .78, 'plat': 1.0, 'long': 1.85}  # facteur de longueur de la voyelle
ASCII = {'é': 'ee'}


RMS_REF = 10 ** (-16 / 20)
DECALAGE_VOYELLE = {'a': 0, 'o': -1, 'on': -1.5, 'e': -1.5, 'ee': -1.5, 'eu': -2, 'i': -3, 'u': -3,
                    'ai': -.5, 'oi': -1, 'ao': -.5, 'ei': -1.5, 'ou': -1.5}
CIBLE_VOCALISE = {'rire': -2, 'rire_moqueur': -3, 'rire_nerveux': -6, 'soupir': -7, 'hmm_reflexion': -5,
                  'hmm_doute': -5, 'hmm_accord': -5, 'euh': -4, 'inspiration_surprise': -5, 'ooh': -2,
                  'oh_decu': -4, 'ah': -3, 'hein': -3, 'pfff': -7, 'grogne': -3, 'tss': -9,
                  'reniflement': -13, 'baillement': -5}


CONSONNES_NOMS = ('ch', 'p', 'b', 't', 'd', 'k', 'm', 'n', 'l', 's', 'f', 'r', 'v', 'z', 'w', 'y')


def _voyelle_de(nom):
    tete = nom.split('_')[0] if not nom.startswith('_') else nom[1:].split('_')[0]
    for c in CONSONNES_NOMS:
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
        legato = replace(t, attaque=max(t.attaque, .02), relache=max(t.relache, .05))
        for c in p['consonnes']:
            for v in p['voyelles']:
                for forme, k in FORMES.items():
                    rng = np.random.default_rng(_graine(self.pid, c, v, forme))
                    cons = consonne(c, self.f0, rng, t)
                    debut_v, fin_v = (v, None) if v not in DIPHTONGUES else DIPHTONGUES[v]
                    glisse = (.45, 1.0)
                    if c in GLISSES:  # « wa », « yo » : la voyelle part de u / i
                        fin_v, debut_v, glisse = debut_v if fin_v is None else fin_v, GLISSES[c], (0.0, .3)
                        if v in DIPHTONGUES:
                            fin_v = DIPHTONGUES[v][0]
                    voy = voyelle(p['syllabe'] * k, self.f0, self.f0, VOYELLES[debut_v], rng, legato,
                                  formants_fin=VOYELLES[fin_v] if fin_v else None, glisse=glisse)
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
