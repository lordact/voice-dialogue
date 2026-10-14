"""Tests de la bibliothèque V9 et du directeur d'humour (python3 tests/test_dialogues.py)."""
import collections, json, os, re, sys

RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.join(RACINE, 'dialogues'))
from construire_v9 import construire
from moteur import Moteur
import simuler_semaine

echecs, controles = [], 0


def verifier(ok, quoi):
    global controles
    controles += 1
    if not ok:
        echecs.append(quoi)
        print('ÉCHEC :', quoi)


v9, rapport = construire()
habitants = {int(k) for k in v9['distribution']['habitants']}

# --- Intégrité ------------------------------------------------------------------------------
N = v9['deep_trees']['V1']['nodes']
verifier(all(c['next'] in N for n in N.values() for c in n['choices'] if 'next' in c), 'arbres V1 : tous les liens existent')
verifier(sum(1 for n in N.values() for c in n['choices'] if c.get('npc_reply') == n['npc_line']) == 0, 'arbres V1 : aucune réponse ne répète la ligne précédente')
verifier(not any(re.search(r'[.!?] [a-z]', n['npc_line']) for n in N.values()), 'arbres V1 : majuscule après un point')
verifier(not any(re.search(r'(more about|boundary on) (trunk lot|family binder|old collection)', c['text']) for n in N.values() for c in n['choices']),
         'arbres V1 : articles corrigés')
verifier(rapport['raccords_manquants_restants'] == 0, 'aucun raccord appelé sans exister')
verifier(all(set(s['habitants']) <= habitants for s in v9['scenes']), 'toutes les scènes renvoient à de vrais habitants')
verifier(rapport['scenes_jouables'] >= 453, 'au moins 453 scènes jouables (%d)' % rapport['scenes_jouables'])
famille = {s['id']: s for s in v9['scenes'] if s['source'] == 'V2' and s['additional']['category'] == 'Family and Home'}
verifier(all(set(s['habitants']) <= {1, 2, 3, 4, 93, 94} for s in famille.values()), 'scènes de famille : seulement la famille du joueur')

# --- Humour : écriture -----------------------------------------------------------------------
hum = v9['humour']
textes = [q['texte'] for q in hum['repliques']] + [e['texte'] for g in hum['running_gags'] for e in g['etapes']]
INTERDITS = re.compile(r"\b(pikachu|pok[eé]mon|mario|zelda|minecraft|skyrim|sims|fortnite|star wars|jedi|hogwarts|gandalf|frodo|"
                       r"cake is a lie|cake was a lie|dangerous to go alone|one does not simply|never gonna give|i'll be back|"
                       r"winter is coming|may the force|we were on a break|shall not pass)\b", re.I)
verifier(not any(INTERDITS.search(t) for t in textes), 'humour : aucune marque ni réplique culte citée mot pour mot')
scenes_txt = [s['opening'] for s in v9['scenes']] + [c['player'] + ' ' + (c.get('npc') or '') for s in v9['scenes'] for c in s['choices']]
verifier(not any(re.search(r'cake (was|is) a lie', t, re.I) for t in scenes_txt), 'quasi-citation de la V8 corrigée')
verifier(all(e.get('qui') for g in hum['running_gags'] for e in g['etapes']), 'chaque étape de running gag a son orateur')
verifier(len(set(textes)) == len(textes), 'pas de doublon dans les répliques humoristiques')

# --- Directeur d'humour : simulation de la semaine --------------------------------------------
res = {}
for persona in ('blagueur', 'neutre', 'serieux'):
    series = [simuler_semaine.simuler(persona, graine=g) for g in (3, 5, 8)]
    res[persona] = sum(r['part_rencontres_avec_humour'] for r, _ in series) / 3
    verifier(all(r['humour_en_negociation_tendue'] == 0 for r, _ in series), '%s : jamais d’humour en négociation tendue' % persona)
    verifier(all(r['redites_entendues'] / r['repliques_pnj'] < .02 for r, _ in series), '%s : moins de 2 %% de redites entendues' % persona)
    for r, journal in series:
        for e in journal:
            for x in e['echanges']:
                if x['tag'].startswith('gag:'):
                    gid, etape = x['tag'].split(':')[1], int(x['tag'].split(':')[2])
                    g = next(g for g in hum['running_gags'] if g['id'] == gid)
                    attendu = v9['distribution']['habitants'][str(g['etapes'][etape]['qui'])]['nom']
                    verifier(x['qui'] == attendu, 'gag %s dit par %s et non %s' % (gid, attendu, x['qui']))
        par_renc = collections.Counter()
        for e in journal:
            par_renc[id(e)] = sum(1 for x in e['echanges'] if x['tag'].startswith(('scene_pop', 'gag', 'clin')))
        verifier(max(par_renc.values()) <= 2, '%s : au plus 2 éléments d’humour par rencontre' % persona)
verifier(res['blagueur'] > res['neutre'] > res['serieux'], 'réciprocité : plus le joueur plaisante, plus on plaisante (%s)' %
         {k: round(v, 2) for k, v in res.items()})
verifier(.3 <= res['blagueur'] <= .6 and res['serieux'] <= .25, 'dosage : blagueur 30-60 %, sérieux ≤ 25 %')

print('%d contrôles, %d échecs' % (controles, len(echecs)))
sys.exit(1 if echecs else 0)
