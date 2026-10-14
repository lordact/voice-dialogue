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

	var it := interjection(texte, emotion)
	var voc_tete: String = it[0]
	var reste: String = it[1]
	var motif := normaliser(texte)
	var graine := fnv1a(motif)
	var am := Alea.new(graine)
	var occ: int = loc.occurrences.get(motif, 0)
	loc.occurrences[motif] = occ + 1
	var av := Alea.new(graine ^ fnv1a("%s#%d#%d" % [loc.pid, loc.ident, occ]) ^ ((loc.repliques * 2654435761) & M32))

	var consonnes := []
	for c in p.consonnes:
		consonnes.append([c, p.consonnes[c]])
	var voyelles := []
	for v in p.voyelles:
		voyelles.append([v, p.voyelles[v]])
	var dures := []
	for c in p.consonnes:
		if c != "" and c in "ptkbd":
			dures.append(c)
	if dures.is_empty():
		dures = ["t"]

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

	var segs := segments(reste)
	if segs.is_empty() and avant.is_empty():
		segs = [[PackedStringArray(["mm"]), "."]]
	var budget := []
	var total := 0
	for sg in segs:
		var n_eng := 0
		for m in sg[0]:
			n_eng += syllabes_anglais(m)
		var b := maxi(1, arrondi(n_eng * float(p.densite)))
		budget.append(b)
		total += b
	if total > 16:
		for i in budget.size():
			budget[i] = maxi(1, arrondi(budget[i] * 16.0 / total))

	var fin_emotion = e.get("fin")
	var tremble := float(e.get("tremble", 0)) * k
	var calme := not (emotion in ["furieux", "agace", "ravi", "joyeux", "surpris"])
	var hesite := maxf(float(e.get("hesite", 0)) * k, float(p.get("tics", {}).get("euh", 0)) * (0.5 if calme else 0.1))
	var pause_chiffre := float(p.get("pause_avant_chiffre", 0))
	var musical := float(p.get("musical", 0.5))
	var legato := float(p.get("legato", 0.035))
	var amplitude := 4.0 * etendue
	var sauts_fin := {"chute": -3.0, "montee": 6.0, "exclamation": -3.5, "suspendue": 0.0,
		"continuation": 2.0, "chantee": -2.5, "chute_montee": 3.0}

	for si in segs.size():
		var mots: PackedStringArray = segs[si][0]
		var ponct: String = segs[si][1]
		var n: int = budget[si]
		var dernier_seg := si == segs.size() - 1
		var forme_fin: String = {"?": "montee", "!": "exclamation", "…": "suspendue", ",": "continuation"}.get(ponct, "chute")
		if dernier_seg and fin_emotion != null and ponct != "?":
			if forme_fin != "exclamation" or fin_emotion in ["chute", "chantee"]:
				forme_fin = fin_emotion
		var nb_mots := maxi(1, mini(n, arrondi(n / 2.2 + am.reel() * 0.8 - 0.2)))
		var tailles := []
		tailles.resize(nb_mots)
		tailles.fill(1)
		for _i in n - nb_mots:
			tailles[int(am.reel() * nb_mots)] += 1
		var accents := []
		for taille in tailles:
			accents.append(true)
			for _k in int(taille) - 1:
				accents.append(false)
		var syl_nombre := -1
		for i in mots.size():
			if _re(NOMBRES).search(mots[i]):
				syl_nombre = int(float(i) / maxi(1, mots.size()) * n)
				break
		# Mélodie en demi-tons : déclinaison, arc vers un sommet, accents, gamme pentatonique.
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
		var j := 0
		for wi in tailles.size():
			var taille: int = tailles[wi]
			for s in taille:
				var c := am.pondere(consonnes)
				var v := am.pondere(voyelles)
				if float(e.dures) * k > av.reel():
					c = dures[int(av.reel() * dures.size())]
				var debut_st: float = cibles[j]
				var fin_st: float
				var forme: String
				if j == n - 1:
					forme = "long"
					fin_st = debut_st + float(sauts_fin.get(forme_fin, -3.0)) * minf(1.5, etendue)
					if forme_fin == "chute_montee":
						debut_st -= 2.0
				else:
					forme = "plat" if s == 0 else "court"
					if debit < 0.85 and s == taille - 1:
						forme = "long"
					fin_st = debut_st + 0.65 * (float(cibles[j + 1]) - debut_st)
				var nom := (c if c != "" else "_") + ("ee" if v == "é" else v) + "_" + forme
				var da: Array = durees.syllabes[nom]
				var gain := 1.5 if s == 0 else 0.0
				if syl_nombre >= 0 and j == syl_nombre:
					if pause_chiffre:
						etat.t += pause_chiffre * av.entre(0.9, 1.1)
					gain += 2.0
					debut_st += 1.0
				if forme_fin == "exclamation" and s == 0:
					gain += 1.5
				var base := f0 / float(p.f0) * av.entre(0.99, 1.01)
				var pitch := base * pow(2.0, debut_st / 12.0)
				var pitch_fin := base * pow(2.0, fin_st / 12.0)
				if tremble:
					pitch *= 1 + tremble * sin(etat.t * 31)
				pitch = minf(1.8, maxf(0.75, pitch))
				pitch_fin = minf(1.8, maxf(0.75, pitch_fin))
				var debut := maxf(0.0, etat.t - float(da[1]) / pitch * 0.5)
				evts.append({"t": debut, "grain": "syl:" + nom, "pitch": pitch, "pitch_fin": pitch_fin, "db": vol + gain})
				etat.t = debut + duree_glissee(float(da[0]), pitch, pitch_fin) - legato
				j += 1
				infos.syllabes += 1
			if wi < tailles.size() - 1:
				etat.t += av.entre(float(p.pause_mot[0]), float(p.pause_mot[1])) * pauses
				if hesite and av.reel() < hesite * 0.35:
					vocalise.call("euh", -3.0)
		if not dernier_seg:
			etat.t += av.entre(float(p.pause_phrase[0]), float(p.pause_phrase[1])) * pauses * {"…": 1.6, ",": 0.55}.get(ponct, 1.0)

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
