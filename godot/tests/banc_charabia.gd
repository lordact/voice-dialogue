extends SceneTree
## Banc d'essai du pilote :
##   godot --headless --fixed-fps 60 --path . --script res://godot/tests/banc_charabia.gd
## 1) coût du séquenceur sur toutes les répliques PNJ de la V8 ;
## 2) 12 habitants qui parlent en même temps (3D), temps de _process et grains actifs ;
## 3) enregistrement de la sortie réelle (bus Master) : user://charabia_godot.wav.

var voix := []
var image := 0
var t_process := []
var t_moteur := []
var t_voix_avant := 0
var lignes := []
var rec: AudioEffectRecord
var dialogue: Array
var etape := 0
var prochain := 0.0
var horloge := 0.0
var ui: CharabiaVoix

var prechargement := true

func _init() -> void:
	CharabiaVoix.charger_donnees()
	prechargement = not ("--sans-prechargement" in OS.get_cmdline_user_args())
	Engine.max_fps = 60  # temps réel : l'enregistrement du bus Master suit l'horloge audio
	_banc_sequenceur()
	_installer_scene()

func _lignes_v8() -> Array:
	var d: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://donnees/CARD_HUSTLE_DIALOGUES_CONSOLIDES_V8.json"))
	var vues := {}
	for s in d.scenes:
		vues[s.opening] = true
		for c in s.choices:
			if c.get("npc"): vues[c.npc] = true
			for f in c.get("followups", []):
				if f.get("npc"): vues[f.npc] = true
	for k in d.deep_trees.V1.nodes:
		var n: Dictionary = d.deep_trees.V1.nodes[k]
		vues[n.npc_line] = true
		for c in n.choices:
			if c.has("npc_reply"): vues[c.npc_reply] = true
	return vues.keys()

func _banc_sequenceur() -> void:
	lignes = _lignes_v8()
	var pids: Array = CharabiaVoix.profils.keys()
	var emos: Array = CharabiaVoix.emotions.keys()
	var cout := []
	var duree_max := 0.0
	var syl_max := 0
	var vides := 0
	var t0 := Time.get_ticks_usec()
	for i in lignes.size():
		var pid: String = pids[i % pids.size()]
		var loc := CharabiaLocuteur.new(pid, CharabiaVoix.profils[pid], i)
		var b := CharabiaBanque.pour(pid)
		var a := Time.get_ticks_usec()
		var p := CharabiaSequenceur.partition(lignes[i], loc, emos[i % emos.size()], CharabiaVoix.emotions, b.durees, 0.7)
		cout.append(Time.get_ticks_usec() - a)
		duree_max = maxf(duree_max, float(p.infos.duree))
		syl_max = maxi(syl_max, int(p.infos.syllabes))
		if p.evenements.is_empty(): vides += 1
	cout.sort()
	print("SEQUENCEUR lignes=%d total=%.1f ms moyenne=%d us mediane=%d us p99=%d us max=%d us duree_max=%.2f s syllabes_max=%d partitions_vides=%d" % [
		lignes.size(), (Time.get_ticks_usec() - t0) / 1000.0, int(cout.reduce(func(a, b): return a + b, 0) / cout.size()),
		cout[cout.size() / 2], cout[int(cout.size() * 0.99)], cout[-1], duree_max, syl_max, vides])

func _installer_scene() -> void:
	var monde := Node3D.new()
	root.add_child(monde)
	var cam := Camera3D.new()
	monde.add_child(cam)
	var ecoute := AudioListener3D.new()
	cam.add_child(ecoute)
	ecoute.make_current()
	var pids := ["vendeuse_bavarde", "commercant_blase", "collectionneur_methodique", "revendeur_nerveux", "enfant", "grand_gaillard",
		"dame_distinguee", "pro_presse", "parent_chaleureux", "sarcastique", "reveuse_artiste", "cuisinier_jovial"]
	for i in pids.size():
		var n := Node3D.new()
		monde.add_child(n)
		n.position = Vector3(cos(i) * (2 + i), 0, sin(i) * (2 + i))
		var v := CharabiaVoix.new()
		n.add_child(v)
		v.configurer(pids[i], 50 + i, true)
		voix.append(v)
		if prechargement:
			v.banque.precharger()
	ui = CharabiaVoix.new()
	root.add_child(ui)
	ui.configurer("revendeur_assure", 73, false)
	if prechargement:
		ui.banque.precharger()
		var t0 := Time.get_ticks_msec()
		for v in voix + [ui]:
			while not v.banque.prechargement_fini():
				OS.delay_msec(5)
		print("PRECHARGEMENT 13 profils en %d ms" % (Time.get_ticks_msec() - t0))
	rec = AudioEffectRecord.new()
	AudioServer.add_bus_effect(0, rec)
	rec.set_recording_active(true)
	dialogue = [["I know what the market is. I also know what sells.", "neutre", 0.6], ["You're not my first lowballer today.", "furieux", 0.75],
		["Meet me in the middle.", "mefiant", 0.7], ["Pleasure doing business.", "ravi", 0.55]]

var sortie := -1

func _process(delta: float) -> bool:
	if sortie >= 0:  # laisse le mixeur libérer les grains avant de quitter
		sortie += 1
		if sortie == 1:
			AudioServer.remove_bus_effect(0, 0)
			for v in voix + [ui]:
				v.lecteur.stop()
			for n in root.get_children():
				n.queue_free()
		elif sortie == 4:
			CharabiaBanque.vider()
			return true
		return false
	horloge += delta
	image += 1
	var a := Time.get_ticks_usec()
	if image < 600:
		# phase 1 : 12 voix 3D bavardent sans arrêt (pire cas, bien au-delà du budget prévu)
		for i in voix.size():
			var v: CharabiaVoix = voix[i]
			if not v.parle():
				v.dire(lignes[(image * 7 + i * 131) % lignes.size()], ["neutre", "joyeux", "agace", "fatigue"][i % 4], 0.7)
	elif image == 600:
		for v in voix:
			v.arreter()
		prochain = horloge + 0.5
	elif etape < dialogue.size() and horloge >= prochain and not ui.parle():
		var r: Array = dialogue[etape]
		prochain = horloge + ui.dire(r[0], r[1], r[2]) + 0.6
		etape += 1
	t_process.append(Time.get_ticks_usec() - a)
	if image > 5 and image < 600:
		t_moteur.append(CharabiaVoix.cout_lecture_usec - t_voix_avant)
	t_voix_avant = CharabiaVoix.cout_lecture_usec
	if etape >= dialogue.size() and horloge > prochain + 0.5:
		rec.set_recording_active(false)
		var w := rec.get_recording()
		var info := "aucun enregistrement (pilote audio factice ?)"
		if w:
			w.save_to_wav("user://charabia_godot.wav")
			info = "%s, %.1f s" % [ProjectSettings.globalize_path("user://charabia_godot.wav"), w.get_length()]
		var phase1: Array = t_process.slice(5, 600)
		phase1.sort()
		print("LECTURE images=%d voix=12 _process moyen=%d us p99=%d us max=%d us | grains declenches: voir audio | wav=%s" % [
			phase1.size(), int(phase1.reduce(func(x, y): return x + y, 0) / phase1.size()), phase1[int(phase1.size() * 0.99)], phase1[-1], info])
		t_moteur.sort()
		print("LECTURE_VOIX (_process des 12 CharabiaVoix, par image) moyen=%d us p99=%d us max=%d us" % [int(t_moteur.reduce(func(x, y): return x + y, 0) / t_moteur.size()), t_moteur[int(t_moteur.size() * 0.99)], t_moteur[-1]])
		print("GRAINS declenches=%d play_stream total=%d ms soit %d us/grain" % [CharabiaVoix.nb_grains, CharabiaVoix.cout_play_usec / 1000, CharabiaVoix.cout_play_usec / maxi(1, CharabiaVoix.nb_grains)])
		print("MEMOIRE statique=%.1f Mo" % (Performance.get_monitor(Performance.MEMORY_STATIC) / 1048576.0))
		sortie = 0
	return false
