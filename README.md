# Charabia Card Hustle — laboratoire vocal

Prototype des voix des habitants de Card Hustle : le synthétiseur d'origine
(`Outils/generer_voix.py` du jeu) enrichi en charabia expressif. **Rien n'est encore
branché dans le jeu** : ce dépôt sert à écouter, comparer et valider avant intégration.

Page d'écoute A/B : `demo/index.html` (10 scènes, sous-titres anglais, capture Godot,
audit V8, mesures, autocritique).

## Contenu

| Dossier | Rôle |
|---|---|
| `charabia/noyau.py` | DSP des voix d'origine (même source, mêmes formants, mêmes consonnes) ; `ligne_origine()` reproduit les 10 anciennes voix |
| `charabia/vocalises.py` | 18 vocalises (rires, soupirs, hmm, surprise, agacement…) avec le timbre du profil |
| `charabia/banque.py`, `exporter_banque.py` | Banque de grains par profil (240 syllabes + 36 vocalises), exportée en WAV pour Godot (import QOA) |
| `charabia/sequenceur.py` | Sous-titre anglais + profil + émotion → partition de grains (motif stable par réplique, variations, anti-répétition) |
| `charabia/mixage.py`, `demo.py`, `page_demo.py` | Rendu des scènes A/B et de la page |
| `donnees/` | `profils_voix.json` (17 profils + origine), `emotions.json` (14 émotions, tables ton V8 → émotion et Economy → émotion), bibliothèque V8, négociation calculée par Economy |
| `godot/charabia/` | Pilote Godot 4.4 : `CharabiaSequenceur` (portage exact), `CharabiaLocuteur`, `CharabiaBanque`, `CharabiaVoix` (lecteur polyphonique 2D/3D) |
| `godot/tests/`, `tests/` | Parité Python/Godot, cas limites, banc de performance, tests Python |
| `outils_jeu/negociation_demo.gd` | À lancer dans le projet du jeu : produit `donnees/negociation_economy.json` |

## Dialogues V9

`dialogues/construire_v9.py` reconstruit `donnees/dialogues_v9.json` depuis la V8 (intacte) et les textes de
`donnees/ecriture/` : fautes et redites corrigées, raccords manquants, distribution sur les vrais habitants,
réponses variées par famille, humour pop culture et running gags. `dialogues/moteur.py` est le moteur de
conversation de référence avec son directeur d'humour ; `dialogues/simuler_semaine.py` simule la semaine de démo.
Détails : `docs/DIALOGUES_V9.md`, exemples : `docs/exemples_conversations.md`.

## Commandes

```sh
pip install numpy scipy            # + ffmpeg
python3 charabia/exporter_banque.py                     # banque/ (ignorée par git, 24 s)
python3 tests/test_charabia.py                          # JEU=<projet du jeu> pour comparer aux voix d'origine
python3 dialogues/construire_v9.py && python3 tests/test_dialogues.py && python3 dialogues/simuler_semaine.py
python3 charabia/demo.py --jeu <projet du jeu> --sortie demo && python3 charabia/page_demo.py

godot --headless --editor --path . --import --quit
godot --headless --path . --script res://godot/tests/test_parite.gd && python3 tests/test_parite.py <user://parite_godot.json>
godot --headless --path . --script res://godot/tests/test_cas_limites.gd
godot --headless --path . --script res://godot/tests/banc_charabia.gd
```

## Résultats (14 octobre 2026, Godot 4.4.1 headless, Linux)

- v2 « mélodieuse » : legato, glissés de hauteur, arcs mélodiques, gamme pentatonique, vibrato chanté.
- v2.1 : registre médium à médium-aigu (f0 de 165 à 315 Hz, notes jouées surtout entre ~155 et ~500 Hz).
- v3 « syllabaire parlé » (`charabia/phonetique.py`) : syllabes V/CV/CVC/CCV coarticulées, accent par mot, syllabes réduites, mots-outils, source avec jitter/shimmer/pente.
- v4 « calé sur la lecture » : un mot de charabia par mot anglais (longueur voisine), mots-outils rapides, pauses sur la ponctuation, durée ≈ temps de lecture (≈ 15 car./s) ; signal `mot(rang)` pour afficher le sous-titre mot à mot.
- Bavardage d'ambiance (`godot/charabia/charabia_ambiance.gd`) : les habitants proches bavardent entre eux sans sous-titres (prosodie tirée de `donnees/ambiance_scripts.json`), audibles jusqu'à 30 m, 3 conversations au plus (2 près du joueur), silences, baisse de 9 dB pendant un dialogue. Test : `godot/tests/test_ambiance.gd`.
- Tests Python 35/35 ; parité Python/Godot 23/23 ; cas limites Godot 16/16.
- Séquenceur GDScript 0,31 ms par réplique ; 34 µs par grain déclenché ; 12 voix en continu 0,12 ms/image avec glissés (p99 0,28 ms).
- Non mesuré : coût du mixage C++ (pilote audio factice), rendu sur PC de jeu.
