class_name CharabiaLocuteur
extends RefCounted
## État vocal d'un habitant : profil, hauteur personnelle, mémoire anti-répétition.
## `etat()` / `restaurer()` : ce qui mérite d'aller dans la sauvegarde (occurrences des motifs).

var pid: String
var profil: Dictionary
var ident: int
var decalage_f0: float
var repliques := 0
var occurrences := {}            # motif -> nombre de fois dite
var dernieres_vocalises := []    # [[type, n° de réplique]]
var dernier_variant := {}        # type -> dernière prise jouée

func _init(p_pid: String, p_profil: Dictionary, p_ident: int = 0, p_decalage: float = 1.0) -> void:
	pid = p_pid
	profil = p_profil
	ident = p_ident
	decalage_f0 = p_decalage

## Deux habitants du même profil n'ont pas tout à fait la même hauteur (±6 %).
static func decalage_pour(id_habitant: int) -> float:
	return 1 + (((id_habitant * 37) % 11) - 5) * 0.012

func etat() -> Dictionary:
	return {"repliques": repliques, "occurrences": occurrences}

func restaurer(d: Dictionary) -> void:
	repliques = int(d.get("repliques", 0))
	occurrences = d.get("occurrences", {})
	for k in occurrences:
		occurrences[k] = int(occurrences[k])
