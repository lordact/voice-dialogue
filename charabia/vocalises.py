"""Vocalises non verbales : rires, soupirs, « hmm », hésitations, surprise, agacement...

Toutes passent par la même source glottale et les mêmes formants que les syllabes (noyau.py),
avec le timbre du profil : un rire de Frank sonne comme Frank. Chaque fonction reçoit
f0 (Hz), le Timbre, un générateur aléatoire et renvoie un signal mono.
"""
import numpy as np
from noyau import SR, VOYELLES, voyelle, consonne, bruit_filtre, Timbre


def _cat(*parts):
    return np.concatenate([p for p in parts if len(p)])


def _silence(d):
    return np.zeros(int(d * SR))


def aspiration(duree, voyelle_cle, t, rng, force=.35):
    """« h » : souffle filtré par les formants de la voyelle qui suit."""
    f1, f2 = VOYELLES[voyelle_cle]
    n = int(duree * SR)
    b = rng.normal(0, 1, n)
    from noyau import resonateur
    s = resonateur(b, f1 * t.formant, 250) + resonateur(b, f2 * t.formant, 300) * .6
    return s * np.linspace(.2, 1, n) * force


def rire(f0, t, rng, style='ha'):
    """Rire en salves. ha : franc ; hihi : aigu, rapide ; hoho : grave, bouche fermée ; ricane : nasal, moqueur."""
    cfg = {'ha': ('a', 4, 1.3, .07, .055, 1.0), 'hihi': ('i', 5, 1.55, .05, .045, .85),
           'hoho': ('o', 3, 1.05, .085, .07, 1.0), 'ricane': ('on', 4, 1.2, .055, .06, .8)}[style]
    v, n, haut, dv, dg, force = cfg
    n += int(rng.integers(0, 2))
    parts = []
    for k in range(n):
        h = f0 * haut * (1 - .07 * k) * rng.uniform(.97, 1.03)
        tt = t if style != 'ricane' else Timbre(**{**t.__dict__, 'nasal': max(t.nasal, .5)})
        parts.append(aspiration(.03 if style != 'hoho' else .015, v, t, rng, .3))
        if style == 'hoho':
            parts.append(consonne('m', h, rng, t) * .5)
        parts.append(voyelle(dv * rng.uniform(.9, 1.15), h, h * .9, VOYELLES[v], rng, tt) * force * (1 - .08 * k))
        parts.append(_silence(dg * rng.uniform(.8, 1.2)))
    return _cat(*parts)


def rire_nerveux(f0, t, rng):
    parts = []
    for k in range(3):
        h = f0 * 1.35 * (1 - .04 * k)
        parts += [aspiration(.02, 'i', t, rng, .2), voyelle(.045, h, h * .95, VOYELLES['é'], rng, t) * .55, _silence(.05)]
    return _cat(*parts)


def soupir(f0, t, rng):
    inspir = bruit_filtre(.22, 1100 * t.formant, 1600 * t.formant, 900, rng, [(0, 0), (.6, .18), (1, .05)])
    expir = bruit_filtre(.7, 900 * t.formant, 600 * t.formant, 700, rng, [(0, 0), (.08, .55), (1, 0)])
    voix = voyelle(.55, f0 * .95, f0 * .78, VOYELLES['a'], rng, t, formants_fin=VOYELLES['eu'],
                   enveloppe=[(0, 0), (.1, .25), (1, 0)])
    n = max(len(expir), len(voix))
    corps = np.zeros(n)
    corps[:len(expir)] += expir
    corps[:len(voix)] += voix
    return _cat(inspir * .6, _silence(.06), corps)


def hmm(f0, t, rng, variante='reflexion'):
    """Bourdonnement nasal « mmm » avec une mélodie : réflexion, doute, accord (« mm-hm »)."""
    nas = Timbre(**{**t.__dict__, 'nasal': 1.0, 'brillance': .04})
    mm = (300, 1100)
    if variante == 'accord':
        a = voyelle(.14, f0, f0 * .97, mm, rng, nas)
        b = voyelle(.2, f0 * .95, f0 * 1.15, mm, rng, nas)
        return _cat(a, _silence(.07), b) * .7
    if variante == 'doute':
        return voyelle(.55, f0, f0, mm, rng, nas, contour=[(0, 1.0), (.45, .86), (1, 1.12)]) * .7
    return voyelle(.6, f0, f0, mm, rng, nas, contour=[(0, .97), (.7, 1.0), (1, 1.06)]) * .65


def euh(f0, t, rng):
    return voyelle(.32 * rng.uniform(.9, 1.15), f0 * .98, f0 * .93, VOYELLES['eu'], rng, t,
                   enveloppe=[(0, 0), (.15, .7), (.8, .6), (1, 0)])


def inspiration_surprise(f0, t, rng):
    """Hoquet de surprise : inspiration brève qui monte, puis un « oh ! » aigu."""
    insp = bruit_filtre(.16, 900 * t.formant, 2200 * t.formant, 900, rng, [(0, 0), (.7, .5), (1, .1)])
    oh = voyelle(.14, f0 * 1.4, f0 * 1.65, VOYELLES['o'], rng, t)
    return _cat(insp, oh)


def ooh(f0, t, rng):
    """« Oooh » d'admiration : glissé ou->o, la mélodie monte puis redescend."""
    return voyelle(.55, f0, f0, VOYELLES['u'], rng, t, contour=[(0, 1.0), (.45, 1.38), (1, 1.05)],
                   formants_fin=VOYELLES['o'], enveloppe=[(0, 0), (.12, 1), (.8, .8), (1, 0)])


def oh_decu(f0, t, rng):
    return voyelle(.38, f0 * 1.05, f0 * .78, VOYELLES['o'], rng, t, enveloppe=[(0, 0), (.1, .8), (1, 0)])


def ah(f0, t, rng):
    return voyelle(.2, f0 * 1.25, f0 * 1.02, VOYELLES['a'], rng, t)


def hein(f0, t, rng):
    nas = Timbre(**{**t.__dict__, 'nasal': max(t.nasal, .6)})
    return _cat(aspiration(.03, 'é', t, rng, .25), voyelle(.26, f0, f0 * 1.42, VOYELLES['é'], rng, nas))


def pfff(f0, t, rng):
    p = consonne('p', f0, rng, t)
    f = bruit_filtre(.32, 2400 * t.formant, 1500 * t.formant, 1600, rng, [(0, .7), (.2, .5), (1, 0)])
    return _cat(p, f * .9)


def grogne(f0, t, rng):
    """Grognement / souffle agacé : « hnn ! » court, nasal, avec un peu de bruit."""
    nas = Timbre(**{**t.__dict__, 'nasal': 1.0, 'raucite': max(t.raucite, .25), 'souffle': .12})
    v = voyelle(.18, f0 * .95, f0 * .8, (350, 1200), rng, nas, enveloppe=[(0, 0), (.1, 1), (1, 0)])
    b = bruit_filtre(.18, 1300, 900, 900, rng, [(0, .4), (1, 0)])
    return (v + b[:len(v)] * .5) * 1.1


def tss(f0, t, rng):
    """« Tss-tss » : deux claquements de langue."""
    c = consonne('t', f0, rng, t)
    return _cat(c, _silence(.07), consonne('t', f0, rng, t) * .8) * 1.2


def reniflement(f0, t, rng):
    a = bruit_filtre(.08, 3500, 4200, 1500, rng, [(0, 0), (.5, .4), (1, 0)])
    return _cat(a, _silence(.06), a * .8)


def baillement(f0, t, rng):
    return voyelle(.9, f0, f0, VOYELLES['o'], rng, Timbre(**{**t.__dict__, 'souffle': .1}),
                   contour=[(0, 1.15), (.35, 1.2), (1, .78)], formants_fin=VOYELLES['a'],
                   enveloppe=[(0, 0), (.2, .7), (.7, .6), (1, 0)])


TYPES = {
    'rire': lambda f0, t, rng, p: rire(f0, t, rng, p.get('rire', 'ha')),
    'rire_moqueur': lambda f0, t, rng, p: rire(f0, t, rng, 'ricane'),
    'rire_nerveux': lambda f0, t, rng, p: rire_nerveux(f0, t, rng),
    'soupir': lambda f0, t, rng, p: soupir(f0, t, rng),
    'hmm_reflexion': lambda f0, t, rng, p: hmm(f0, t, rng, 'reflexion'),
    'hmm_doute': lambda f0, t, rng, p: hmm(f0, t, rng, 'doute'),
    'hmm_accord': lambda f0, t, rng, p: hmm(f0, t, rng, 'accord'),
    'euh': lambda f0, t, rng, p: euh(f0, t, rng),
    'inspiration_surprise': lambda f0, t, rng, p: inspiration_surprise(f0, t, rng),
    'ooh': lambda f0, t, rng, p: ooh(f0, t, rng),
    'oh_decu': lambda f0, t, rng, p: oh_decu(f0, t, rng),
    'ah': lambda f0, t, rng, p: ah(f0, t, rng),
    'hein': lambda f0, t, rng, p: hein(f0, t, rng),
    'pfff': lambda f0, t, rng, p: pfff(f0, t, rng),
    'grogne': lambda f0, t, rng, p: grogne(f0, t, rng),
    'tss': lambda f0, t, rng, p: tss(f0, t, rng),
    'reniflement': lambda f0, t, rng, p: reniflement(f0, t, rng),
    'baillement': lambda f0, t, rng, p: baillement(f0, t, rng),
}
