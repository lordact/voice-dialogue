"""Construit donnees/dialogues_v9.json à partir de la V8 (jamais modifiée) et de donnees/ecriture/.

python3 dialogues/construire_v9.py   -> écrit la V9 et donnees/rapport_v9.json

Ce que fait la V9 :
  - corrige les fautes des arbres V1 (majuscule après un point, articles manquants) ;
  - remplace les redites des arbres V1 (refus identique x800, réponse qui répète la ligne précédente x640) ;
  - crée les 6 raccords appelés mais absents, et varie l'ouverture des raccords existants ;
  - rattache chaque scène à de vrais habitants (la boulangerie devient la cuisine du café) ;
  - corrige la quasi-citation pop culture repérée ;
  - ajoute les réponses variées aux relances génériques, l'humour pop culture et les running gags.
"""
import collections, json, os, re, sys, zlib

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.join(ICI, '..')
sys.path.insert(0, ICI)
from distribution import distribution

SUJETS = {'dragon-set holdings': 'your dragon-set holdings', 'new reselling business': 'your new reselling business',
          'weekly resale plan': 'your weekly resale plan', 'condition under a proper light': 'the condition under a proper light'}
SUJETS_THE = ['dusty foil card', 'family binder', 'listed holo card', 'old collection', 'old shoebox of cards',
              'small stack of cleaned cards', 'trunk lot']


def lire(chemin):
    return json.load(open(os.path.join(RACINE, chemin), encoding='utf-8'))


def choix_stable(cle, liste):
    return liste[zlib.crc32(cle.encode()) % len(liste)]


def corriger_phrase(t):
    t = re.sub(r'([.!?] )([a-z])', lambda m: m.group(1) + m.group(2).upper(), t)
    for s in SUJETS_THE:
        t = re.sub(r'\b(more about|boundary on) ' + re.escape(s) + r'\b', r'\1 the ' + s, t)
    for s, r in SUJETS.items():
        t = re.sub(r'\b(more about|boundary on|know about) ' + re.escape(s) + r'\b', r'\1 ' + r, t)
    return t


FAMILLE_DU_JOUEUR = [1, 2, 3, 4, 93, 94]   # parents, grands-parents, tante, cousin (histoires « Our … »)


def habitants_v2(categorie, dist):
    """Qui peut jouer une scène V2 selon son thème (et non n'importe quel habitant)."""
    hs = dist['habitants'].values()
    if categorie == 'Family and Home':
        return FAMILLE_DU_JOUEUR
    if categorie == 'Jobs and Daily Work':
        return [h['id'] for h in hs if 20 <= h['age'] < 66 and h['famille'] in ('cafe', 'commerce', 'services_publics', 'secours', 'techniques')]
    if categorie == 'Friendship and Feelings':
        return [h['id'] for h in hs if 15 <= h['age'] < 35]
    if categorie in ('Pets and Wildlife', 'Curious and Silly Encounters', 'Public Spaces and Recreation'):
        return [h['id'] for h in hs if h['age'] >= 8]
    return [h['id'] for h in hs if h['age'] >= 15]


def construire():
    v8 = lire('donnees/CARD_HUSTLE_DIALOGUES_CONSOLIDES_V8.json')
    rel = lire('donnees/ecriture/relances.json')
    hum = lire('donnees/ecriture/humour_pop.json')
    rac = lire('donnees/ecriture/raccords_et_arbres.json')
    dist = distribution()
    v9 = json.loads(json.dumps(v8))
    rapport = collections.Counter()

    # 1. Arbres V1 : fautes et redites.
    refus = rac['arbres_v1']['refus_par_interlocuteur']
    modeles = rac['arbres_v1']['reformulations_honnetes']['modeles']
    for nid, n in v9['deep_trees']['V1']['nodes'].items():
        avant = n['npc_line']
        n['npc_line'] = corriger_phrase(avant)
        if n['npc_line'] == 'Understood. Thanks for being decent about it.':
            n['npc_line'] = choix_stable(nid, refus.get(n['speaker'], refus['Neighbor']))
            rapport['arbres_refus_varies'] += 1
        rapport['arbres_fautes_corrigees'] += avant != n['npc_line']
        for i, c in enumerate(n['choices']):
            t = corriger_phrase(c['text'])
            rapport['arbres_fautes_corrigees'] += t != c['text']
            c['text'] = t
            if 'npc_reply' not in c:
                continue
            r = corriger_phrase(c['npc_reply'])
            if r == 'Understood. Thanks for being decent about it.':
                pool = refus.get(n['speaker'], refus['Neighbor'])
                r = choix_stable(nid + str(i), pool)
                if r == n['npc_line']:   # jamais la même phrase que celle qu'on vient d'entendre
                    r = pool[(pool.index(r) + 1) % len(pool)]
                rapport['arbres_refus_varies'] += 1
            elif r == n['npc_line']:
                cle = nid + str(i)
                m1 = re.match(r'All right\. Here is the honest part: (.+?)\. Anything beyond that needs checking\.', r)
                m2 = re.match(r'Potentially\. (.+?)\. We can talk after the facts are clear\.', r)
                m3 = re.match(r'(.+?)\. That is why I care about this\.', r)
                if m1:
                    r = choix_stable(cle, modeles).replace('{fait}', m1.group(1))
                elif m2:
                    cond = m2.group(1)
                    r = choix_stable(cle, rac['arbres_v1']['reformulations_conditions']['modeles']).replace('{condition}', cond[0].lower() + cond[1:] if not cond.startswith('I ') else cond)
                elif m3:
                    mot = m3.group(1)
                    mot_min = mot if mot.startswith('I ') else mot[0].lower() + mot[1:]
                    r = choix_stable(cle, rac['arbres_v1']['reformulations_motifs']['modeles']).replace('{motif}', mot).replace('{motif_min}', mot_min)
                if r != n['npc_line']:
                    r = r[0].upper() + r[1:]
                    rapport['arbres_redites_reformulees'] += 1
            c['npc_reply'] = r

    # 2. Raccords manquants + variantes d'ouverture.
    for k, h in rac['raccords'].items():
        v9['conditional_hubs'][k] = {'npc': h['npc_variantes'][0], 'npc_variantes': h['npc_variantes'], 'choices': h['choices']}
        rapport['raccords_ajoutes'] += 1
    var_rep = rac.get('variantes_reponses_raccords', {})
    for h in v9['conditional_hubs'].values():
        for c in h['choices']:
            if c['player'] in var_rep:
                c['npc_variantes'] = var_rep[c['player']]
    for k, vs in rac['variantes_ouverture_raccords'].items():
        if k in v9['conditional_hubs']:
            v9['conditional_hubs'][k]['npc_variantes'] = vs

    # 3. Scènes : habitants réels, boulangerie -> café, citation corrigée.
    remplacements = hum['audit_existant']['remplacements']
    for s in v9['scenes']:
        role = s['role_normalized']
        if role == 'baker':
            s['role_village'] = 'cafe_cook'
            rapport['scenes_boulanger_vers_cafe'] += 1
        for c in [s] + s['choices']:
            for cle in ('opening', 'player', 'npc'):
                if c.get(cle):
                    t = c[cle].replace('the bakery', 'the café').replace('bakery', 'café')
                    for a, b in remplacements.items():
                        if a in t:
                            t = t.replace(a, b)
                            rapport['citations_corrigees'] += 1
                    rapport['lieux_corriges'] += t != c[cle] and 'bakery' in c[cle]
                    c[cle] = t
            for f in c.get('followups', []) if c is not s else []:
                for cle in ('player', 'npc'):
                    if f.get(cle) and 'bakery' in f[cle]:
                        f[cle] = f[cle].replace('the bakery', 'the café').replace('bakery', 'café')
                        rapport['lieux_corriges'] += 1
        s['habitants'] = dist['roles'].get(role, dist['roles']['ambient_resident']) if role in dist['roles'] else \
            dist['roles']['ambient_resident']
        if s['source'] == 'V2':   # les scènes V2 « ambiance » visent des publics précis selon leur thème
            s['habitants'] = habitants_v2(s['additional']['category'], dist)
        s['disponible'] = bool(s['habitants'])
        rapport['scenes_jouables'] += s['disponible']
        s['humour_pop'] = bool(s.get('additional', {}).get('reference_inspiration'))

    # 4. Nouvelles couches : relances variées, humour, distribution.
    v9['relances'] = rel
    v9['humour'] = hum
    v9['distribution'] = dist
    v9['metadata'] = dict(v8['metadata'], title='Card Hustle — Dialogue Library V9 (cleaned, cast, with humour layer)',
                          derived_from='CARD_HUSTLE_DIALOGUES_CONSOLIDES_V8.json (unchanged)')

    # 5. Mesures avant / après.
    def uniques(d):
        lignes = set()
        for s in d['scenes']:
            lignes.add(s['opening'])
            for c in s['choices']:
                lignes.add(c.get('npc') or '')
                for f in c.get('followups', []):
                    lignes.add(f.get('npc') or '')
        for n in d['deep_trees']['V1']['nodes'].values():
            lignes.add(n['npc_line'])
            for c in n['choices']:
                lignes.add(c.get('npc_reply', ''))
        for h in d['conditional_hubs'].values():
            lignes.update(h.get('npc_variantes', [h['npc']]))
            for c in h['choices']:
                lignes.add(c['npc'])
        lignes.discard('')
        return lignes
    nouvelles = set()
    for f, ls in rel['commun'].items():
        nouvelles.update(ls)
    for fam in rel['familles'].values():
        for ls in fam.values():
            nouvelles.update(ls)
    nouvelles.update(q['texte'] for q in hum['repliques'])
    for g in hum['running_gags']:
        nouvelles.update(e['texte'] for e in g['etapes'])
    for st in hum['receptions'].values():
        if isinstance(st, dict):
            for ls in st.values():
                nouvelles.update(ls)
    rapport['repliques_pnj_uniques_v8'] = len(uniques(v8))
    rapport['repliques_pnj_uniques_v9'] = len(uniques(v9) | nouvelles)
    rapport['repliques_humour_pop_nouvelles'] = len(hum['repliques'])
    rapport['running_gags'] = len(hum['running_gags'])
    rapport['etapes_running_gags'] = sum(len(g['etapes']) for g in hum['running_gags'])
    hubs_ref = set()
    for s in v9['scenes']:
        hubs_ref.update(s.get('rejoin_options', []))
        for c in s['choices']:
            if c.get('suggested_next_hub'):
                hubs_ref.add(c['suggested_next_hub'])
            for f in c.get('followups', []):
                if str(f.get('outcome', '')).startswith('hub:'):
                    hubs_ref.add(f['outcome'][4:])
    rapport['raccords_manquants_restants'] = len(hubs_ref - set(v9['conditional_hubs']))
    sans = collections.Counter(s['role_normalized'] for s in v9['scenes'] if not s['disponible'])
    rapport_d = dict(rapport)
    rapport_d['scenes_sans_habitant'] = dict(sans)
    return v9, rapport_d


if __name__ == '__main__':
    v9, rapport = construire()
    json.dump(v9, open(os.path.join(RACINE, 'donnees', 'dialogues_v9.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    json.dump(rapport, open(os.path.join(RACINE, 'donnees', 'rapport_v9.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    for k, v in rapport.items():
        print('%-34s %s' % (k, v))
