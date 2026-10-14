class_name CharabiaAmbiance
extends Node
## Bavardage d'ambiance : les habitants proches les uns des autres se parlent entre eux, et on
## les entend au loin. Pas de sous-titres : le texte (tiré de la V8) ne sert qu'à donner un
## rythme et une intonation de vraie conversation au charabia.
##
## Règles anti-cacophonie : au plus `max_conversations` à la fois, dont `max_proches` à moins de
## `rayon_proche` du joueur ; un groupe qui vient de parler se tait un moment ; parfois personne
## ne parle ; pendant un dialogue du joueur, l'ambiance baisse de `baisse_dialogue_db`.

@export var rayon_ecoute := 30.0          ## au-delà, aucune conversation ne démarre (et on n'entendrait rien)
@export var distance_paire := 4.0         ## deux habitants à moins de cette distance peuvent bavarder
@export var max_conversations := 3
@export var max_proches := 2
@export var rayon_proche := 15.0
@export var gain_ambiance_db := -5.0      ## on bavarde entre soi plus doucement qu'on ne parle au joueur
@export var baisse_dialogue_db := -9.0
@export var envie := 0.5                  ## chance qu'un groupe disponible se mette à parler à chaque examen

var auditeur: Node3D
var habitants := []        # [{noeud, voix, id, libre_a}]
var conversations := []    # [{a, b, tours, i, prochain, cle}]
var silences := {}         # paire -> instant où elle peut reparler
var scripts := []
var rng := RandomNumberGenerator.new()
var _t := 0.0
var _examen := 0.0
var _gain_courant := 0.0
var _gain_vise := 0.0
# Mesures (banc d'essai).
var nb_lancees := 0
var max_simultanees := 0
var max_proches_vu := 0
var cout_usec := 0

func _ready() -> void:
	rng.seed = 12345
	scripts = JSON.parse_string(FileAccess.get_file_as_string("res://donnees/ambiance_scripts.json"))
	_gain_courant = gain_ambiance_db
	_gain_vise = gain_ambiance_db

## À appeler pour chaque habitant (sa voix d'ambiance est posée sous son nœud 3D).
func ajouter(noeud: Node3D, profil_id: String, id_habitant: int) -> CharabiaVoix:
	var v := CharabiaVoix.new()
	noeud.add_child(v)
	v.configurer(profil_id, id_habitant, true, "Master", rayon_ecoute)
	v.gain_db = gain_ambiance_db
	habitants.append({"noeud": noeud, "voix": v, "id": id_habitant, "libre_a": 0.0, "occupe": false})
	return v

## Le joueur parle à quelqu'un : on baisse le bavardage (et cet habitant ne bavarde plus).
func dialogue_joueur(actif: bool, noeud_interlocuteur: Node3D = null) -> void:
	_gain_vise = gain_ambiance_db + (baisse_dialogue_db if actif else 0.0)
	for h in habitants:
		if h.noeud == noeud_interlocuteur:
			h.occupe = actif
			if actif:
				_couper_conversations_de(h)

func _process(delta: float) -> void:
	var t0 := Time.get_ticks_usec()
	_t += delta
	# Baisse / remontée douce du volume d'ambiance.
	_gain_courant = move_toward(_gain_courant, _gain_vise, delta * 30.0)
	for h in habitants:
		h.voix.gain_db = _gain_courant
	# Tours de parole des conversations en cours.
	var k := 0
	while k < conversations.size():
		var c: Dictionary = conversations[k]
		# Devenue inaudible (le joueur s'est éloigné) : elle s'arrête et libère sa place.
		if auditeur and c.a.noeud.global_position.distance_to(auditeur.global_position) > rayon_ecoute + 5.0:
			c.a.voix.arreter()
			c.b.voix.arreter()
			_terminer(c)
			conversations.remove_at(k)
			continue
		var parleur: Dictionary = c.a if c.tours[c.i][0] == "A" else c.b
		if _t >= c.prochain:
			if c.i >= c.tours.size() - 1 and c.get("commence", false):
				if parleur.voix.parle():   # on laisse finir la dernière réplique
					k += 1
					continue
				_terminer(c)
				conversations.remove_at(k)
				continue
			if c.get("commence", false):
				c.i += 1
			c.commence = true
			var tour: Array = c.tours[c.i]
			var qui: Dictionary = c.a if tour[0] == "A" else c.b
			var duree: float = qui.voix.dire(tour[1], tour[2], rng.randf_range(0.4, 0.8))
			# Petit blanc entre deux répliques, parfois un léger chevauchement (on se coupe la parole).
			var blanc := rng.randf_range(-0.12, 0.6) if rng.randf() < 0.85 else rng.randf_range(0.8, 1.6)
			c.prochain = _t + duree + blanc
		k += 1
	# Recherche de nouveaux groupes (deux fois par seconde suffit).
	_examen -= delta
	if _examen <= 0.0:
		_examen = 0.5
		_chercher()
	_mesurer()
	cout_usec += Time.get_ticks_usec() - t0

func _chercher() -> void:
	if auditeur == null or scripts.is_empty() or conversations.size() >= max_conversations:
		return
	var proches := _nb_proches()
	var p := auditeur.global_position
	for i in habitants.size():
		var a: Dictionary = habitants[i]
		if not _libre(a) or a.noeud.global_position.distance_to(p) > rayon_ecoute:
			continue
		for j in range(i + 1, habitants.size()):
			var b: Dictionary = habitants[j]
			if not _libre(b) or a.noeud.global_position.distance_to(b.noeud.global_position) > distance_paire:
				continue
			var cle := "%d-%d" % [a.id, b.id]
			if _t < float(silences.get(cle, 0.0)):
				continue
			var proche: bool = a.noeud.global_position.distance_to(p) < rayon_proche
			if proche and proches >= max_proches:
				continue
			if rng.randf() > envie:
				silences[cle] = _t + rng.randf_range(4.0, 10.0)   # pas envie de parler pour l'instant
				continue
			var tours: Array = scripts[rng.randi() % scripts.size()]
			if rng.randf() < 0.5:
				tours = _inverser(tours)
			conversations.append({"a": a, "b": b, "tours": tours, "i": 0, "prochain": _t + rng.randf_range(0.0, 0.6), "cle": cle})
			a.libre_a = INF
			b.libre_a = INF
			nb_lancees += 1
			if OS.is_debug_build() and "--trace-ambiance" in OS.get_cmdline_user_args():
				print("t=%.1f lance %s (dist joueur %.0f m, %d en cours)" % [_t, cle, a.noeud.global_position.distance_to(p), conversations.size()])
			return

func _libre(h: Dictionary) -> bool:
	return not h.occupe and _t >= float(h.libre_a)

func _inverser(tours: Array) -> Array:
	var out := []
	for tr in tours:
		out.append(["B" if tr[0] == "A" else "A", tr[1], tr[2]])
	return out

func _terminer(c: Dictionary) -> void:
	silences[c.cle] = _t + rng.randf_range(25.0, 50.0)   # ce groupe se tait un moment
	c.a.libre_a = _t + rng.randf_range(15.0, 35.0)
	c.b.libre_a = _t + rng.randf_range(15.0, 35.0)

func _couper_conversations_de(h: Dictionary) -> void:
	var k := 0
	while k < conversations.size():
		var c: Dictionary = conversations[k]
		if c.a == h or c.b == h:
			c.a.voix.arreter()
			c.b.voix.arreter()
			_terminer(c)
			conversations.remove_at(k)
		else:
			k += 1

func _nb_proches() -> int:
	if auditeur == null:
		return 0
	var n := 0
	for c in conversations:
		if c.a.noeud.global_position.distance_to(auditeur.global_position) < rayon_proche:
			n += 1
	return n

func _mesurer() -> void:
	var actives := 0
	for c in conversations:
		if c.a.voix.parle() or c.b.voix.parle():
			actives += 1
	max_simultanees = maxi(max_simultanees, actives)
	max_proches_vu = maxi(max_proches_vu, _nb_proches())
