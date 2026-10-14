extends SceneTree
## Empaquette res://banque/<profil>/ (WAV importés en QOA) en res://banque_pack/<profil>.res.
##   python3 charabia/exporter_banque.py && godot --headless --editor --path . --import --quit
##   godot --headless --path . --script res://godot/outils/empaqueter_banque.gd
func _init() -> void:
	DirAccess.make_dir_recursive_absolute("res://banque_pack")
	var total := 0
	for pid in DirAccess.get_directories_at("res://banque"):
		var idx: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://banque/%s/index.json" % pid))
		var pack := CharabiaPack.new()
		pack.profil = pid
		pack.index = idx
		for nom in idx.syllabes:
			pack.grains["syl:" + nom] = load("res://banque/%s/%s.wav" % [pid, nom]).duplicate()   # duplicate : le son est intégré, pas référencé
		for typ in idx.vocalises:
			for k in idx.vocalises[typ].size():
				pack.grains["voc:%s:%d" % [typ, k]] = load("res://banque/%s/%s_%d.wav" % [pid, typ, k]).duplicate()
		var chemin := "res://banque_pack/%s.res" % pid
		var err := ResourceSaver.save(pack, chemin, ResourceSaver.FLAG_COMPRESS)
		var taille := FileAccess.get_file_as_bytes(chemin).size()
		total += taille
		print("%-26s %4d grains  %6d Ko  %s" % [pid, pack.grains.size(), taille / 1024, "ok" if err == OK else "ERREUR %d" % err])
	print("TOTAL %.1f Mo" % (total / 1048576.0))
	quit()
