class_name CharabiaSequenceur
extends RefCounted
## Portage exact de charabia/sequenceur.py : du sous-titre anglais à une partition de grains.
## Même hachage (FNV-1a), même hasard (xorshift32), mêmes arrondis : pour une même entrée,
## Python et Godot produisent la même partition (vérifié par tests/test_parite.gd).

const M32 := 0xFFFFFFFF

class Alea:
	var x: int
	func _init(graine: int) -> void:
		x = graine & 0xFFFFFFFF
		if x == 0:
			x = 0x9E3779B9
	func suivant() -> int:
		x ^= (x << 13) & 0xFFFFFFFF
		x ^= x >> 17
		x ^= (x << 5) & 0xFFFFFFFF
		return x
	func reel() -> float:
		return float(suivant()) / 4294967296.0
	func entre(a: float, b: float) -> float:
		return a + (b - a) * reel()
	func pondere(poids: Array) -> String:
		var total := 0.0
		for kw in poids:
			total += float(kw[1])
		var r := reel() * total
		for kw in poids:
			r -= float(kw[1])
			if r < 0:
				return kw[0]
		return poids[poids.size() - 1][0]

static func arrondi(v: float) -> int:
	return int(floor(v + 0.5))

static func fnv1a(texte: String) -> int:
	var h := 0x811C9DC5
	for b in texte.to_utf8_buffer():
		h ^= b
		h = (h * 0x01000193) & M32
	return h

static var _re_cache := {}
static func _re(motif: String) -> RegEx:
	if not _re_cache.has(motif):
		_re_cache[motif] = RegEx.create_from_string(motif)
	return _re_cache[motif]

static func normaliser(texte: String) -> String:
	var t := texte.to_lower().replace("’", "'").replace("‘", "'").replace("“", "\"").replace("”", "\"")
	t = _re("[^a-z0-9$' ]+").sub(t, " ", true)
	return _re("\\s+").sub(t, " ", true).strip_edges()

const INTERJECTIONS := [
	["(uh+|um+|er+|erm)", "euh"], ["(hmm+|hm+)", ""], ["(mm+-?hm+)", "hmm_accord"],
	["(ha(ha)+|heh+|hah)", "rire"], ["(ugh+|argh+)", "grogne"], ["(wow+|whoa+)", "ooh"],
	["(pfft+|pff+)", "pfff"], ["(aw+|aww+)", "oh_decu"], ["(huh)", "hein"], ["(tsk|tch)", "tss"],
	["(oh+|ah+)", ""], ["(sigh)", "soupir"]]
const NOMBRES := "^(\\$?\\d[\\d,.]*\\$?|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|fifteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|dollars?|bucks?|cents?|half)$"

static func syllabes_anglais(mot: String) -> int:
	if _re(NOMBRES).search(mot) and _re("^\\$?\\d").search(mot):
		return maxi(1, _re("\\D").sub(mot, "", true).length())
	var m := _re("[^a-z]").sub(mot, "", true)
	if m.is_empty():
		return 0
	var n := _re("[aeiouy]+").search_all(m).size()
	if m.ends_with("e") and n > 1 and not (m.ends_with("le") or m.ends_with("ee")):
		n -= 1
	return maxi(1, n)

## [vocalise ou "", reste du texte]
static func interjection(texte: String, emotion: String) -> Array:
	var t := texte.strip_edges()
	for iv in INTERJECTIONS:
		var m := _re("(?i)^" + iv[0] + "\\b[\\s,.!?…—-]*").search(t)
		if m:
			var mot := m.get_string(1).to_lower()
			var voc: String = iv[1]
			if voc.is_empty():
				if mot.begins_with("h"):
					voc = "hmm_doute" if emotion in ["mefiant", "decu"] else "hmm_reflexion"
				elif emotion == "surpris":
					voc = "inspiration_surprise"
				elif emotion in ["decu", "triste"]:
					voc = "oh_decu"
				else:
					voc = "ah"
			return [voc, t.substr(m.get_end())]
	return ["", t]

## [[mots: PackedStringArray, ponctuation finale], ...]
static func segments(texte: String) -> Array:
	var out := []
	for m in _re("([^.!?,;:…—]+)([.!?,;:…—]+|$)").search_all(texte.replace("...", "…")):
		var mots := normaliser(m.get_string(1)).split(" ", false)
		if mots.is_empty():
			continue
		var p := m.get_string(2).strip_edges()
		var fin := "?" if "?" in p else "!" if "!" in p else "…" if "…" in p else "." if ("." in p or p.is_empty()) else ","
		out.append([mots, fin])
	return out

## Comme segments(), avec le rang de chaque mot dans le texte (pour le sous-titre mot à mot).
static func segments_mots(texte: String) -> Array:
	var jetons := []
	for m in _re("\\S+").search_all(texte.replace("...", "…")):
		jetons.append(m.get_string())
	var out := []
	var cour := []
	for i in jetons.size():
		var mot := normaliser(jetons[i]).replace(" ", "")
		if not mot.is_empty():
			cour.append([i, mot])
		var m := _re("[.!?,;:…—]+$").search(jetons[i])
		if m or i == jetons.size() - 1:
			var p := m.get_string() if m else ""
			if not cour.is_empty():
				var fin := "?" if "?" in p else "!" if "!" in p else "…" if "…" in p else "." if ("." in p or p.is_empty()) else ","
				out.append([cour, fin])
			cour = []
	return out

static func nb_jetons(texte: String) -> int:
	return _re("\\S+").search_all(texte.replace("...", "…")).size()

const MOTS_OUTILS := ["a", "an", "the", "to", "of", "in", "on", "at", "it", "i", "you", "is", "and", "or", "but", "my",
	"your", "me", "we", "he", "she", "they", "be", "for", "that", "this", "so", "do", "if", "as", "by",
	"with", "was", "are", "am", "can", "its", "it's", "i'm", "his", "her", "our", "them", "him", "us",
	"from", "just", "some", "what", "there", "than", "then", "not", "no", "up", "out", "all", "got",
	"get", "one", "have", "has", "had", "will", "don't", "i'll", "you're", "that's"]

static func moyennes(durees: Dictionary) -> Dictionary:
	if not durees.has("_moyennes"):
		var somme := {"court": 0.0, "plat": 0.0, "long": 0.0}
		var nb := {"court": 0, "plat": 0, "long": 0}
		for nom in durees.syllabes:
			var forme: String = nom.substr(nom.rfind("_") + 1)
			if somme.has(forme):
				somme[forme] += float(durees.syllabes[nom][0])
				nb[forme] += 1
		var m := {}
		for f in somme:
			m[f] = somme[f] / maxi(1, nb[f])
		durees["_moyennes"] = m
	return durees["_moyennes"]

static func _ajuster(val: float, neutre: float, k: float) -> float:
	return neutre + (val - neutre) * k

## Renvoie {"evenements": [{t, grain, pitch, db}], "infos": {...}}.
## durees = {"syllabes": {nom: [duree, attaque]}, "vocalises": {type: [durees]}}
static func partition(texte: String, loc: CharabiaLocuteur, emotion: String, emotions: Dictionary, durees: Dictionary,
		intensite: float = 0.7, fps: float = 0.0) -> Dictionary:
	var p: Dictionary = loc.profil
	var e: Dictionary = emotions[emotion]
	var k := 0.4 + 0.85 * intensite
	var hauteur := _ajuster(float(e.hauteur), 1, k)
	var etendue := float(p.etendue) * _ajuster(float(e.etendue), 1, k)
	var debit := _ajuster(float(e.debit), 1, k)
	var pauses := _ajuster(float(e.pauses), 1, k) / debit
	var vol := float(p.get("volume_db", 0)) + float(e.volume_db) * k
	var f0 := float(p.f0) * loc.decalage_f0 * hauteur

	var inter := interjection(texte, emotion)
	var voc_tete: String = inter[0]
	var reste: String = inter[1]
	var motif := normaliser(texte)
	var graine := fnv1a(motif)
	var am := Alea.new(graine)
	var occ: int = loc.occurrences.get(motif, 0)
	loc.occurrences[motif] = occ + 1
	var av := Alea.new(graine ^ fnv1a("%s#%d#%d" % [loc.pid, loc.ident, occ]) ^ ((loc.repliques * 2654435761) & M32))

	var pleines := []
	var particules := []
	var syl_dures := []
	for x in durees.inventaire:   # [nom, poids, particule, attaque dure]
		if x[2]:
			particules.append([x[0], x[1]])
		else:
			pleines.append([x[0], x[1]])
		if x[3]:
			syl_dures.append(x[0])
	if particules.is_empty():
		particules = pleines
	if syl_dures.is_empty():
		syl_dures = [pleines[0][0]]

	var evts := []
	var etat := {"t": 0.0}
	var infos := {"motif": motif, "graine": graine, "occurrence": occ, "vocalises": [], "syllabes": 0}

	var recent := func(typ: String) -> bool:
		for vn in loc.dernieres_vocalises:
			if vn[0] == typ and loc.repliques - int(vn[1]) <= 2:
				return true
		return false

	var vocalise := func(typ: String, gain_db: float = 0.0) -> void:
		if not durees.vocalises.has(typ):
			return
		var prises: Array = durees.vocalises[typ]
		var var_ := (int(loc.dernier_variant.get(typ, -1)) + 1) % prises.size()
		loc.dernier_variant[typ] = var_
		var pitch := loc.decalage_f0 * hauteur * av.entre(0.97, 1.03)
		evts.append({"t": etat.t, "grain": "voc:%s:%d" % [typ, var_], "pitch": pitch, "pitch_fin": pitch, "db": vol + gain_db - 1})
		etat.t += float(prises[var_]) / pitch + av.entre(0.08, 0.16) * pauses
		loc.dernieres_vocalises.append([typ, loc.repliques])
		infos.vocalises.append(typ)

	var tirer := func(liste: Array) -> String:
		for tp in liste:
			var pr: float = float(tp[1]) * (0.5 + intensite * 0.7) * (0.25 if recent.call(tp[0]) else 1.0)
			if av.reel() < pr:
				return tp[0]
		return ""

	var avant: String = voc_tete if not voc_tete.is_empty() else tirer.call(e.avant)
	if avant.is_empty() and emotion in ["neutre", "curieux", "mefiant", "fatigue", "decu", "agace", "moqueur"]:
		var tics: Dictionary = p.get("tics", {})
		var liste := []
		for x in ["soupir", "hmm", "pfff"]:
			if tics.has(x):
				liste.append([x, float(tics[x]) * 0.6])
		avant = tirer.call(liste)
		if avant == "hmm":
			avant = "hmm_reflexion"
	if not avant.is_empty():
		vocalise.call(avant)

	# Rythme calé sur le sous-titre anglais (voir charabia/sequenceur.py).
	var decalage := nb_jetons(texte) - nb_jetons(reste)
	var segs := segments_mots(reste)
	if segs.is_empty() and avant.is_empty():
		segs = [[[[-1, "mm"]], "."]]
	var lecture := float(reste.strip_edges().length()) / (float(p.get("lecture", 15.0)) * debit)
	lecture = minf(9.0, maxf(0.45, lecture))
	infos.lecture = lecture
	infos.mots = []
	for i in decalage:
		infos.mots.append([i, 0.0])
	var moy := moyennes(durees)
	var legato := float(p.get("legato", 0.035))
	var estimation := 0.0
	var plans := []
	for sg in segs:
		var pm := []
		for gm in sg[0]:
			var mot: String = gm[1]
			var outil := mot in MOTS_OUTILS
			var n_w := 1 if outil else mini(4, maxi(1, syllabes_anglais(mot)))
			pm.append([int(gm[0]), mot, outil, n_w])
			if outil:
				estimation += float(moy.court) - legato
			else:
				estimation += float(moy.plat) + (n_w - 1) * float(moy.court) - n_w * legato
		plans.append([pm, sg[1]])
	estimation /= 1.1
	estimation += (segs.size() - 1) * (float(p.pause_phrase[0]) + float(p.pause_phrase[1])) / 2
	var lecture_neutre := minf(9.0, maxf(0.45, float(reste.strip_edges().length()) / float(p.get("lecture", 15.0))))
	var rapport: float = lecture_neutre / maxf(0.05, estimation)
	if rapport < 0.85 or rapport > 1.15:
		for pl in plans:
			for w in pl[0]:
				if not w[2]:
					var f := maxf(rapport, 0.5) if rapport < 0.85 else minf(rapport, 1.6)
					w[3] = maxi(1, mini(5, arrondi(int(w[3]) * f)))

	var fin_emotion = e.get("fin")
	var tremble := float(e.get("tremble", 0)) * k
	var calme := not (emotion in ["furieux", "agace", "ravi", "joyeux", "surpris"])
	var hesite := maxf(float(e.get("hesite", 0)) * k, float(p.get("tics", {}).get("euh", 0)) * (0.5 if calme else 0.1))
	var pause_chiffre := float(p.get("pause_avant_chiffre", 0))
	var musical := float(p.get("musical", 0.5))
	var amplitude := 4.0 * etendue
	var sauts_fin := {"chute": -3.0, "montee": 6.0, "exclamation": -3.5, "suspendue": 0.0,
		"continuation": 2.0, "chantee": -2.5, "chute_montee": 3.0}

	var items := []
	for si in plans.size():
		var pm: Array = plans[si][0]
		var ponct: String = plans[si][1]
		var dernier_seg := si == plans.size() - 1
		var forme_fin: String = {"?": "montee", "!": "exclamation", "…": "suspendue", ",": "continuation"}.get(ponct, "chute")
		if dernier_seg and fin_emotion != null and ponct != "?":
			if forme_fin != "exclamation" or fin_emotion in ["chute", "chantee"]:
				forme_fin = fin_emotion
		var accents := []
		var outils := []
		var mot_de := []
		var premier := []
		var taille_de := []
		var chiffre := []
		for w in pm:
			var place := 0 if am.reel() < 0.7 else 1
			for s_ in int(w[3]):
				accents.append(not w[2] and s_ == mini(place, int(w[3]) - 1))
				outils.append(w[2])
				mot_de.append(w[0])
				premier.append(s_ == 0)
				taille_de.append(w[3])
				chiffre.append(s_ == 0 and _re(NOMBRES).search(w[1]) != null)
		var n := accents.size()
		var syl_nombre := chiffre.find(true)
		var sommet := am.entre(0.2, 0.6)
		var cibles := []
		for j in n:
			var x := float(j) / maxi(1, n - 1)
			var phase := am.reel()
			var micro := am.entre(-1, 1)
			var st := 1.0 - 1.8 * x + exp(-pow((x - sommet) / 0.3, 2)) * 1.0
			if accents[j]:
				st += 0.45
			if forme_fin == "exclamation":
				st += 0.9 * (1 - x)
			if forme_fin == "chantee" and n > 1 and j == n - 2:
				st += 0.8
			if emotion in ["joyeux", "moqueur", "ravi"]:
				st += 0.35 * sin(j * 1.9 + phase)
			st = st * amplitude + micro * 0.8
			cibles.append(st * (1 - musical) + pentatonique(st) * musical)
		for j in n:
			var nom_syl := am.pondere(particules if outils[j] else pleines)
			if float(e.dures) * k > av.reel():
				nom_syl = syl_dures[int(av.reel() * syl_dures.size())]
			var fin_mot: bool = j == n - 1 or premier[j + 1]
			var debut_st: float = cibles[j]
			var fin_st: float
			var forme: String
			if j == n - 1:
				forme = "long"
				fin_st = debut_st + float(sauts_fin.get(forme_fin, -3.0)) * minf(1.5, etendue)
				if forme_fin == "chute_montee":
					debut_st -= 2.0
			else:
				forme = "plat" if accents[j] else "court"
				if debit < 0.85 and fin_mot and not outils[j]:
					forme = "long"
				fin_st = debut_st + 0.65 * (float(cibles[j + 1]) - debut_st)
			var gain := 1.5 if accents[j] else 0.0
			var nombre := syl_nombre >= 0 and j == syl_nombre
			if nombre:
				gain += 2.0
				debut_st += 1.0
			if forme_fin == "exclamation" and accents[j]:
				gain += 1.5
			var base := f0 / float(p.f0) * av.entre(0.99, 1.01)
			var it := {"nom": nom_syl, "forme": forme, "pitch": minf(1.8, maxf(0.75, base * pow(2.0, debut_st / 12.0))),
				"pitch_fin": minf(1.8, maxf(0.75, base * pow(2.0, fin_st / 12.0))), "gain": gain, "accent": accents[j],
				"mot": mot_de[j], "premier": premier[j], "nombre": nombre, "pause": 0.0, "hesite": false,
				"mots_syl": taille_de[j], "fin_mot": fin_mot, "fin_seg": false}
			if fin_mot and j < n - 1:
				it.pause = av.entre(float(p.pause_mot[0]), float(p.pause_mot[1])) * pauses
				it.hesite = bool(hesite) and av.reel() < hesite * 0.35
			if j == n - 1 and not dernier_seg:
				it.pause = av.entre(float(p.pause_phrase[0]), float(p.pause_phrase[1])) * pauses * {"…": 1.6, ",": 0.55}.get(ponct, 1.0)
				it.fin_seg = true
			items.append(it)

	var duree_item := func(it: Dictionary, forme: String) -> float:
		return duree_glissee(float(durees.syllabes[it.nom + "_" + forme][0]), it.pitch, it.pitch_fin) - legato
	var euh := 0.0
	if durees.vocalises.has("euh"):
		euh = float(durees.vocalises.euh[0]) / hauteur + 0.12 * pauses
	var somme := 0.0
	for it in items:
		somme += duree_item.call(it, it.forme) + it.pause + (euh if it.hesite else 0.0) + (pause_chiffre if it.nombre else 0.0)
	var marge: float = lecture - (etat.t + somme)
	infos.marge_initiale = marge
	if marge > 0:
		var candidats := []
		for i in items.size():
			if items[i].accent and items[i].forme == "plat":
				candidats.append(i)
		candidats.sort_custom(func(a, b): return items[a].mots_syl > items[b].mots_syl or (items[a].mots_syl == items[b].mots_syl and a < b))
		for i in candidats:
			var gain_t: float = duree_item.call(items[i], "long") - duree_item.call(items[i], "plat")
			if marge < gain_t * 0.5:
				break
			items[i].forme = "long"
			marge -= gain_t
		var mots_trous := []
		var seg_trous := []
		for i in items.size() - 1:
			if items[i].fin_seg:
				seg_trous.append(items[i])
			elif items[i].fin_mot:
				mots_trous.append(items[i])
		if marge > 0 and not mots_trous.is_empty():
			var ajout := minf(0.1, marge * 0.6 / mots_trous.size())
			for it in mots_trous:
				it.pause += ajout
			marge -= ajout * mots_trous.size()
		if marge > 0 and not seg_trous.is_empty():
			var ajout2 := minf(0.45, marge / seg_trous.size())
			for it in seg_trous:
				it.pause += ajout2
	elif marge < 0:
		for it in items:
			if it.fin_seg:
				it.pause *= 0.6
			else:
				it.pause *= 0.2

	for it in items:
		if it.nombre and pause_chiffre:
			etat.t += pause_chiffre
		var nom: String = it.nom + "_" + it.forme
		var da: Array = durees.syllabes[nom]
		var pitch: float = it.pitch
		var pitch_fin: float = it.pitch_fin
		if tremble:
			pitch = minf(1.8, maxf(0.75, pitch * (1 + tremble * sin(etat.t * 31))))
		var debut := maxf(0.0, etat.t - float(da[1]) / pitch * 0.5)
		if it.premier and int(it.mot) >= 0:
			infos.mots.append([decalage + int(it.mot), debut])
		evts.append({"t": debut, "grain": "syl:" + nom, "pitch": pitch, "pitch_fin": pitch_fin, "db": vol + it.gain})
		etat.t = debut + duree_glissee(float(da[0]), pitch, pitch_fin) - legato
		infos.syllabes += 1
		etat.t += it.pause
		if it.hesite:
			vocalise.call("euh", -3.0)

	var apres: String = tirer.call(e.apres)
	if not apres.is_empty():
		etat.t += 0.04
		vocalise.call(apres)
	loc.repliques += 1
	if fps > 0:
		var pas := 1.0 / fps
		for ev in evts:
			ev.t = ceil(ev.t / pas - 1e-9) * pas
	var fin := 0.0
	for ev in evts:
		fin = maxf(fin, ev.t + duree_grain(ev, durees))
	infos.duree = fin
	return {"evenements": evts, "infos": infos}

## Durée réelle d'un grain lu avec une hauteur qui glisse de p0 à p1.
static func duree_glissee(longueur: float, p0: float, p1: float) -> float:
	if absf(p1 - p0) < 1e-9:
		return longueur / p0
	return longueur * log(p1 / p0) / (p1 - p0)

## Demi-ton le plus proche de la gamme pentatonique majeure (0 2 4 7 9).
static func pentatonique(st: float) -> float:
	var octave: float = floor(st / 12.0)
	var reste: float = st - octave * 12.0
	var meilleur := 0.0
	for d in [0.0, 2.0, 4.0, 7.0, 9.0, 12.0]:
		if absf(reste - d) < absf(reste - meilleur):
			meilleur = d
	return octave * 12.0 + meilleur

static func duree_grain(ev: Dictionary, durees: Dictionary) -> float:
	var g: String = ev.grain
	if g.begins_with("syl:"):
		return duree_glissee(float(durees.syllabes[g.substr(4)][0]), float(ev.pitch), float(ev.pitch_fin))
	var rest := g.substr(4)
	var cut := rest.rfind(":")
	return float(durees.vocalises[rest.substr(0, cut)][int(rest.substr(cut + 1))]) / float(ev.pitch)
