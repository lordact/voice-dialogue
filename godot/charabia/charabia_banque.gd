class_name CharabiaBanque
extends RefCounted
## Banque de grains d'un profil (res://banque/<profil>/), chargée à la demande.
## Grains en WAV importés en QOA (compressés en mémoire, décodage quasi gratuit).

## Où chercher : d'abord les banques empaquetées (une par profil), sinon les dossiers de grains.
static var dossiers_packs := ["res://Audio/charabia/", "res://banque_pack/"]
const RACINE := "res://banque/"
static var _banques := {}

var pid: String
var durees := {"syllabes": {}, "vocalises": {}, "inventaire": []}
var _flux := {}
var ok := false
var extension := "wav"
var pack: CharabiaPack
var chemin_pack := ""

static func pour(profil_id: String) -> CharabiaBanque:
	if not _banques.has(profil_id):
		_banques[profil_id] = CharabiaBanque.new(profil_id)
	return _banques[profil_id]

## Libère les banques (changement de niveau, fermeture du jeu).
static func vider() -> void:
	_banques.clear()
	CharabiaSequenceur._re_cache.clear()

func _init(profil_id: String) -> void:
	pid = profil_id
	for d in dossiers_packs:
		if ResourceLoader.exists(d + pid + ".res"):
			chemin_pack = d + pid + ".res"
			break
	if chemin_pack != "":
		pack = load(chemin_pack)
		_lire_index(pack.index)
		return
	var chemin := RACINE + pid + "/index.json"
	if not FileAccess.file_exists(chemin):
		push_warning("Charabia : banque absente pour " + pid)
		return
	_lire_index(JSON.parse_string(FileAccess.get_file_as_string(chemin)))

func _lire_index(idx: Dictionary) -> void:
	for nom in idx.syllabes:
		durees.syllabes[nom] = [float(idx.syllabes[nom].duree), float(idx.syllabes[nom].attaque)]
	for typ in idx.vocalises:
		durees.vocalises[typ] = idx.vocalises[typ]
	durees.inventaire = idx.get("inventaire", [])
	extension = str(idx.get("format", "ogg"))
	ok = true

var _en_attente := {}

func _chemin(grain: String) -> String:
	var fichier: String
	if grain.begins_with("syl:"):
		fichier = grain.substr(4)
	else:
		var rest := grain.substr(4)
		var cut := rest.rfind(":")
		fichier = rest.substr(0, cut) + "_" + rest.substr(cut + 1)
	return RACINE + pid + "/" + fichier + "." + extension

func grains() -> Array:
	var l := []
	for nom in durees.syllabes:
		l.append("syl:" + nom)
	for typ in durees.vocalises:
		for k in durees.vocalises[typ].size():
			l.append("voc:%s:%d" % [typ, k])
	return l

## Précharge tous les grains du profil en tâche de fond (à appeler quand un habitant
## de ce profil s'approche du joueur) : évite les pics de chargement au premier mot.
func precharger() -> void:
	if pack:
		return   # une banque empaquetée est chargée d'un bloc
	for g in grains():
		if not _flux.has(g) and not _en_attente.has(g):
			_en_attente[g] = _chemin(g)
			ResourceLoader.load_threaded_request(_en_attente[g], "AudioStream")

func prechargement_fini() -> bool:
	for g in _en_attente.keys():
		var st := ResourceLoader.load_threaded_get_status(_en_attente[g])
		if st == ResourceLoader.THREAD_LOAD_IN_PROGRESS:
			return false
		_flux[g] = ResourceLoader.load_threaded_get(_en_attente[g]) if st == ResourceLoader.THREAD_LOAD_LOADED else null
		_en_attente.erase(g)
	return true

## "syl:ta_plat" ou "voc:rire:1" -> AudioStream (null si le fichier manque).
func flux(grain: String) -> AudioStream:
	if pack:
		return pack.grains.get(grain)
	if _flux.has(grain):
		return _flux[grain]
	var chemin := _chemin(grain)
	if _en_attente.has(grain):
		_en_attente.erase(grain)
		_flux[grain] = ResourceLoader.load_threaded_get(chemin)  # attend la fin de ce seul fichier
		return _flux[grain]
	var s: AudioStream = load(chemin) if ResourceLoader.exists(chemin) else null
	_flux[grain] = s
	return s
