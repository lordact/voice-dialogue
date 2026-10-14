"""Noyau DSP du charabia Card Hustle.

Reprend la synthèse de `Outils/generer_voix.py` (les 10 voix d'origine du village) :
  - voyelle : source glottale « scie + carré » + souffle, filtrée par deux formants (F1, F2)
    et un troisième fixe vers 2900 Hz, vibrato léger, attaque 12 ms, relâche 35 ms ;
  - consonnes : éclats de bruit (p t k b d), bruits filtrés (s ch f), bourdonnements (m n l r).

Avec un `Timbre()` par défaut, le résultat est celui de l'ancien script (voir
`ligne_origine`, vérifié par tests/test_noyau.py). Les profils ne font que déplacer ces
réglages (hauteur, longueur du conduit vocal, souffle, raucité, nasalité, vibrato), pour que
toutes les nouvelles voix gardent la couleur des premières.
"""
from dataclasses import dataclass, replace
import numpy as np
from scipy.signal import lfilter

SR = 44100
VOYELLES = {'a': (800, 1250), 'e': (480, 1850), 'i': (320, 2300), 'o': (520, 900),
            'u': (360, 820), 'é': (420, 2000), 'eu': (480, 1450), 'on': (430, 1000)}
CONSONNES = ['p', 't', 'k', 'b', 'd', 'm', 'n', 'l', 's', 'ch', 'f', 'r', '']
# Style mélodieux : diphtongues (la voyelle glisse vers une seconde dans sa seconde moitié) et
# glissés d'attaque w/y. Séparés de VOYELLES pour ne pas changer la reproduction des voix d'origine.
DIPHTONGUES = {'ai': ('a', 'i'), 'oi': ('o', 'i'), 'ao': ('a', 'u'), 'ei': ('é', 'i'), 'ou': ('o', 'u')}
GLISSES = {'w': 'u', 'y': 'i'}


@dataclass(frozen=True)
class Timbre:
    formant: float = 1.0      # longueur du conduit vocal (<1 : grande personne, >1 : enfant)
    largeur: float = 1.0      # largeur de bande des formants (>1 : voix plus sourde)
    scie: float = .8          # part de dent de scie dans la source
    carre: float = .25        # part de carré : la couleur « synthé » des voix d'origine
    souffle: float = .02      # bruit ajouté à la source
    vibrato: float = .012     # profondeur du vibrato (fraction de f0)
    vib_freq: float = 5.5
    raucite: float = 0.0      # sous-harmonique f0/2 (voix âgée, fatiguée)
    nasal: float = 0.0        # résonance nasale 250 Hz, F2 atténué
    attaque: float = .012
    relache: float = .035
    brillance: float = .15    # gain du troisième formant
    chant: float = 0.0        # vibrato « chanté » ajouté sur les voyelles tenues (style mélodieux)
    chant_retard: float = .12 # il s'installe après ce délai (s), comme chez un chanteur
    jitter: float = 0.0       # micro-instabilité de hauteur (style parlé)
    shimmer: float = 0.0      # micro-instabilité d'amplitude (style parlé)
    pente: float = 0.0        # coupure (Hz) d'un passe-bas sur la source : adoucit le buzz (0 = son d'origine)


def resonateur(x, f, bw):
    """Résonateur à deux pôles (formant), gain unité au centre. Même filtre que l'original."""
    r = np.exp(-np.pi * bw / SR)
    c1, c2 = 2 * r * np.cos(2 * np.pi * f / SR), -r * r
    return lfilter([1 - r], [1, -c1, -c2], x)


def resonateur_glissant(x, f_debut, f_fin, bw, bloc=256, debut=0.0, fin=1.0):
    """Formant dont la fréquence glisse (diphtongues, soupirs, w/y) : coefficients mis à jour par
    bloc. Le glissé a lieu entre les fractions `debut` et `fin` de la durée."""
    if abs(f_fin - f_debut) < 1:
        return resonateur(x, f_debut, bw)
    y = np.empty_like(x)
    zi = np.zeros(2)
    n = len(x)
    for a in range(0, n, bloc):
        b = min(n, a + bloc)
        pos = (a + b) / 2 / max(1, n)
        u = min(1.0, max(0.0, (pos - debut) / max(1e-6, fin - debut)))
        f = f_debut + (f_fin - f_debut) * u
        r = np.exp(-np.pi * bw / SR)
        c1, c2 = 2 * r * np.cos(2 * np.pi * f / SR), -r * r
        y[a:b], zi = lfilter([1 - r], [1, -c1, -c2], x[a:b], zi=zi)
    return y


def courbe(points, n):
    """Interpole une courbe [(t 0..1, valeur), ...] sur n échantillons."""
    t = np.linspace(0, 1, n)
    xs, ys = zip(*points)
    return np.interp(t, xs, ys)


def source(f0, rng, t: Timbre, n_bruit=None):
    """Source glottale de l'original : 0,8 scie + 0,25 carré + bruit. f0 = tableau par échantillon."""
    n = len(f0)
    phase = np.cumsum(f0 / SR)
    scie = 2 * (phase % 1.0) - 1
    carre = np.sign(np.sin(2 * np.pi * phase))
    s = scie * t.scie + carre * t.carre + rng.normal(0, t.souffle, n)
    if t.raucite:
        s *= 1 + t.raucite * np.sign(np.sin(np.pi * phase))
    return s


def voyelle(duree, f0_debut, f0_fin, formants, rng, t: Timbre = Timbre(), contour=None,
            formants_fin=None, enveloppe=None, glisse=(0.0, 1.0)):
    """Voyelle de l'original, avec en plus : courbe de hauteur libre, formants glissants,
    enveloppe libre. Sans ces options et avec Timbre(), sortie identique à l'ancien script."""
    n = int(duree * SR)
    if n <= 0:
        return np.zeros(0)
    if contour is None:
        f0 = np.linspace(f0_debut, f0_fin, n)
    else:
        f0 = courbe(contour, n) * f0_debut
    f0 = f0 * (1 + t.vibrato * np.sin(np.linspace(0, 2 * np.pi * t.vib_freq * duree, n)))
    if t.chant:
        tt = np.arange(n) / SR
        rampe = np.clip((tt - t.chant_retard) / .15, 0, 1)
        f0 = f0 * (1 + t.chant * rampe * np.sin(2 * np.pi * t.vib_freq * tt))
    src = source(f0, rng, t)
    f1, f2 = formants[0] * t.formant, formants[1] * t.formant
    bw1, bw2, bw3 = 90 * t.largeur, 140 * t.largeur, 250 * t.largeur
    if formants_fin is None:
        sig = resonateur(src, f1, bw1) + resonateur(src, f2, bw2) * .55 * (1 - .5 * t.nasal)
    else:
        g1, g2 = formants_fin[0] * t.formant, formants_fin[1] * t.formant
        sig = resonateur_glissant(src, f1, g1, bw1, debut=glisse[0], fin=glisse[1]) + \
            resonateur_glissant(src, f2, g2, bw2, debut=glisse[0], fin=glisse[1]) * .55 * (1 - .5 * t.nasal)
    sig = sig + resonateur(src, 2900 * t.formant, bw3) * t.brillance
    if t.nasal:
        sig = sig + resonateur(src, 250, 100) * t.nasal * .8
    if enveloppe is None:
        env = np.ones(n)
        a = min(n // 4, int(t.attaque * SR)); r = min(n // 3, int(t.relache * SR))
        if a:
            env[:a] = np.linspace(0, 1, a)
        if r:
            env[-r:] = np.linspace(1, 0, r)
    else:
        env = courbe(enveloppe, n)
    return sig * env


def consonne(c, f0, rng, t: Timbre = Timbre()):
    """Consonnes de l'original ; les fréquences suivent la taille du conduit vocal.
    Ajouts du style mélodieux : v et z (fricatives voisées) ; w et y sont des glissés de
    voyelle (rendus par la voyelle elle-même, voir banque.py)."""
    if c in ('', 'w', 'y'):
        return np.zeros(0)
    if c in ('v', 'z'):
        n = int(.05 * SR)
        env = np.sin(np.linspace(0, np.pi, n))
        bruit = resonateur(rng.normal(0, 1, n), (2200 if c == 'v' else 5000) * t.formant, 1800) * .22
        phase = np.cumsum(np.full(n, f0) / SR)
        hum = resonateur(np.sin(2 * np.pi * phase) + .3 * np.sin(4 * np.pi * phase), 400 * t.formant, 250) * .5
        return (bruit + hum) * env
    k = t.formant
    if c in 'ptkbd':
        n = int(.018 * SR)
        bruit = rng.normal(0, 1, n) * np.exp(-np.linspace(0, 6, n))
        return resonateur(bruit, {'p': 900, 't': 3200, 'k': 1800, 'b': 600, 'd': 2600}[c] * k, 600) * .9
    if c in ('s', 'ch', 'f'):
        n = int(.05 * SR)
        bruit = rng.normal(0, 1, n)
        centre = {'s': 5500, 'ch': 3000, 'f': 2200}[c] * k
        env = np.sin(np.linspace(0, np.pi, n))
        return resonateur(bruit, centre, 1800) * env * .5
    n = int(.045 * SR)
    phase = np.cumsum(np.full(n, f0) / SR)
    son = np.sin(2 * np.pi * phase) + .3 * np.sin(4 * np.pi * phase)
    if c == 'r':
        son *= 1 + .5 * np.sin(np.linspace(0, 2 * np.pi * 3, n))
    env = np.sin(np.linspace(0, np.pi, n))
    return resonateur(son, {'m': 300, 'n': 350, 'l': 450, 'r': 600}[c] * k, 200) * env * .6


def bruit_filtre(duree, centre_debut, centre_fin, bw, rng, enveloppe):
    """Souffle filtré (inspirations, soupirs, reniflements, « pfff »)."""
    n = int(duree * SR)
    return resonateur_glissant(rng.normal(0, 1, n), centre_debut, centre_fin, bw) * courbe(enveloppe, n)


# ---------------------------------------------------------------------------
# Reproduction exacte de l'ancien générateur (référence d'écoute A/B et test).
LIGNES_ORIGINE = [
    ('affirmation', 5, 210, 1.0), ('question', 5, 220, 1.05), ('exclamation', 4, 245, 1.15),
    ('calme', 6, 190, .9), ('joyeux', 5, 235, 1.1), ('question', 4, 215, 1.0),
    ('affirmation', 6, 200, .95), ('exclamation', 5, 250, 1.2), ('calme', 5, 185, .85),
    ('joyeux', 6, 230, 1.05)]


def ligne_origine(index):
    """Copie fidèle de `ligne()` d'Outils/generer_voix.py (mêmes tirages, même ordre)."""
    intonation, mots, f0, vitesse = LIGNES_ORIGINE[index]
    rng = np.random.default_rng(1000 + index)
    morceaux = []
    syllabes = [rng.integers(1, 4) for _ in range(mots)]
    total = sum(syllabes)
    k = 0
    for m, nb in enumerate(syllabes):
        for s in range(nb):
            t = k / max(1, total - 1)
            if intonation == 'question':
                cible = f0 * (1 - .08 * t + (.45 * (t - .7) / .3 if t > .7 else 0))
            elif intonation == 'exclamation':
                cible = f0 * (1.15 - .2 * t)
            elif intonation == 'calme':
                cible = f0 * (1 - .12 * t)
            elif intonation == 'joyeux':
                cible = f0 * (1.05 + .1 * np.sin(k * 1.9))
            else:
                cible = f0 * (1.05 - .22 * t)
            accent = 1.12 if s == 0 else 1.0
            debut = cible * accent * rng.uniform(.97, 1.03)
            fin = debut * rng.uniform(.93, 1.04)
            if intonation == 'question' and k == total - 1:
                fin = debut * 1.25
            c = CONSONNES[rng.integers(len(CONSONNES))]
            v = list(VOYELLES)[rng.integers(len(VOYELLES))]
            duree = rng.uniform(.09, .15) / vitesse * (1.6 if k == total - 1 else 1.0)
            morceaux.append(consonne(c, debut, rng))
            morceaux.append(voyelle(duree, debut, fin, VOYELLES[v], rng) * (1.25 if intonation == 'exclamation' else 1.0) * accent)
            k += 1
        if m < mots - 1:
            morceaux.append(np.zeros(int(rng.uniform(.05, .12) / vitesse * SR)))
    sig = np.concatenate([np.zeros(int(.03 * SR))] + morceaux + [np.zeros(int(.08 * SR))])
    return sig / (np.max(np.abs(sig)) + 1e-9) * .8


def timbre_depuis(d: dict) -> Timbre:
    """Construit un Timbre depuis la section « timbre » d'un profil JSON."""
    return replace(Timbre(), **{k: float(v) for k, v in d.items()})
