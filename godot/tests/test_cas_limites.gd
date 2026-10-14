extends SceneTree
## godot --headless --path . --script res://godot/tests/test_cas_limites.gd
var echecs := 0
var controles := 0

func verifier(ok: bool, quoi: String) -> void:
	controles += 1
	if not ok:
		echecs += 1
		printerr("ÉCHEC : " + quoi)

var image := 0

func _process(_delta: float) -> bool:
	image += 1
	if image == 1:
		_tests()
		print("%d contrôles, %d échecs" % [controles, echecs])
	elif image == 3:  # laisse le mixeur libérer les grains en cours avant de quitter
		for n in root.get_children():
			n.queue_free()
	elif image == 5:
		CharabiaBanque.vider()
		quit(1 if echecs else 0)
	return false

func _tests() -> void:
	CharabiaVoix.charger_donnees()
	var E := CharabiaVoix.emotions
	# Profil inconnu : repli sur la voix d'origine, pas de plantage.
	var v := CharabiaVoix.new()
	root.add_child(v)
	v.configurer("boulanger_inexistant", 999, false)
	verifier(v.locuteur.pid == "origine", "profil inconnu -> origine")
	# Émotion inconnue : neutre.
	verifier(v.dire("Morning. The bread's almost ready.", "nostalgique_inconnue") > 0.0, "émotion inconnue -> neutre, la voix parle")
	# Redire pendant qu'il parle : la réplique précédente est coupée, la nouvelle part.
	var d2 := v.dire("Sure thing.", "neutre")
	verifier(v.parle() and d2 > 0.0, "nouvelle réplique pendant la précédente")
	# Le joueur passe la ligne : arrêt avec fondu, signal émis.
	var recu := [false]
	v.fini.connect(func(): recu[0] = true)
	v.arreter()
	verifier(not v.parle() and recu[0], "arrêt propre + signal fini")
	# Banque absente (asset manquant) : silence, mais aucun plantage et 0 s renvoyé.
	var b := CharabiaBanque.new("profil_sans_banque")
	verifier(not b.ok, "banque absente détectée")
	var w := CharabiaVoix.new()
	root.add_child(w)
	w.configurer("origine", 1, true)
	w.banque = b
	verifier(w.dire("Hello there.") == 0.0 and not w.parle(), "banque absente -> sous-titre seul")
	# Textes limites.
	var loc := CharabiaLocuteur.new("origine", CharabiaVoix.profils.origine, 1)
	var ban := CharabiaBanque.pour("origine")
	for t in ["", "...", "?!", "$36.69", "Hmm.", "Uh... uh...", "a" .repeat(400)]:
		var p := CharabiaSequenceur.partition(t, loc, "neutre", E, ban.durees, 0.7)
		verifier(not p.evenements.is_empty() and float(p.infos.duree) < 8.0, "texte limite « %s »" % t.left(12))
	# Sauvegarde / reprise : la mémoire des motifs survit, la suite est identique.
	var a := CharabiaLocuteur.new("enfant", CharabiaVoix.profils.enfant, 36)
	var bb := CharabiaLocuteur.new("enfant", CharabiaVoix.profils.enfant, 36)
	var benf := CharabiaBanque.pour("enfant")
	CharabiaSequenceur.partition("See you around!", a, "joyeux", E, benf.durees, 0.8)
	var sauve: Dictionary = JSON.parse_string(JSON.stringify(a.etat()))
	bb.restaurer(sauve)
	var pa := CharabiaSequenceur.partition("See you around!", a, "joyeux", E, benf.durees, 0.8)
	var pb := CharabiaSequenceur.partition("See you around!", bb, "joyeux", E, benf.durees, 0.8)
	verifier(JSON.stringify(pa.evenements) == JSON.stringify(pb.evenements) and int(pa.infos.occurrence) == 1, "reprise après sauvegarde identique")
	# Même phrase, deux voix : même nombre de mots/syllabes possible, sons différents.
	var p1 := CharabiaSequenceur.partition("Pleasure doing business.", CharabiaLocuteur.new("revendeur_assure", CharabiaVoix.profils.revendeur_assure, 73), "ravi", E, CharabiaBanque.pour("revendeur_assure").durees, 0.6)
	var p2 := CharabiaSequenceur.partition("Pleasure doing business.", CharabiaLocuteur.new("vendeuse_bavarde", CharabiaVoix.profils.vendeuse_bavarde, 57), "ravi", E, CharabiaBanque.pour("vendeuse_bavarde").durees, 0.6)
	verifier(JSON.stringify(p1.evenements) != JSON.stringify(p2.evenements), "même phrase, deux voix différentes")
	# PNJ retiré de la scène en pleine réplique : silence, pas d'erreur.
	var z := CharabiaVoix.new()
	root.add_child(z)
	z.configurer("enfant", 11, true)
	z.dire("I made a cardboard spaceship but the wings fell off during launch.", "triste")
	root.remove_child(z)
	verifier(not z.parle() and z.dire("Hello?") == 0.0, "PNJ hors scène : se tait sans erreur")
	z.free()
