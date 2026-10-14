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
    """Découpe en groupes de souffle : [(mots, ponctuation finale)] (mots normalisés)."""
    return [([m for _, m in mots], fin) for mots, fin in segments_mots(texte)]


def segments_mots(texte):
    """Comme segments(), mais garde pour chaque mot son rang dans le texte (mots séparés par des
    espaces) : [([(rang, mot normalisé), ...], ponctuation finale)]. Le rang sert à afficher le
    sous-titre mot à mot, en même temps que la voix."""
    jetons = texte.replace('...', '…').split()
    out, cour = [], []
    for i, jeton in enumerate(jetons):
        mot = normaliser(jeton).replace(' ', '')
        if mot:
            cour.append((i, mot))
        m = re.search(r'[.!?,;:…—]+$', jeton)
        if m or i == len(jetons) - 1:
            p = m.group(0) if m else ''
            if cour:
                fin = '?' if '?' in p else '!' if '!' in p else '…' if '…' in p else '.' if '.' in p or not p else ','
                out.append((cour, fin))
            cour = []
    return out


# Petits mots anglais qui, dans la voix, deviennent des syllabes-outils rapides et inaccentuées.
MOTS_OUTILS = {'a', 'an', 'the', 'to', 'of', 'in', 'on', 'at', 'it', 'i', 'you', 'is', 'and', 'or', 'but', 'my',
               'your', 'me', 'we', 'he', 'she', 'they', 'be', 'for', 'that', 'this', 'so', 'do', 'if', 'as', 'by',
               'with', 'was', 'are', 'am', 'can', 'its', "it's", "i'm", 'his', 'her', 'our', 'them', 'him', 'us',
               'from', 'just', 'some', 'what', 'there', 'than', 'then', 'not', 'no', 'up', 'out', 'all', 'got',
               'get', 'one', 'have', 'has', 'had', 'will', "don't", "i'll", "you're", "that's"}


def moyennes(durees):
    """Durée moyenne d'une syllabe de chaque forme (court, plat, long) dans la banque ; mise en cache."""
    if '_moyennes' not in durees:
        somme, nb = {'court': 0.0, 'plat': 0.0, 'long': 0.0}, {'court': 0, 'plat': 0, 'long': 0}
        for nom, da in durees['syllabes'].items():
            forme = nom.rsplit('_', 1)[1]
            if forme in somme:
                somme[forme] += da[0]
                nb[forme] += 1
        durees['_moyennes'] = {f: somme[f] / max(1, nb[f]) for f in somme}
    return durees['_moyennes']


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

    inv = durees['inventaire']                      # [[nom, poids, particule, attaque dure], ...]
    pleines = [(x[0], x[1]) for x in inv if not x[2]]
    particules = [(x[0], x[1]) for x in inv if x[2]] or pleines
    syl_dures = [x[0] for x in inv if x[3]] or [pleines[0][0]]

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
        evts.append({'t': t, 'grain': 'voc:%s:%d' % (typ, var), 'pitch': pitch, 'pitch_fin': pitch, 'db': vol + gain_db - 1})
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

    # 2. Rythme calé sur le sous-titre anglais.
    #    Chaque mot anglais devient un mot de charabia d'à peu près autant de syllabes ; les petits
    #    mots (the, to, it…) deviennent des syllabes-outils ; les pauses tombent sur la ponctuation.
    #    La durée visée est le temps de lecture du sous-titre : on lit en même temps qu'il parle.
    decalage = len(texte.replace('...', '…').split()) - len(reste.replace('...', '…').split())
    segs = segments_mots(reste) or ([([(-1, 'mm')], '.')] if not avant else [])
    lecture = len(reste.strip()) / (p.get('lecture', 15.0) * debit)
    lecture = min(9.0, max(.45, lecture))
    infos['lecture'] = lecture
    infos['mots'] = [[i, 0.0] for i in range(decalage)]       # l'interjection est dite tout de suite
    moy = moyennes(durees)
    legato = p.get('legato', .035)
    estimation, eng_total = 0.0, 0
    plans = []
    for mots, ponct in segs:
        pm = []
        for gi, mot in mots:
            outil = mot in MOTS_OUTILS
            n_w = 1 if outil else min(4, max(1, syllabes_anglais(mot)))
            pm.append([gi, mot, outil, n_w])
            estimation += (moy['court'] - legato) if outil else (moy['plat'] + (n_w - 1) * moy['court'] - n_w * legato)
        plans.append((pm, ponct))
    estimation /= 1.1   # la mélodie, en moyenne un peu au-dessus de la voix de base, raccourcit les grains
    estimation += (len(segs) - 1) * sum(p['pause_phrase']) / 2
    # Nombre de syllabes fixé au tempo neutre : l'émotion ne change pas la « signature » de la phrase,
    # seulement la durée de ses syllabes et de ses silences (calage plus bas).
    lecture_neutre = min(9.0, max(.45, len(reste.strip()) / p.get('lecture', 15.0)))
    rapport = lecture_neutre / max(.05, estimation)
    if rapport < .85 or rapport > 1.15:                 # trop long ou trop court : on ajuste le nombre de syllabes
        for pm, _ in plans:
            for w in pm:
                if not w[2]:
                    w[3] = max(1, min(5, arrondi(w[3] * (max(rapport, .5) if rapport < .85 else min(rapport, 1.6)))))

    fin_emotion = e.get('fin')
    tremble = e.get('tremble', 0) * k
    calme = emotion not in ('furieux', 'agace', 'ravi', 'joyeux', 'surpris')
    hesite = max(e.get('hesite', 0) * k, p.get('tics', {}).get('euh', 0) * (.5 if calme else .1))
    pause_chiffre = p.get('pause_avant_chiffre', 0)
    musical = p.get('musical', .5)
    amplitude = 4.0 * etendue                         # hauteur de l'arc mélodique, en demi-tons
    sauts_fin = {'chute': -3.0, 'montee': 6.0, 'exclamation': -3.5, 'suspendue': 0.0,
                 'continuation': 2.0, 'chantee': -2.5, 'chute_montee': 3.0}

    # 2a. Plan : syllabes, accents, mélodie, silences (sans les instants).
    items = []
    for si, (pm, ponct) in enumerate(plans):
        dernier_seg = si == len(plans) - 1
        forme_fin = {'?': 'montee', '!': 'exclamation', '…': 'suspendue', ',': 'continuation'}.get(ponct, 'chute')
        if dernier_seg and fin_emotion and ponct != '?':
            forme_fin = fin_emotion if forme_fin != 'exclamation' or fin_emotion in ('chute', 'chantee') else forme_fin
        accents, outils, mot_de, premier, taille_de, chiffre = [], [], [], [], [], []
        for w in pm:
            place = 0 if am.reel() < .7 else 1
            for s_ in range(w[3]):
                accents.append(not w[2] and s_ == min(place, w[3] - 1))
                outils.append(w[2])
                mot_de.append(w[0])
                premier.append(s_ == 0)
                taille_de.append(w[3])
                chiffre.append(s_ == 0 and NOMBRES.match(w[1]) is not None)
        n = len(accents)
        syl_nombre = next((j for j in range(n) if chiffre[j]), None)
        # Mélodie en demi-tons : déclinaison, arc vers un sommet, accents, gamme pentatonique.
        sommet = am.entre(.2, .6)
        cibles = []
        for j in range(n):
            x = j / max(1, n - 1)
            phase, micro = am.reel(), am.entre(-1, 1)        # tirés quelle que soit l'émotion
            st = 1.0 - 1.8 * x + math.exp(-((x - sommet) / .3) ** 2) * 1.0
            if accents[j]:
                st += .45
            if forme_fin == 'exclamation':
                st += .9 * (1 - x)
            if forme_fin == 'chantee' and n > 1 and j == n - 2:
                st += .8
            if emotion in ('joyeux', 'moqueur', 'ravi'):
                st += .35 * math.sin(j * 1.9 + phase)
            st = st * amplitude + micro * .8
            cibles.append(st * (1 - musical) + pentatonique(st) * musical)
        for j in range(n):
            nom_syl = am.pondere(particules if outils[j] else pleines)
            if e['dures'] * k > av.reel():          # colère : attaques plus dures
                nom_syl = syl_dures[int(av.reel() * len(syl_dures))]
            fin_mot = j == n - 1 or premier[j + 1]
            debut_st = cibles[j]
            if j == n - 1:
                forme = 'long'
                fin_st = debut_st + sauts_fin.get(forme_fin, -3.0) * min(1.5, etendue)
                if forme_fin == 'chute_montee':
                    debut_st -= 2.0
            else:
                forme = 'plat' if accents[j] else 'court'
                if debit < .85 and fin_mot and not outils[j]:   # fatigue : on traîne en fin de mot
                    forme = 'long'
                fin_st = debut_st + .65 * (cibles[j + 1] - debut_st)   # glisse vers la syllabe suivante
            gain = 1.5 if accents[j] else 0.0
            nombre = syl_nombre is not None and j == syl_nombre
            if nombre:
                gain += 2.0
                debut_st += 1.0
            if forme_fin == 'exclamation' and accents[j]:
                gain += 1.5
            base = f0 / p['f0'] * av.entre(.99, 1.01)
            pitch = min(1.8, max(.75, base * 2 ** (debut_st / 12)))
            pitch_fin = min(1.8, max(.75, base * 2 ** (fin_st / 12)))
            it = {'nom': nom_syl, 'forme': forme, 'pitch': pitch, 'pitch_fin': pitch_fin, 'gain': gain,
                  'accent': accents[j], 'mot': mot_de[j], 'premier': premier[j], 'nombre': nombre,
                  'pause': 0.0, 'hesite': False, 'mots_syl': taille_de[j], 'fin_mot': fin_mot}
            if fin_mot and j < n - 1:
                it['pause'] = av.entre(*p['pause_mot']) * pauses
                it['hesite'] = bool(hesite) and av.reel() < hesite * .35
            if j == n - 1 and not dernier_seg:
                it['pause'] = av.entre(*p['pause_phrase']) * pauses * {'…': 1.6, ',': .55}.get(ponct, 1.0)
                it['fin_seg'] = True
            items.append(it)

    # 2b. Calage sur le temps de lecture : on allonge des syllabes accentuées et les silences si la
    #     voix finirait trop tôt, on resserre les silences si elle finirait trop tard.
    def duree_item(it, forme):
        return duree_glissee(durees['syllabes'][it['nom'] + '_' + forme][0], it['pitch'], it['pitch_fin']) - legato

    euh = durees['vocalises']['euh'][0] / hauteur + .12 * pauses if 'euh' in durees['vocalises'] else 0.0
    naturel = t + sum(duree_item(it, it['forme']) + it['pause'] + (euh if it['hesite'] else 0.0)
                      + (pause_chiffre if it['nombre'] else 0.0) for it in items)
    marge = lecture - naturel
    infos['marge_initiale'] = marge
    if marge > 0:
        candidats = sorted([i for i, it in enumerate(items) if it['accent'] and it['forme'] == 'plat'],
                           key=lambda i: (-items[i]['mots_syl'], i))
        for i in candidats:
            gain_t = duree_item(items[i], 'long') - duree_item(items[i], 'plat')
            if marge < gain_t * .5:
                break
            items[i]['forme'] = 'long'
            marge -= gain_t
        mots_trous = [it for it in items[:-1] if it['fin_mot'] and not it.get('fin_seg')]
        seg_trous = [it for it in items[:-1] if it.get('fin_seg')]
        if marge > 0 and mots_trous:
            ajout = min(.1, marge * .6 / len(mots_trous))
            for it in mots_trous:
                it['pause'] += ajout
            marge -= ajout * len(mots_trous)
        if marge > 0 and seg_trous:
            ajout = min(.45, marge / len(seg_trous))
            for it in seg_trous:
                it['pause'] += ajout
    elif marge < 0:
        for it in items:
            if it.get('fin_seg'):
                it['pause'] *= .6
            else:
                it['pause'] *= .2

    # 2c. Réalisation : instants, événements, début de chaque mot (pour le sous-titre mot à mot).
    for it in items:
        if it['nombre'] and pause_chiffre:
            t += pause_chiffre
        nom = it['nom'] + '_' + it['forme']
        dur, attaque = durees['syllabes'][nom]
        pitch, pitch_fin = it['pitch'], it['pitch_fin']
        if tremble:
            pitch = min(1.8, max(.75, pitch * (1 + tremble * math.sin(t * 31))))
        debut = max(0.0, t - attaque / pitch * .5)  # aligne grossièrement l'attaque de voyelle
        if it['premier'] and it['mot'] >= 0:
            infos['mots'].append([decalage + it['mot'], debut])
        evts.append({'t': debut, 'grain': 'syl:' + nom, 'pitch': pitch, 'pitch_fin': pitch_fin, 'db': vol + it['gain']})
        t = debut + duree_glissee(dur, pitch, pitch_fin) - legato
        infos['syllabes'] += 1
        t += it['pause']
        if it['hesite']:
            vocalise('euh', -3)

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


def duree_glissee(longueur, p0, p1):
    """Durée réelle d'un grain de `longueur` s lu avec une hauteur qui glisse de p0 à p1
    (la vitesse de lecture suit la position dans le grain : dp/dt = p0 + (p1-p0)·pos/L)."""
    if abs(p1 - p0) < 1e-9:
        return longueur / p0
    return longueur * math.log(p1 / p0) / (p1 - p0)


def pentatonique(st):
    """Demi-ton le plus proche de la gamme pentatonique majeure (0 2 4 7 9) autour de la base."""
    octave = math.floor(st / 12)
    reste = st - octave * 12
    meilleur = min((0, 2, 4, 7, 9, 12), key=lambda d: abs(reste - d))
    return octave * 12 + meilleur


def _duree_grain(ev, durees):
    kind, rest = ev['grain'].split(':', 1)
    if kind == 'syl':
        return duree_glissee(durees['syllabes'][rest][0], ev['pitch'], ev['pitch_fin'])
    typ, var = rest.rsplit(':', 1)
    return durees['vocalises'][typ][int(var)] / ev['pitch']
