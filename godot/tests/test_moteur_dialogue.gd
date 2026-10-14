extends SceneTree
## Joue une semaine de conversations avec chaque habitant et vérifie le déroulé du MoteurDialogue.

func _init() -> void:
	var m := MoteurDialogue.new("res://donnees/dialogues_v9.json", "res://donnees/emotions.json", 7)
	var hs: Array = JSON.parse_string(FileAccess.get_file_as_string("res://donnees/habitants_village_demo.json"))
	var erreurs := 0
	var lignes := 0
	var etapes_max := 0
	var vides := 0
	var tags := {}
	var alea := RandomNumberGenerator.new()
	alea.seed = 3
	for jour in 7:
		m.jour = jour
		for h in hs:
			var e := m.commencer(int(h.id), alea.randf() < 0.1)
			var n := 0
			while true:
				n += 1
				for l in e.lignes:
					lignes += 1
					tags[l.tag] = int(tags.get(l.tag, 0)) + 1
					if str(l.texte).strip_edges() == "":
						vides += 1
				if e.fin:
					break
				if e.options.is_empty() or e.options[-1] != MoteurDialogue.PARTIR:
					erreurs += 1
					break
				if n > 14:
					erreurs += 1
					break
				# choisit souvent une vraie option, parfois « partir »
				var k: int = alea.randi() % e.options.size() if alea.randf() < 0.85 else e.options.size() - 1
				if e.options.size() == 1:
					k = 0
				e = m.choisir(k)
			etapes_max = maxi(etapes_max, n)
	var sauve: Dictionary = JSON.parse_string(JSON.stringify(m.etat()))
	var m2 := MoteurDialogue.new("res://donnees/dialogues_v9.json", "res://donnees/emotions.json", 7)
	m2.restaurer(sauve)
	var e2 := m2.commencer(30)
	print("lignes=%d etapes_max=%d vides=%d erreurs=%d tags=%s" % [lignes, etapes_max, vides, erreurs, tags])
	print("restauré: rencontres Dave=", m2.pnj.get("30", {}).get("rencontres"), " ouverture: ", e2.lignes[0].texte)
	var ok := erreurs == 0 and vides == 0 and lignes > 1000 and int(m2.pnj["30"].rencontres) >= 7
	print("MOTEUR " + ("OK" if ok else "ECHEC"))
	quit(0 if ok else 1)
