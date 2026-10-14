extends SceneTree
## Bavardage d'ambiance au loin, dans le vrai moteur (temps réel, enregistrement du bus Master).
##   godot --headless --path . --script res://godot/tests/test_ambiance.gd
## Le joueur traverse le village en 40 s ; à 22 s il parle 6 s à Derek (l'ambiance doit baisser).

const PROFILS := ["vendeuse_bavarde", "commercant_blase", "dame_distinguee", "grand_gaillard", "enfant", "parent_chaleureux",
	"collectionneur_methodique", "revendeur_nerveux", "sarcastique", "vieil_habitue", "ado_surexcite", "cuisinier_jovial",
	"reveuse_artiste", "pro_presse", "agent_officiel", "voisin_discret"]
# Groupes : brocante (4 stands), terrasse du café, banc du parc, un groupe très loin (hors d'écoute au début).
const GROUPES := [Vector3(-25, 0, 6), Vector3(-5, 0, -4), Vector3(0, 0, 5), Vector3(6, 0, -5), Vector3(12, 0, 4),
	Vector3(30, 0, 8), Vector3(-45, 0, -8), Vector3(85, 0, 0)]

var amb: CharabiaAmbiance
var joueur: Node3D
var derek: CharabiaVoix
var rec: AudioEffectRecord
var t := 0.0
var etape := 0
var sortie := -1
var echantillons := []
var debut := 0
var code := 0

func _init() -> void:
	CharabiaVoix.charger_donnees()
	Engine.max_fps = 60
	var monde := Node3D.new()
	root.add_child(monde)
	joueur = Node3D.new()
	monde.add_child(joueur)
	var cam := Camera3D.new()
	joueur.add_child(cam)
	var ecoute := AudioListener3D.new()
	cam.add_child(ecoute)
	ecoute.make_current()
	amb = CharabiaAmbiance.new()
	root.add_child(amb)
	amb.auditeur = joueur
	var n := 0
	for g in GROUPES:
		for k in 3:
			var h := Node3D.new()
			monde.add_child(h)
			h.position = g + Vector3(cos(k * 2.1) * 1.3, 0, sin(k * 2.1) * 1.3)
			var v := amb.ajouter(h, PROFILS[n % PROFILS.size()], 100 + n)
			v.banque.precharger()
			n += 1
	derek = CharabiaVoix.new()
	root.add_child(derek)
	derek.configurer("revendeur_assure", 73, false)
	derek.banque.precharger()
	rec = AudioEffectRecord.new()
	AudioServer.add_bus_effect(0, rec)
	rec.set_recording_active(true)
	debut = Time.get_ticks_msec()

func _process(delta: float) -> bool:
	if sortie >= 0:
		sortie += 1
		if sortie == 1:
			AudioServer.remove_bus_effect(0, 0)
			for c in root.get_children():
				c.queue_free()
		elif sortie == 4:
			CharabiaBanque.vider()
			quit(code)
		return false
	t += delta
	joueur.position = Vector3(lerpf(-40.0, 60.0, clampf(t / 40.0, 0.0, 1.0)), 1.6, 0)
	if etape == 0 and t > 22.0:
		etape = 1
		amb.dialogue_joueur(true)
		derek.dire("I know what the market is. I also know what sells.", "neutre", 0.6)
	elif etape == 1 and t > 25.0:
		etape = 2
		derek.dire("Meet me in the middle.", "mefiant", 0.7)
	elif etape == 2 and t > 28.0:
		etape = 3
		amb.dialogue_joueur(false)
	var parlent := 0   # voix réellement audibles (à moins de 30 m)
	for h in amb.habitants:
		if h.voix.parle() and h.noeud.global_position.distance_to(joueur.global_position) < amb.rayon_ecoute:
			parlent += 1
	echantillons.append(parlent)
	if t > 42.0:
		rec.set_recording_active(false)
		var w := rec.get_recording()
		var info := "aucun enregistrement"
		if w:
			w.save_to_wav("user://ambiance_village.wav")
			info = "%.1f s" % w.get_length()
		var silence := 0
		for e in echantillons:
			if e == 0:
				silence += 1
		print("AMBIANCE conversations=%d max_simultanees=%d max_proches=%d voix_max=%d temps_sans_bavardage_audible=%d%% cout_moyen=%d us/image wav=%s" % [
			amb.nb_lancees, amb.max_simultanees, amb.max_proches_vu, echantillons.max(),
			int(100.0 * silence / echantillons.size()), amb.cout_usec / maxi(1, echantillons.size()), info])
		print("WAV ", ProjectSettings.globalize_path("user://ambiance_village.wav"))
		if amb.max_simultanees > amb.max_conversations or amb.nb_lancees < 4 or echantillons.max() > 2 * amb.max_conversations:
			printerr("ÉCHEC : règles anti-cacophonie non respectées")
			code = 1
		sortie = 0
	return false
