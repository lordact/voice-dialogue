# Dialogues V9 — nettoyage, distribution et humour pop culture

La V8 (`donnees/CARD_HUSTLE_DIALOGUES_CONSOLIDES_V8.json`) n'est jamais modifiée. La V9
(`donnees/dialogues_v9.json`) est reconstruite à l'identique par `python3 dialogues/construire_v9.py`
à partir de la V8 et des textes écrits dans `donnees/ecriture/`.

## Ce qui change

| | V8 | V9 |
|---|---|---|
| Répliques de PNJ différentes | 2 124 | 2 656 |
| Refus identique « Understood. Thanks for being decent about it. » | 800 | 0 (variantes par interlocuteur) |
| Réponse qui répète mot pour mot la ligne précédente (arbres V1) | 480 | 0 |
| Fautes dans les arbres V1 (majuscule, article manquant) | 443 | 0 |
| Raccords appelés mais absents | 6 | 0 |
| Scènes jouables par un vrai habitant du Village_Demo | 422 | 453 / 455 |
| Réponses aux relances génériques | 1 réponse figée, répétée 120 fois | tronc commun + 11 familles de personnages |
| Humour pop culture | 185 scènes, sans dosage | 185 scènes + 55 clins d'œil + 8 running gags (30 étapes) + réactions, dosés |

- **Boulangerie** : le village n'en a pas ; les 17 scènes de boulanger sont jouées par la cuisine du café
  (Marcus, Leo) et « bakery » devient « café » dans le texte. Restent sans habitant : le maître-nageur
  (pas de piscine) et l'acheteur en ligne (passe par le téléphone).
- **Scènes V2** : attribuées selon leur thème (famille du joueur pour « Family and Home », métiers de
  service pour « Jobs », jeunes pour « Friendship »…), plus n'importe quel habitant.
- **Quasi-citation retirée** : « So the cake was a lie? » → « So the recipe was a trap all along? ».

## Humour : règles d'écriture

- Allusions reconnaissables (quêtes secondaires, écrans de chargement, « achievement unlocked », le
  chien dans la pièce en feu, les rires enregistrés de sitcom, l'édition longue avec appendices…).
- Jamais de réplique culte recopiée, jamais de nom de marque ou de personnage dans le texte dit
  (vérifié par `tests/test_dialogues.py`). Le champ `reference` sert seulement à l'audit.
- Chaque réplique a un public (enfant, ado, adulte, senior), un domaine (jeux vidéo, mèmes, films,
  séries, cartes, jeux de société) et une intensité (1 clin d'œil, 2 blague franche, 3 gros gag).
- Les retraités ont un style « papy_meme » : ils emploient les mèmes de travers (« My grandson
  says ‘GG’. I believe it means good luck. »).
- Les running gags appartiennent au village : les canards du passage piéton, la Bourse de Tyler et
  Noah, la sauce de Marcus, les outils de Doug, le tableur de Colin, le château d'eau de Samir, le bus
  de Nora, les règles de Debbie. Une étape au plus par jour, dite par son personnage.

## Le directeur d'humour (`dialogues/moteur.py`)

- Appétit d'humour par habitant (style, âge, goûts, histoire) ; il grandit quand on se connaît.
- Réciprocité : si le joueur plaisante et que le personnage aime ça, il plaisante davantage.
- Jamais de blague si le personnage est triste, en colère ou déçu, ni pendant une négociation tendue.
- Budget par rencontre : une scène pop **ou** un running gag, plus un clin d'œil au plus.
- Un clin d'œil n'est jamais réentendu dans la semaine ; trois références au plus par domaine et par jour.

Simulation de la semaine de démo (`python3 dialogues/simuler_semaine.py`, 7 jours × 14 rencontres,
moyenne sur 5 tirages) :

| Joueur | Rencontres avec humour | Redites entendues | Humour en négociation tendue |
|---|---|---|---|
| Blagueur | 40 % | 0,8 sur 321 répliques | 0 |
| Neutre | 34 % | 0 sur 309 | 0 |
| Sérieux | 15 % | 0,6 sur 301 | 0 |

Exemples complets : `docs/exemples_conversations.md`.

## Limites connues

- Les arbres V1 restent construits sur des gabarits : la même structure revient d'un scénario à l'autre ;
  la mémoire du moteur évite seulement qu'un joueur entende deux fois la même réplique.
- Certaines répliques « humor » de la V2 sont absurdes sans lien clair avec la phrase du joueur
  (« The spoons are strangely persuasive. ») : à relire scène par scène.
- Le moteur est une référence Python ; son portage Godot (comme pour la voix) se fera à l'intégration.
- Les références pop culture restent à valider juridiquement avant une sortie commerciale (liste dans
  `donnees/ecriture/humour_pop.json`, champ `reference`).
