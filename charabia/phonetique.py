"""Syllabaire « parlé » : des syllabes complètes, articulées comme dans une vraie langue.

Ce qui fait qu'on croit entendre parler, et que ce module reproduit :
  - des syllabes de formes variées : V, CV, CVC, CCV, CCVC (« a », « ba », « tam », « bla », « tros ») ;
  - les gestes des consonnes : silence d'occlusion puis explosion et souffle pour p/t/k,
    barre de voisement pour b/d/g, murmure nasal pour m/n, l et r « liquides », frictions s/ch/f/h,
    v/z voisées, glissés w/y ;
  - la coarticulation : les formants partent du « lieu » de la consonne et glissent vers la voyelle
    (puis vers la consonne finale), sans aucune rupture de la source ;
  - des syllabes réduites (inaccentuées) : plus courtes, voyelle centralisée, plus douces ;
  - une source moins « parfaite » : micro-instabilités de hauteur (jitter) et d'amplitude
    (shimmer), pente spectrale qui adoucit le buzz électronique.

La couleur de base reste celle du synthétiseur d'origine (scie + carré + formants) : on ne
change que ce qui manque pour que cela sonne comme de la parole. Aucune vraie langue n'est
construite : l'inventaire de syllabes est tiré au hasard (déterministe) par profil.
"""
import zlib
import numpy as np
from scipy.signal import lfilter
from noyau import SR, VOYELLES, DIPHTONGUES, resonateur

F3 = {'a': 2500, 'e': 2550, 'i': 2950, 'o': 2400, 'u': 2300, 'é': 2650, 'eu': 2350, 'on': 2400}
SCHWA = (500, 1450)
LIEU = {'p': 'lab', 'b': 'lab', 'm': 'lab', 'f': 'lab', 'v': 'lab', 'w': 'lab',
        't': 'alv', 'd': 'alv', 'n': 'alv', 's': 'alv', 'z': 'alv', 'l': 'alv',
        'ch': 'pal', 'y': 'pal', 'k': 'vel', 'g': 'vel', 'r': 'r', 'h': None}
LOCUS_F2 = {'lab': 850, 'alv': 1750, 'pal': 2150, 'r': 1150}
BRUIT_EXPLOSION = {'p': 900, 'b': 700, 't': 3600, 'd': 3000, 'k': 1900, 'g': 1700}
FRICTION = {'s': (5600, 1500, .45), 'z': (5200, 1500, .3), 'ch': (3100, 1300, .5), 'f': (2400, 2400, .22),
            'v': (2200, 2000, .16)}
SOURDES = ('p', 't', 'k')
SONORES = ('b', 'd', 'g')
ATTAQUES_GROUPEES = {'bl': 1.0, 'pl': .8, 'kl': .6, 'gl': .5, 'fl': .7, 'br': .9, 'pr': .7, 'tr': 1.0, 'dr': .7,
                     'kr': .7, 'gr': .7, 'fr': .6, 'st': .6, 'sp': .4, 'sk': .4, 'sl': .4, 'sm': .3, 'sn': .3,
                     'kw': .4, 'tw': .3}
CODAS_DEFAUT = {'': 6.0, 'n': 1.6, 'l': 1.0, 's': .9, 'm': .7, 'r': .9, 't': .5, 'k': .4}


def _graine(*parts):
    return zlib.crc32('|'.join(map(str, parts)).encode())


def _decouper_attaque(a):
    """'tr' -> ['t', 'r'] ; 'ch' -> ['ch'] ; '' -> []."""
    if a in ('', 'ch'):
        return [a] if a else []
    if len(a) == 2:
        return [a[0], a[1]]
    return [a]


def nom(attaque, voyelle, coda):
    v = {'é': 'ee'}.get(voyelle, voyelle)
    return '%s%s%s' % (attaque or '_', v, ('-' + coda) if coda else '')


def inventaire(pid, p, taille=None):
    """Syllabes que ce profil emploie, avec leur poids. Les « particules » sont des syllabes
    courtes et neutres (le, de, na…) réemployées comme petits mots-outils : c'est leur retour
    fréquent qui donne l'impression d'une langue. Déterministe : même profil -> même liste."""
    rng = np.random.default_rng(_graine('inventaire', pid))
    attaques = dict(p['consonnes'])
    if 'g' not in attaques and 'k' in attaques:
        attaques['g'] = round(attaques['k'] * .8, 2)
    attaques.setdefault('h', .5)
    for a, w in ATTAQUES_GROUPEES.items():
        attaques[a] = w * p.get('groupes', .22)
    codas = p.get('codas', CODAS_DEFAUT)
    voy = p['voyelles']
    ka, wa = list(attaques), np.array(list(attaques.values()), float)
    kv, wv = list(voy), np.array(list(voy.values()), float)
    kc, wc = list(codas), np.array(list(codas.values()), float)
    taille = taille or p.get('taille_inventaire', 56)
    vus, liste = set(), []
    essais = 0
    while len(liste) < taille and essais < taille * 50:
        essais += 1
        a = ka[rng.choice(len(ka), p=wa / wa.sum())]
        v = kv[rng.choice(len(kv), p=wv / wv.sum())]
        c = kc[rng.choice(len(kc), p=wc / wc.sum())]
        if v in DIPHTONGUES and c:          # pas de « bain-s » : diphtongue = syllabe ouverte
            c = ''
        if a in ('w', 'y') and v in ('u', 'i'):
            continue
        n = nom(a, v, c)
        if n in vus:
            continue
        vus.add(n)
        poids = round(float(wa[ka.index(a)] * wv[kv.index(v)] * (1.4 if not c else 1.0)), 3)
        liste.append({'nom': n, 'attaque': a, 'voyelle': v, 'coda': c, 'poids': poids, 'particule': False,
                      'dure': _decouper_attaque(a)[:1] in (['p'], ['t'], ['k'], ['b'], ['d'], ['g'])})
    # Particules : 6 syllabes ouvertes et neutres, fréquentes.
    for a, v in [('d', 'eu'), ('n', 'a'), ('l', 'e'), ('m', 'i'), ('', 'a'), ('t', 'eu')]:
        n = nom(a, v, '')
        if n not in vus:
            vus.add(n)
            liste.append({'nom': n, 'attaque': a, 'voyelle': v, 'coda': '', 'poids': 1.0, 'particule': True,
                          'dure': a in ('d', 't')})
        else:
            next(x for x in liste if x['nom'] == n)['particule'] = True
    return liste


def _filtre_variable(x, pistes, bws, gains, bloc=128):
    """Banc de résonateurs dont les fréquences suivent des pistes (un tableau par formant)."""
    n = len(x)
    out = np.zeros(n)
    for f_piste, bw, g in zip(pistes, bws, gains):
        zi = np.zeros(2)
        r = np.exp(-np.pi * bw / SR)
        for a in range(0, n, bloc):
            b = min(n, a + bloc)
            f = f_piste[(a + b) // 2]
            c1, c2 = 2 * r * np.cos(2 * np.pi * f / SR), -r * r
            y, zi = lfilter([1 - r], [1, -c1, -c2], x[a:b], zi=zi)
            out[a:b] += y * g
    return out


def syllabe(attaque, voyelle, coda, duree_voyelle, f0, t, rng, reduite=False):
    """Rend une syllabe complète à hauteur fixe f0 (la mélodie est ajoutée à la lecture).
    Renvoie (signal, début de la voyelle en s)."""
    k = t.formant
    segs = []        # (durée, type, données)
    for c in _decouper_attaque(attaque):
        segs.append(c)
    # --- trajectoires (échantillon par échantillon) ---------------------------------------
    v1 = VOYELLES[DIPHTONGUES[voyelle][0] if voyelle in DIPHTONGUES else voyelle]
    v2 = VOYELLES[DIPHTONGUES[voyelle][1]] if voyelle in DIPHTONGUES else None
    f3v = F3.get(DIPHTONGUES[voyelle][0] if voyelle in DIPHTONGUES else voyelle, 2500)
    if reduite:  # voyelle inaccentuée : centralisée vers le schwa, plus courte
        v1 = (v1[0] * .65 + SCHWA[0] * .35, v1[1] * .65 + SCHWA[1] * .35)
        v2 = None if v2 is None else (v2[0] * .7 + SCHWA[0] * .3, v2[1] * .7 + SCHWA[1] * .3)
    F1, F2, F3_, AV, AN, NAS, ORAL, FRIC = [], [], [], [], [], [], [], []
    extra = []   # (position en échantillons, signal) : explosions, frictions

    def ajoute(n, f1, f2, f3, av, an=0.0, nas=0.0, oral=1.0):
        n = max(1, int(n))
        for lst, val in ((F1, f1), (F2, f2), (F3_, f3), (AV, av), (AN, an), (NAS, nas), (ORAL, oral)):
            lst.append(np.broadcast_to(np.asarray(val, float), (n,)) if np.ndim(val) == 0 else np.asarray(val, float))
        return n

    def pos():
        return sum(len(a) for a in F1)

    vit = min(1.25, max(.75, duree_voyelle / .13)) ** .5   # consonnes un peu plus longues chez les lents
    lieu_final = None
    for i, c in enumerate(segs):
        premier_groupe = len(segs) == 2 and i == 0
        ech = (.7 if premier_groupe else 1.0) * vit * SR
        lieu = LIEU.get(c)
        f2l = LOCUS_F2.get(lieu, v1[1])
        if c in SOURDES:
            ajoute(.032 * ech, 300, f2l, 2500, 0.0)                         # occlusion : silence
            p0 = pos()
            n = int(.006 * SR)
            b = resonateur(rng.normal(0, 1, n), BRUIT_EXPLOSION[c] * k, 900) * np.exp(-np.linspace(0, 4, n))
            extra.append((p0, b * 1.4))
            if not (len(segs) == 2 and i == 0 and segs[1] in ('l', 'r', 'w')):
                ajoute(.03 * ech, np.linspace(400, v1[0], int(.03 * ech)), np.linspace(f2l, v1[1], int(.03 * ech)),
                       f3v, np.linspace(0, .4, int(.03 * ech)), an=.55)     # souffle (aspiration)
        elif c in SONORES:
            ajoute(.022 * ech, 220, f2l, 2400, .12, oral=.25)               # barre de voisement
            p0 = pos()
            n = int(.004 * SR)
            extra.append((p0, resonateur(rng.normal(0, 1, n), BRUIT_EXPLOSION[c] * k, 900) * .6))
        elif c in ('m', 'n'):
            ajoute(.05 * ech, 280, 1100 if c == 'm' else 1500, 2400, .55, nas=1.0, oral=.18)
        elif c == 'l':
            ajoute(.042 * ech, 360, 1150, 2800, .65)
        elif c == 'r':
            ajoute(.048 * ech, 420, 1150, 1650, .62)                         # r « américain » : F3 bas
        elif c in ('w', 'y'):
            ajoute(.035 * ech, 300, 700 if c == 'w' else 2200, 2300 if c == 'w' else 3000, .55)
        elif c == 'h':
            ajoute(.05 * ech, v1[0], v1[1], f3v, 0.0, an=.7)
        elif c in FRICTION:
            centre, bw, g = FRICTION[c]
            n = int((.07 if c in ('s', 'ch') else .055) * ech)
            env = np.sin(np.linspace(0, np.pi, n)) ** .7
            p0 = pos()
            extra.append((p0, resonateur(rng.normal(0, 1, n), centre * k, bw) * env * g * 2.2))
            ajoute(n, 300, f2l, 2500, .3 if c in ('v', 'z') else 0.0, oral=.35)
        lieu_final = lieu
    debut_voyelle = pos()
    # --- voyelle : transition depuis le lieu de la consonne -------------------------------
    nv = int(duree_voyelle * SR)
    f2_depart = v1[1] * .55 + LOCUS_F2.get(lieu_final, v1[1]) * .45 if lieu_final else v1[1]
    f1_depart = v1[0] * .6 + 300 * .4 if lieu_final and lieu_final != 'r' else v1[0]
    if lieu_final == 'vel':   # « pince » vélaire : F2 et F3 se rapprochent
        f2_depart = v1[1] * 1.12
    nt = min(nv // 2, int(.045 * SR))
    f1 = np.full(nv, float(v1[0])); f2 = np.full(nv, float(v1[1])); f3 = np.full(nv, float(f3v))
    f1[:nt] = np.linspace(f1_depart, v1[0], nt); f2[:nt] = np.linspace(f2_depart, v1[1], nt)
    if lieu_final == 'r':
        f3[:nt] = np.linspace(1700, f3v, nt)
    if v2 is not None:
        a = int(nv * .45)
        f1[a:] = np.linspace(v1[0], v2[0], nv - a); f2[a:] = np.linspace(v1[1], v2[1], nv - a)
    # coda : la voyelle se dirige vers la consonne finale
    if coda:
        nc = min(nv // 3, int(.035 * SR))
        cible2 = {'n': 1700, 'm': 900, 'l': 1050, 'r': 1200, 's': 1750, 't': 1750, 'k': f2[-1] * 1.1}[coda]
        f2[-nc:] = np.linspace(f2[-nc], cible2, nc)
        if coda == 'r':
            f3[-int(nv * .45):] = np.linspace(f3v, 1700, int(nv * .45))
        if coda in ('n', 'm', 's', 't', 'k'):
            f1[-nc:] = np.linspace(f1[-nc], 350, nc)
    env = np.ones(nv)
    # profil d'énergie d'une vraie syllabe : monte vite, culmine tôt, décroît doucement
    env *= np.interp(np.arange(nv), [0, nv * .25, nv], [.85, 1.0, .72 if coda else .8])
    av_v = env * (.72 if reduite else 1.0)
    ajoute(nv, f1, f2, f3, av_v, an=.04)
    # consonne finale
    if coda in ('n', 'm'):
        ajoute(.055 * SR, 280, 1100 if coda == 'm' else 1500, 2400, .45 * np.linspace(1, .3, int(.055 * SR)), nas=1.0, oral=.18)
    elif coda == 'l':
        ajoute(.045 * SR, 380, 1050, 2700, .5 * np.linspace(1, .25, int(.045 * SR)))
    elif coda == 's':
        n = int(.075 * SR)
        extra.append((pos(), resonateur(rng.normal(0, 1, n), 5600 * k, 1500) * np.linspace(1, 0, n) ** 1.5 * .9))
        ajoute(n, 350, 1700, 2600, 0.0)
    elif coda in ('t', 'k'):
        ajoute(.03 * SR, 300, 1700, 2500, 0.0)                               # occlusion finale
        n = int(.005 * SR)
        extra.append((pos(), resonateur(rng.normal(0, 1, n), BRUIT_EXPLOSION[coda] * k, 900) * .5))
        ajoute(.006 * SR, 300, 1700, 2500, 0.0)
    # --- source et filtrage -----------------------------------------------------------------
    F1 = np.concatenate(F1) * k; F2 = np.concatenate(F2) * k; F3_ = np.concatenate(F3_) * k
    AV = np.concatenate(AV); AN = np.concatenate(AN); NAS = np.concatenate(NAS); ORAL = np.concatenate(ORAL)
    n = len(AV)
    # lissage des commandes (pas de marches d'escalier entre segments)
    lisse = np.hanning(int(.012 * SR)); lisse /= lisse.sum()
    for arr in (AV, AN, NAS, ORAL):
        arr[:] = np.convolve(arr, lisse, mode='same')
    tt = np.arange(n) / SR
    f0s = np.full(n, float(f0))
    f0s *= 1 + t.vibrato * np.sin(2 * np.pi * t.vib_freq * tt)
    if t.chant:
        f0s *= 1 + t.chant * np.clip((tt - debut_voyelle / SR - t.chant_retard) / .15, 0, 1) * np.sin(2 * np.pi * t.vib_freq * tt)
    jit = t.jitter
    if jit:
        f0s *= 1 + jit * np.convolve(rng.normal(0, 1, n), np.ones(200) / 14, mode='same')
    phase = np.cumsum(f0s / SR)
    src = (2 * (phase % 1.0) - 1) * t.scie + np.sign(np.sin(2 * np.pi * phase)) * t.carre
    if t.raucite:
        src *= 1 + t.raucite * np.sign(np.sin(np.pi * phase))
    pente = t.pente
    if pente:  # adoucit le buzz : passe-bas d'ordre 1 (source glottale plus naturelle)
        a = np.exp(-2 * np.pi * pente / SR)
        src = lfilter([1 - a], [1, -a], src) * (1 + 1500 / pente) ** .5
    shim = t.shimmer
    amp = AV * (1 + shim * np.convolve(rng.normal(0, 1, n), np.ones(300) / 17, mode='same')) if shim else AV
    bruit = rng.normal(0, 1, n)
    exc = src * amp + bruit * (AN * .35 + t.souffle * AV)
    bw = t.largeur
    oral = _filtre_variable(exc, [F1, F2, F3_], [90 * bw, 130 * bw, 220 * bw], [1.0, .55, .22])
    oral = oral + resonateur(exc, 3500 * k, 300) * t.brillance * .5
    nasal = resonateur(src * amp, 260, 90) * .9 + resonateur(src * amp, 1300 * k, 250) * .12
    sig = oral * ORAL * (1 - .5 * t.nasal) + nasal * (NAS + t.nasal * .5)
    for p0, b in extra:
        fin = min(n, p0 + len(b))
        sig[p0:fin] += b[:fin - p0] * .5
    # fondus de bord (pas de clic)
    f = min(int(.006 * SR), n // 4)
    sig[:f] *= np.linspace(0, 1, f); sig[-f:] *= np.linspace(1, 0, f)
    return sig, debut_voyelle / SR
