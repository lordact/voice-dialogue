"""Du sous-titre anglais à une partition de grains (charabia).

Principes :
  - aucune traduction mot à mot : la longueur et la ponctuation de la réplique décident du
    nombre de syllabes, des pauses et de la courbe mélodique (question, exclamation...) ;
  - motif : le texte exact (normalisé) fixe la graine du « motif » (découpage en mots,
    syllabes, accents, petite mélodie propre). Une même réplique garde donc une identité
    reconnaissable, quel que soit le locuteur ; le profil choisit ses propres sons
    (inventaire de consonnes/voyelles) et l'émotion déforme la prosodie ;
  - variation : un second tirage (motif + locuteur + occurrence) ajoute de petites
    différences de rythme et de hauteur et choisit les vocalises, avec anti-répétition.

Tout est volontairement simple et sans numpy, pour être porté tel quel en GDScript :
FNV-1a 32 bits pour les graines, xorshift32 pour le hasard.
"""
import math
import re

M32 = 0xFFFFFFFF


def arrondi(x):
    """Arrondi « au plus proche, .5 vers le haut », comme round() de GDScript (pas l'arrondi bancaire de Python)."""
    return int(math.floor(x + .5))


def fnv1a(texte):
    h = 0x811C9DC5
    for b in texte.encode('utf-8'):
        h ^= b
        h = (h * 0x01000193) & M32
    return h


class Alea:
    def __init__(self, graine):
        self.x = (graine & M32) or 0x9E3779B9

    def suivant(self):
        x = self.x
        x ^= (x << 13) & M32
        x ^= x >> 17
        x ^= (x << 5) & M32
        self.x = x
        return x

    def reel(self):
        return self.suivant() / 4294967296.0

    def entre(self, a, b):
        return a + (b - a) * self.reel()

    def pondere(self, poids):
        """Choix pondéré ; poids = liste de (clé, poids)."""
        total = sum(w for _, w in poids)
        r = self.reel() * total
        for k, w in poids:
            r -= w
            if r < 0:
                return k
        return poids[-1][0]


def normaliser(texte):
    t = texte.lower().replace('’', "'").replace('‘', "'").replace('“', '"').replace('”', '"')
    t = re.sub(r"[^a-z0-9$' ]+", ' ', t)
    return re.sub(r'\s+', ' ', t).strip()


INTERJECTIONS = [  # (motif regex en début de réplique, vocalise ; None = selon l'émotion)
    (r'(uh+|um+|er+|erm)', 'euh'), (r'(hmm+|hm+)', None), (r'(mm+-?hm+)', 'hmm_accord'),
    (r'(ha(ha)+|heh+|hah)', 'rire'), (r'(ugh+|argh+)', 'grogne'), (r'(wow+|whoa+)', 'ooh'),
    (r'(pfft+|pff+)', 'pfff'), (r'(aw+|aww+)', 'oh_decu'), (r'(huh)', 'hein'), (r'(tsk|tch)', 'tss'),
    (r'(oh+|ah+)', None), (r'(sigh)', 'soupir')]
NOMBRES = re.compile(r"^(\$?\d[\d,.]*\$?|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
                     r"fifteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|"
                     r"dollars?|bucks?|cents?|half)$")


def syllabes_anglais(mot):
    if NOMBRES.match(mot) and re.match(r'\$?\d', mot):
        return max(1, len(re.sub(r'\D', '', mot)))
    m = re.sub(r"[^a-z]", '', mot)
    if not m:
        return 0
    n = len(re.findall(r'[aeiouy]+', m))
    if m.endswith('e') and n > 1 and not m.endswith(('le', 'ee')):
        n -= 1
    return max(1, n)


def interjection(texte, emotion):
    """Repère une interjection en tête (« Uh... », « Hmm. », « Oh! ») -> (vocalise, reste du texte)."""
    t = texte.strip()
    for motif, voc in INTERJECTIONS:
        m = re.match(r'^' + motif + r'\b[\s,.!?…—-]*', t, re.I)
        if m:
            mot = m.group(1).lower()
            if voc is None:
                if mot.startswith('h'):
                    voc = 'hmm_doute' if emotion in ('mefiant', 'decu') else 'hmm_reflexion'
                elif emotion == 'surpris':
                    voc = 'inspiration_surprise'
                elif emotion in ('decu', 'triste'):
                    voc = 'oh_decu'
                else:
                    voc = 'ah'
            return voc, t[m.end():]
    return None, t


def segments(texte):
    """Découpe en groupes de souffle : [(mots, ponctuation finale)]."""
    morceaux = re.findall(r'([^.!?,;:…—]+)([.!?,;:…—]+|$)', texte.replace('...', '…'))
    out = []
    for corps, ponct in morceaux:
        mots = normaliser(corps).split()
        if mots:
            p = ponct.strip()
            fin = '?' if '?' in p else '!' if '!' in p else '…' if '…' in p else '.' if '.' in p or not p else ','
            out.append((mots, fin))
    return out


class Locuteur:
    """État d'un PNJ qui parle : profil, f0 personnel, mémoire anti-répétition."""

    def __init__(self, pid, profil, ident=0, decalage_f0=1.0):
        self.pid, self.p, self.ident = pid, profil, ident
        self.decalage_f0 = decalage_f0       # petite différence entre deux PNJ du même profil
        self.repliques = 0
        self.occurrences = {}                # motif -> nombre de fois dite
        self.dernieres_vocalises = []        # [(type, n° de réplique)]
        self.dernier_variant = {}            # type -> variante jouée la dernière fois


def _ajuster(val, neutre, k):
    return neutre + (val - neutre) * k


def partition(texte, loc: Locuteur, emotion, emotions, durees, intensite=.7, fps=None):
    """Renvoie (événements, infos). Un événement = dict(t, grain, pitch, db).
    durees : {'syllabes': {nom: (duree, attaque)}, 'vocalises': {type: [durees]}}"""
    p = loc.p
    e = emotions[emotion]
    k = .4 + .85 * intensite
    hauteur = _ajuster(e['hauteur'], 1, k)
    etendue = p['etendue'] * _ajuster(e['etendue'], 1, k)
    debit = _ajuster(e['debit'], 1, k)        # le tempo propre du profil est dans ses pauses
    pauses = _ajuster(e['pauses'], 1, k) / debit
    vol = p.get('volume_db', 0) + e['volume_db'] * k
    f0 = p['f0'] * loc.decalage_f0 * hauteur

    voc_tete, reste = interjection(texte, emotion)
    motif = normaliser(texte)
    graine = fnv1a(motif)
    am = Alea(graine)                                        # motif : identique à chaque fois
    occ = loc.occurrences.get(motif, 0)
    loc.occurrences[motif] = occ + 1
    av = Alea(graine ^ fnv1a('%s#%d#%d' % (loc.pid, loc.ident, occ)) ^ (loc.repliques * 2654435761 & M32))

    consonnes = list(p['consonnes'].items())
    voyelles = list(p['voyelles'].items())
    dures = [c for c in p['consonnes'] if c and c in 'ptkbd'] or ['t']

    evts, t = [], 0.0
    infos = {'motif': motif, 'graine': graine, 'occurrence': occ, 'vocalises': [], 'syllabes': 0}

    def recent(typ):
        return any(v == typ and loc.repliques - n <= 2 for v, n in loc.dernieres_vocalises)

    def vocalise(typ, gain_db=0.0):
        nonlocal t
        if typ not in durees['vocalises']:
            return
        var = (loc.dernier_variant.get(typ, -1) + 1) % len(durees['vocalises'][typ])  # alterne les prises
        loc.dernier_variant[typ] = var
        pitch = loc.decalage_f0 * hauteur * av.entre(.97, 1.03)
        evts.append({'t': t, 'grain': 'voc:%s:%d' % (typ, var), 'pitch': pitch, 'db': vol + gain_db - 1})
        t += durees['vocalises'][typ][var] / pitch + av.entre(.08, .16) * pauses
        loc.dernieres_vocalises.append((typ, loc.repliques))
        infos['vocalises'].append(typ)

    def tirer(liste):
        for typ, prob in liste:
            pr = prob * (.5 + intensite * .7) * (.25 if recent(typ) else 1)
            if av.reel() < pr:
                return typ
        return None

    # 1. Avant la phrase : interjection écrite, sinon vocalise d'émotion ou tic du profil.
    avant = voc_tete or tirer(e['avant'])
    if not avant and emotion in ('neutre', 'curieux', 'mefiant', 'fatigue', 'decu', 'agace', 'moqueur'):
        tics = p.get('tics', {})
        avant = tirer([(x, tics[x] * .6) for x in ('soupir', 'hmm', 'pfff') if x in tics])
        avant = {'hmm': 'hmm_reflexion'}.get(avant, avant)
    if avant:
        vocalise(avant)

    # 2. Budget de syllabes : proportionnel à la longueur anglaise, plafonné.
    segs = segments(reste) or ([(['mm'], '.')] if not avant else [])
    eng = [sum(syllabes_anglais(m) for m in mots) for mots, _ in segs]
    budget = [max(1, arrondi(n * p['densite'])) for n in eng]
    total = sum(budget)
    if total > 16:
        budget = [max(1, arrondi(b * 16 / total)) for b in budget]

    fin_emotion = e.get('fin')
    tremble = e.get('tremble', 0) * k
    calme = emotion not in ('furieux', 'agace', 'ravi', 'joyeux', 'surpris')
    hesite = max(e.get('hesite', 0) * k, p.get('tics', {}).get('euh', 0) * (.5 if calme else .1))
    pause_chiffre = p.get('pause_avant_chiffre', 0)

    for si, ((mots, ponct), n) in enumerate(zip(segs, budget)):
        dernier_seg = si == len(segs) - 1
        forme_fin = {'?': 'montee', '!': 'exclamation', '…': 'suspendue', ',': 'continuation'}.get(ponct, 'chute')
        if dernier_seg and fin_emotion and ponct != '?':
            forme_fin = fin_emotion if forme_fin != 'exclamation' or fin_emotion in ('chute', 'chantee') else forme_fin
        # Découpage en « mots » de charabia (1 à 3 syllabes), fixé par le motif.
        nb_mots = max(1, min(n, arrondi(n / 2.2 + am.reel() * .8 - .2)))
        tailles = [1] * nb_mots
        for _ in range(n - nb_mots):
            tailles[int(am.reel() * nb_mots)] += 1
        # Position du premier nombre (silence avant la somme, syllabe appuyée).
        idx_nombre = next((i for i, m in enumerate(mots) if NOMBRES.match(m)), None)
        syl_nombre = None if idx_nombre is None else int(idx_nombre / max(1, len(mots)) * n)
        # Hauteurs cibles.
        cibles = []
        for j in range(n):
            x = j / max(1, n - 1)
            if forme_fin == 'exclamation':
                h = 1.15 - .2 * x
            elif forme_fin == 'montee':
                h = 1 - .06 * x + (.4 * (x - .65) / .35 if x > .65 else 0)
            elif forme_fin in ('suspendue', 'continuation'):
                h = 1.02 - .04 * x
            else:
                h = 1.05 - .16 * x
            if forme_fin == 'chantee' and n > 1 and j == n - 2:
                h += .14
            phase, micro = am.reel(), am.entre(.96, 1.04)   # tirés quelle que soit l'émotion
            if emotion in ('joyeux', 'moqueur', 'ravi'):
                h += .07 * math.sin(j * 1.9 + phase)
            h *= micro                                      # mélodie propre à la réplique
            cibles.append(1 + (h - 1) * etendue)
        j = 0
        for wi, taille in enumerate(tailles):
            for s in range(taille):
                c = am.pondere(consonnes)
                v = am.pondere(voyelles)
                if e['dures'] * k > av.reel():
                    c = dures[int(av.reel() * len(dures))]
                dernier = j == n - 1
                if dernier:
                    forme = {'montee': 'monte_long', 'exclamation': 'descend_long', 'suspendue': 'plat_long',
                             'continuation': 'monte', 'chantee': 'descend_long', 'chute_montee': 'monte_long'
                             }.get(forme_fin, 'descend_long')
                    if forme == 'monte' and debit < .85:
                        forme = 'monte_long'
                else:
                    r = cibles[j + 1] / cibles[j]
                    forme = 'monte' if r > 1.04 else 'descend' if r < .96 else 'plat'
                    if forme_fin == 'chute_montee' and j == n - 2:
                        forme = 'descend'
                    if debit < .85 and s == taille - 1:   # fatigue, tristesse : on traîne en fin de mot
                        forme += '_long'
                nom = '%s%s_%s' % (c or '_', {'é': 'ee'}.get(v, v), forme)
                if nom not in durees['syllabes']:
                    nom = '%s%s_plat' % (c or '_', {'é': 'ee'}.get(v, v))
                dur, attaque = durees['syllabes'][nom]
                accent = p['accent'] if s == 0 else 1.0
                gain = 1.5 if s == 0 else 0.0
                if syl_nombre is not None and j == syl_nombre:
                    if pause_chiffre:
                        t += pause_chiffre * av.entre(.9, 1.1)
                    gain += 2.0
                    accent *= 1.04
                if forme_fin == 'exclamation' and s == 0:
                    gain += 1.5
                pitch = f0 / p['f0'] * cibles[j] * accent * av.entre(.985, 1.015)
                if tremble:
                    pitch *= 1 + tremble * math.sin(t * 31)
                pitch = min(1.9, max(.55, pitch))
                debut = max(0.0, t - attaque / pitch * .5)  # aligne grossièrement l'attaque de voyelle
                evts.append({'t': debut, 'grain': 'syl:' + nom, 'pitch': pitch, 'db': vol + gain})
                t = debut + dur / pitch - .008
                j += 1
                infos['syllabes'] += 1
            if wi < len(tailles) - 1:
                t += av.entre(*p['pause_mot']) * pauses
                if hesite and av.reel() < hesite * .35:
                    vocalise('euh', -3)
        if not dernier_seg:
            t += av.entre(*p['pause_phrase']) * pauses * {'…': 1.6, ',': .55}.get(ponct, 1.0)

    # 3. Après la phrase : rire, reniflement, grognement...
    apres = tirer(e['apres'])
    if apres:
        t += .04
        vocalise(apres)
    loc.repliques += 1
    if fps:  # le lecteur Godot déclenche les grains à l'image près : on simule cette quantification
        pas = 1.0 / fps
        for ev in evts:
            ev['t'] = math.ceil(ev['t'] / pas - 1e-9) * pas
    fin = max((ev['t'] + _duree_grain(ev, durees) for ev in evts), default=0.0)
    infos['duree'] = fin
    return evts, infos


def _duree_grain(ev, durees):
    kind, rest = ev['grain'].split(':', 1)
    if kind == 'syl':
        return durees['syllabes'][rest][0] / ev['pitch']
    typ, var = rest.rsplit(':', 1)
    return durees['vocalises'][typ][int(var)] / ev['pitch']
