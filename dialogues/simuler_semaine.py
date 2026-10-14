"""Simule la semaine de démo (7 jours) pour trois profils de joueur et mesure le dosage de l'humour.

python3 dialogues/simuler_semaine.py  -> donnees/simulation_semaine.json + docs/exemples_conversations.md
"""
import collections, json, os, random, sys

ICI = os.path.dirname(os.path.abspath(__file__))
RACINE = os.path.join(ICI, '..')
sys.path.insert(0, ICI)
from moteur import Moteur

JOURS, PAR_JOUR = 7, 14


def simuler(persona, graine=7):
    mo = Moteur(graine=graine)
    rng = random.Random(graine * 31)
    ids = list(mo.habitants)
    # Les voisins, le café et les vendeurs se croisent plus souvent que les visiteurs.
    poids = [2.0 if mo.habitants[i]['famille'] in ('cafe', 'brocante', 'cartes') else
             .6 if mo.habitants[i]['famille'] == 'visiteurs' else 1.0 for i in ids]
    marchands = [i for i in ids if mo.habitants[i]['famille'] in ('cartes', 'brocante')]
    journal = []
    for jour in range(JOURS):
        mo.jour = jour
        for k in range(PAR_JOUR):
            tendu = k == PAR_JOUR - 1
            pid = rng.choice(marchands) if tendu else rng.choices(ids, weights=poids)[0]
            t = mo.rencontre(pid, persona, tendu=tendu)
            journal.append({'jour': jour, 'habitant': mo.habitants[pid]['nom'], 'tendu': tendu, 'echanges': t})
    st = mo.stats
    n = st['rencontres']
    par_jour = collections.Counter(e['jour'] for e in journal for x in e['echanges'] if x['tag'].startswith(('scene_pop', 'gag', 'clin')))
    tendus_drole = sum(1 for e in journal if e['tendu'] for x in e['echanges'] if x['tag'].startswith(('clin', 'scene_pop')))
    resume = {
        'persona': persona, 'rencontres': n,
        'part_rencontres_avec_humour': round(st['rencontres_avec_humour'] / n, 3),
        'elements_humour_par_rencontre': round(st['elements_humour'] / n, 2),
        'humour_par_jour': [par_jour[j] for j in range(JOURS)],
        'scenes_pop': st['ref_scene'], 'clins_doeil': st['ref_clin'], 'etapes_running_gags': st['ref_gag'],
        'domaines': {k[4:]: v for k, v in st.items() if k.startswith('dom_')},
        'reactions': {k[9:]: v for k, v in st.items() if k.startswith('reaction_')},
        'redites_entendues': st['redites_entendues'],
        'repliques_pnj': sum(1 for e in journal for x in e['echanges'] if x['qui'] != 'You'),
        'humour_en_negociation_tendue': tendus_drole,
    }
    return resume, journal


def extrait_md(journal, titre, n=8):
    lignes = ['## ' + titre, '']
    pris = 0
    for e in journal:
        if not any(x['tag'].startswith(('scene_pop', 'gag', 'clin', 'reaction')) for x in e['echanges']):
            continue
        lignes.append('**Jour %d — %s**%s' % (e['jour'] + 1, e['habitant'], ' (négociation tendue)' if e['tendu'] else ''))
        lignes.append('')
        for x in e['echanges']:
            marque = {'scene_pop': ' 🎮', 'gag': ' 🔁', 'clin': ' 😉', 'reaction': ' 😄'}.get(x['tag'].split(':')[0], '')
            lignes.append('- *%s* : %s%s' % (x['qui'], x['texte'], marque))
        lignes.append('')
        pris += 1
        if pris >= n:
            break
    return lignes


if __name__ == '__main__':
    resultats, md = {}, ['# Exemples de conversations simulées (V9)', '',
                         'Légende : 🎮 scène pop culture, 😉 clin d’œil pop culture, 🔁 running gag du village, 😄 réaction à une blague du joueur.', '']
    for persona in ('blagueur', 'neutre', 'serieux'):
        r, j = simuler(persona)
        # moyenne sur 5 graines pour ne pas dépendre d'un tirage chanceux
        series = [simuler(persona, graine=g)[0] for g in (7, 11, 23, 42, 99)]
        for cle in ('part_rencontres_avec_humour', 'elements_humour_par_rencontre', 'redites_entendues', 'repliques_pnj',
                    'humour_en_negociation_tendue', 'scenes_pop', 'clins_doeil', 'etapes_running_gags'):
            r[cle + '_moy5'] = round(sum(x[cle] for x in series) / 5, 3)
        r['max_negociation_tendue_sur_5'] = max(x['humour_en_negociation_tendue'] for x in series)
        resultats[persona] = r
        md += extrait_md(j, 'Joueur %s' % persona, 8 if persona == 'blagueur' else 4)
        print(json.dumps(r, ensure_ascii=False))
    json.dump(resultats, open(os.path.join(RACINE, 'donnees', 'simulation_semaine.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    os.makedirs(os.path.join(RACINE, 'docs'), exist_ok=True)
    open(os.path.join(RACINE, 'docs', 'exemples_conversations.md'), 'w', encoding='utf-8').write('\n'.join(md))
