"""Extrait de la V8 des échanges courts entre deux habitants, pour le bavardage d'ambiance.

Le texte n'est jamais affiché : il sert seulement à donner au charabia un rythme et une
intonation de vraie conversation (questions, réponses, exclamations). Écrit
donnees/ambiance_scripts.json : [[["A"|"B", texte, émotion], ...], ...]
"""
import json, os, random

RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
TONS = json.load(open(os.path.join(RACINE, 'donnees', 'emotions.json'), encoding='utf-8'))['tons_v8']

v8 = json.load(open(os.path.join(RACINE, 'donnees', 'CARD_HUSTLE_DIALOGUES_CONSOLIDES_V8.json'), encoding='utf-8'))
rng = random.Random(4)
scripts = []
for s in v8['scenes']:
    if s['source'] not in ('V2', 'V3', 'V4', 'V5', 'V6'):
        continue
    for c in s['choices']:
        if not c.get('npc'):
            continue
        emo = TONS.get(c.get('tone'), 'neutre')
        tours = [['A', s['opening'], 'neutre'], ['B', c['player'], 'curieux' if c['player'].endswith('?') else emo],
                 ['A', c['npc'], emo]]
        fups = [f for f in c.get('followups', []) if f.get('npc')]
        if fups and rng.random() < .6:
            f = rng.choice(fups)
            tours += [['B', f['player'], 'neutre'], ['A', f['npc'], 'joyeux' if 'close' in str(f.get('outcome')) else 'neutre']]
        scripts.append(tours)
rng.shuffle(scripts)
json.dump(scripts[:400], open(os.path.join(RACINE, 'donnees', 'ambiance_scripts.json'), 'w', encoding='utf-8'), ensure_ascii=False)
print(len(scripts), 'échanges ; 400 gardés')
