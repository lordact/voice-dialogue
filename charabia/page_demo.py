"""Assemble demo/index.html (page d'écoute A/B) à partir de demo/scenes.json.
python3 charabia/page_demo.py"""
import json, os, sys
ICI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ICI)
RACINE = os.path.join(ICI, '..')
from demo import DISTRIBUTION

scenes = json.load(open(os.path.join(RACINE, 'demo', 'scenes.json'), encoding='utf-8'))
v1 = {s['cle']: s['titres'] for s in json.load(open(os.path.join(RACINE, 'demo', 'scenes_v2.json'), encoding='utf-8'))}
for s in scenes:
    s['nouveau'], s['ancien'] = s['cle'] + '_nouveau.mp3', s['cle'] + '_ancien.mp3'
    if s['cle'] in v1:
        s['v1'], s['titres_v1'] = s['cle'] + '_v2.mp3', v1[s['cle']]   # version précédente (v2.1 mélodieuse)
profils = json.load(open(os.path.join(RACINE, 'donnees', 'profils_voix.json'), encoding='utf-8'))['profils']
habitants = {}
for nom, ident, pid in DISTRIBUTION.values():
    habitants.setdefault(pid, []).append(nom)
donnees = {
    'scenes': scenes,
    'godot': {'cle': 'godot', 'titre': 'Godot capture — 12 voices, then Derek', 'description': '', 'duree': 17.6,
              'nouveau': 'godot_reel_12voix_puis_dialogue.mp3', 'ancien': None, 'titres': []},
    'profils': [[pid, p['description_fr'], '%d Hz' % p['f0'], ', '.join(habitants.get(pid, ['—']))] for pid, p in profils.items()],
    'audit': [
        ['Scènes et arbres profonds', '455 + 850', 'V1 10 · V2 120 · V3 120 · V4 20 · V5 66 · V6 119. Aucun lien cassé.'],
        ['Répliques PNJ des scènes', '6 295 / 2 052 uniques', '« Probably for the best. » 240×, « You too. » 240×, « See you around. » 140× : il faut une mémoire anti-redite.'],
        ['Relances V2 et choix V3', '16 relances × 120', 'Les 120 scènes V2 partagent les mêmes 16 relances ; les 120 scènes V3 les mêmes 3 choix génériques.'],
        ['Arbres V1 (négociation)', '3 410 / 94 uniques', '« Understood. Thanks for being decent about it. » 800×.'],
        ['Réponse = réplique déjà entendue', '640', 'Au niveau 3, le choix « ask » fait répéter mot pour mot la ligne précédente.'],
        ['Fautes dans les arbres V1', '40 + 240', '« Fair. the box… » (minuscule) ; « boundary on trunk lot », « more about family binder » (article manquant).'],
        ['Hubs appelés mais absents', '6', 'close_polite, local_chatter, personal_checkin, absurd_banter, role_related, practical_or_exit ; 140 relances V4 attendent un hub.'],
        ['Scènes sans habitant réel', '33 / 455', 'Boulanger 17, bibliothécaire 6, fermier 2, taxi, zoo, radio, marin… ; 22 scènes citent une boulangerie absente du village.'],
        ['Scènes avec référence pop', '185 (41 %)', 'Toutes V5/V6. Une quasi-citation à retirer : « So the cake was a lie? » (Portal).'],
        ['Cartes hors métier', '≈ 1', 'Les sujets « cartes » restent chez des rôles légitimes ; une scène de bibliothécaire à vérifier.'],
    ],
    'perf': [
        ['Séquenceur GDScript', '0,40 ms / réplique', 'Moyenne sur les 2 096 répliques V8 (p99 0,9 ms). Calculé une fois par réplique.'],
        ['Déclenchement d’un grain', '32 µs', 'WAV importé en QOA. Version OGG mesurée d’abord : 1 ms par grain, abandonnée.'],
        ['12 voix 3D en continu', '0,14 ms / image', 'Glissés de hauteur compris. p99 0,33 ms ; un pic unique au premier mot (chargement). Stress test, bien au-delà du budget du jeu.'],
        ['Préchargement', '0,6 s pour 13 profils', 'En tâche de fond, quand un habitant s’approche.'],
        ['Banque', '18 × ~200 grains', '≈ 60 syllabes par profil × 3 longueurs (réduite, accentuée, finale) ; régénérable à l’identique en 45 s.'],
        ['Parité Python / Godot', '23 / 23', 'Mêmes grains, mêmes instants, mêmes hauteurs de début et de fin de glissé (écart < 10⁻⁹).'],
        ['Tests Python', '35 / 35', 'Dont les 10 voix d’origine reproduites (corrélation > 0,999) et 2 096 répliques V8 sans échec.'],
        ['Cas limites Godot', '16 / 16', 'Profil inconnu, banque absente, émotion inconnue, réplique coupée, redite, PNJ retiré de la scène, sauvegarde/reprise, textes vides.'],
    ],
}
page = open(os.path.join(ICI, 'page_demo.html'), encoding='utf-8').read()
page = page.replace('__DONNEES__', json.dumps(donnees, ensure_ascii=False).replace('</', '<\\/'))
open(os.path.join(RACINE, 'demo', 'index.html'), 'w', encoding='utf-8').write(page)
print('demo/index.html', len(page) // 1024, 'Ko')
