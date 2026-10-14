class_name CharabiaPack
extends Resource
## Banque d'un profil vocal en un seul fichier : l'index (durées, attaques, inventaire de
## syllabes) et tous les grains, déjà compressés en QOA. Fabriqué par godot/outils/empaqueter_banque.gd.

@export var profil := ""
@export var index := {}
@export var grains := {}   # "syl:ta_plat" / "voc:rire:1" -> AudioStreamWAV
