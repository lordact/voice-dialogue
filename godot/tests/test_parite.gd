extends SceneTree
## godot --headless --path . --script res://godot/tests/test_parite.gd
## Écrit user://parite_godot.json : partitions calculées par Godot pour tests/cas_parite.json.
func _init() -> void:
	CharabiaVoix.charger_donnees()
	var cas: Array = JSON.parse_string(FileAccess.get_file_as_string("res://godot/tests/cas_parite.json")).cas
	var sortie := []
	for c in cas:
		var banque := CharabiaBanque.pour(c.profil)
		var loc := CharabiaLocuteur.new(c.profil, CharabiaVoix.profils[c.profil], int(c.ident), CharabiaLocuteur.decalage_pour(int(c.ident)))
		var parts := []
		for r in c.repliques:
			var p := CharabiaSequenceur.partition(r[0], loc, r[1], CharabiaVoix.emotions, banque.durees, float(r[2]), 60.0)
			parts.append(p)
		sortie.append(parts)
	var f := FileAccess.open("user://parite_godot.json", FileAccess.WRITE)
	f.store_string(JSON.stringify(sortie))
	f.close()
	print("PARITE_OK ", ProjectSettings.globalize_path("user://parite_godot.json"))
	CharabiaBanque.vider()
	quit()
