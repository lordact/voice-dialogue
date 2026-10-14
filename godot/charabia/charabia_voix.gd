class_name CharabiaVoix
extends Node
## Voix d'un habitant : joue une partition de grains sur un lecteur polyphonique.
## À poser sous le PNJ (3D, atténuée en distance) ou sous l'interface (dialogue ciblé, 2D).
## Aucun calcul audio en GDScript : on déclenche des grains OGG, le mixage reste en C++.

signal fini

const POLYPHONIE := 6

var locuteur: CharabiaLocuteur
var banque: CharabiaBanque
var lecteur: Node                 # AudioStreamPlayer ou AudioStreamPlayer3D
var _lecture: AudioStreamPlaybackPolyphonic
var _evts := []
var _i := 0
var _t := 0.0
var _duree := 0.0
var _parle := false
var _fondu: Tween
var cout_usec := 0                # temps passé à calculer la dernière partition
static var cout_lecture_usec := 0 # temps cumulé de toutes les voix dans _process (mesure)
static var cout_play_usec := 0    # dont : appels play_stream
static var nb_grains := 0

static var emotions := {}
static var profils := {}

static func charger_donnees() -> void:
	if profils.is_empty():
		profils = JSON.parse_string(FileAccess.get_file_as_string("res://donnees/profils_voix.json")).profils
		emotions = JSON.parse_string(FileAccess.get_file_as_string("res://donnees/emotions.json")).emotions

## spatial : true = AudioStreamPlayer3D (bus, distance max) ; false = dialogue plein cadre.
func configurer(profil_id: String, id_habitant: int, spatial: bool, bus: String = "Master", distance_max: float = 11.0) -> void:
	charger_donnees()
	if not profils.has(profil_id):
		push_warning("Charabia : profil inconnu %s, repli sur 'origine'" % profil_id)
		profil_id = "origine"
	locuteur = CharabiaLocuteur.new(profil_id, profils[profil_id], id_habitant, CharabiaLocuteur.decalage_pour(id_habitant))
	banque = CharabiaBanque.pour(profil_id)
	var flux := AudioStreamPolyphonic.new()
	flux.polyphony = POLYPHONIE
	if spatial:
		var p3 := AudioStreamPlayer3D.new()
		p3.max_distance = distance_max
		p3.unit_size = 3.0
		p3.attenuation_filter_cutoff_hz = 6000.0
		p3.max_polyphony = 1
		lecteur = p3
	else:
		lecteur = AudioStreamPlayer.new()
	lecteur.stream = flux
	lecteur.bus = bus
	add_child(lecteur)

func parle() -> bool:
	return _parle

## Dit une réplique (sous-titre anglais exact). Coupe proprement la précédente.
func dire(texte: String, emotion: String = "neutre", intensite: float = 0.7) -> float:
	if not emotions.has(emotion):
		emotion = "neutre"
	if _parle:
		_couper_net()
	if banque == null or not banque.ok or not is_inside_tree():
		return 0.0  # pas de son (asset absent, PNJ hors scène), mais le dialogue continue : le sous-titre suffit
	var t0 := Time.get_ticks_usec()
	var part := CharabiaSequenceur.partition(texte, locuteur, emotion, emotions, banque.durees, intensite)
	cout_usec = Time.get_ticks_usec() - t0
	_evts = part.evenements
	_duree = float(part.infos.duree)
	_i = 0
	_t = 0.0
	if _fondu and _fondu.is_valid():
		_fondu.kill()
	lecteur.volume_db = 0.0
	if not lecteur.playing:
		lecteur.play()
	_lecture = lecteur.get_stream_playback()
	_parle = true
	_avancer(0.0)
	return _duree

## Le joueur passe la ligne : fondu de 60 ms, sans clic.
func arreter(fondu: float = 0.06) -> void:
	if not _parle:
		return
	_parle = false
	_evts = []
	if _fondu and _fondu.is_valid():
		_fondu.kill()
	_fondu = create_tween()
	_fondu.tween_property(lecteur, "volume_db", -60.0, fondu)
	_fondu.tween_callback(func(): lecteur.stop(); lecteur.volume_db = 0.0)
	fini.emit()

func _couper_net() -> void:
	_parle = false
	_evts = []
	if lecteur.is_inside_tree():
		lecteur.stop()

func _exit_tree() -> void:
	_parle = false  # changement de scène : on se tait sans erreur
	_evts = []
	_lecture = null
	if lecteur:
		lecteur.stop()

func _process(delta: float) -> void:
	if _parle:
		var a := Time.get_ticks_usec()
		_avancer(delta)
		cout_lecture_usec += Time.get_ticks_usec() - a

func _avancer(delta: float) -> void:
	_t += delta
	# Lecture « à l'image près » : chaque grain part dès que son heure est passée.
	while _i < _evts.size() and _evts[_i].t <= _t + 0.0005:
		var ev: Dictionary = _evts[_i]
		var s := banque.flux(ev.grain)
		if s and _lecture:
			var a := Time.get_ticks_usec()
			_lecture.play_stream(s, 0.0, float(ev.db) - 6.0, float(ev.pitch))
			cout_play_usec += Time.get_ticks_usec() - a
			nb_grains += 1
		_i += 1
	if _i >= _evts.size() and _t >= _duree:
		_parle = false
		fini.emit()
