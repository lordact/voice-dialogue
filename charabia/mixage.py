"""Rendu des partitions et mixage des scènes de démonstration.

`rendre` rejoue les grains comme le ferait le lecteur Godot : pitch_scale = rééchantillonnage
(la hauteur et la durée changent ensemble), gain en dB. `spatialiser` approxime
AudioStreamPlayer3D : atténuation en distance inverse, filtre passe-bas qui se ferme avec la
distance, panoramique à puissance constante.
"""
import numpy as np
from scipy.signal import lfilter
from noyau import SR


def grain(banque, nom):
    kind, rest = nom.split(':', 1)
    if kind == 'syl':
        return banque.syllabes[rest][0]
    typ, var = rest.rsplit(':', 1)
    return banque.vocalises[typ][int(var)]


def reechantillonner(sig, pitch):
    if abs(pitch - 1) < 1e-4:
        return sig
    pos = np.arange(0, len(sig) - 1, pitch)
    return np.interp(pos, np.arange(len(sig)), sig)


def rendre(evts, banque, fondu_fin=None):
    """Partition -> signal mono. fondu_fin (s) : interruption propre (le joueur passe la ligne)."""
    if not evts:
        return np.zeros(0)
    morceaux = [(int(ev['t'] * SR), reechantillonner(grain(banque, ev['grain']), ev['pitch']) * 10 ** (ev['db'] / 20))
                for ev in evts]
    n = max(a + len(s) for a, s in morceaux)
    out = np.zeros(n)
    for a, s in morceaux:
        out[a:a + len(s)] += s
    if fondu_fin is not None:
        coupe = int(fondu_fin * SR)
        f = int(.06 * SR)
        out = out[:coupe + f].copy()
        out[coupe:coupe + f] *= np.linspace(1, 0, len(out[coupe:coupe + f]))
    return out


def spatialiser(mono, distance=1.0, pan=0.0, unite=3.0):
    """Mono -> stéréo. distance en mètres, pan -1 (gauche) .. 1 (droite)."""
    d = max(distance, .1)
    gain = unite / (unite + max(0.0, d - unite) * 1.4)
    if d > 4:  # air + obstacles : les aigus tombent avec la distance
        fc = max(1800.0, 9000.0 - 650.0 * (d - 4))
        a = np.exp(-2 * np.pi * fc / SR)
        mono = lfilter([1 - a], [1, -a], mono)
    g, d_ = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    return np.stack([mono * gain * g * 1.41, mono * gain * d_ * 1.41], axis=1) * .707


def spatialiser_trajet(mono, distances, pans):
    """Comme spatialiser, mais la source (ou l'auditeur) se déplace : courbes échantillonnées."""
    n = len(mono)
    tt = np.linspace(0, 1, n)
    d = np.interp(tt, np.linspace(0, 1, len(distances)), distances)
    pn = np.interp(tt, np.linspace(0, 1, len(pans)), pans)
    gain = 3.0 / (3.0 + np.maximum(0, d - 3) * 1.4)
    # passe-bas à coupure variable, par blocs
    out = np.zeros(n)
    zi = np.zeros(1)
    for a in range(0, n, 512):
        b = min(n, a + 512)
        fc = max(1800.0, 9000.0 - 650.0 * max(0.0, d[a] - 4))
        k = np.exp(-2 * np.pi * fc / SR)
        out[a:b], zi = lfilter([1 - k], [1, -k], mono[a:b], zi=zi * 1.0)
    g, dr = np.cos((pn + 1) * np.pi / 4), np.sin((pn + 1) * np.pi / 4)
    return np.stack([out * gain * g, out * gain * dr], axis=1)


class Piste:
    """Piste stéréo où l'on pose des sons à des instants donnés, avec sous-titres."""

    def __init__(self):
        self.sons = []      # (t, stereo)
        self.titres = []    # dict(debut, fin, qui, texte, emotion, joueur)
        self.fin = 0.0      # durée minimale (silences de fin compris)

    def poser(self, t, stereo):
        self.sons.append((t, stereo))

    def titre(self, debut, fin, qui, texte, emotion='', joueur=False, note=''):
        self.titres.append({'debut': round(debut, 3), 'fin': round(fin, 3), 'qui': qui, 'texte': texte,
                            'emotion': emotion, 'joueur': joueur, 'note': note})

    def mixer(self, fond=None, fond_db=-30.0):
        n = max(max(int(t * SR) + len(s) for t, s in self.sons), int(self.fin * SR)) + int(.6 * SR)
        out = np.zeros((n, 2))
        for t, s in self.sons:
            a = int(t * SR)
            out[a:a + len(s)] += s
        if fond is not None:
            f = np.resize(fond, (n, 2)) if fond.ndim == 2 else np.stack([np.resize(fond, n)] * 2, axis=1)
            fd = np.minimum(1, np.minimum(np.arange(n), n - np.arange(n)) / (SR * .8))[:, None]
            out += f * 10 ** (fond_db / 20) * fd
        pic = np.max(np.abs(out)) + 1e-9
        return out * min(1.0, .89 / pic)


def egaliser_sonie(stereo, cible_db=-21.0):
    """Met une piste à une sonie de référence (RMS des passages actifs), pour une écoute A/B
    honnête : à l'oreille, la version la plus forte paraît toujours « meilleure »."""
    m = stereo.mean(axis=1)
    b = 2205
    blocs = m[:len(m) // b * b].reshape(-1, b)
    r = np.sqrt((blocs ** 2).mean(axis=1))
    actifs = blocs[r > 10 ** (-50 / 20)]
    if not len(actifs):
        return stereo
    rms = np.sqrt((actifs ** 2).mean())
    gain = min(10 ** (cible_db / 20) / rms, .95 / (np.max(np.abs(stereo)) + 1e-9))
    return stereo * gain
