class_name MoteurDialogue
extends RefCounted
## Moteur de conversation du village (portage interactif de dialogues/moteur.py).
##
##   var e := moteur.commencer(id_habitant)   # {lignes: [{texte, emotion, tag}], options: [texte...], fin}
##   e = moteur.choisir(i)                   # i = rang de l'option choisie ; la dernière option est toujours « partir »
##
## La bibliothèque V9 (Donnees/charabia/dialogues_v9.json) fournit les scènes, les arbres de négociation,
## les raccords, les réponses variées et l'humour ; ce moteur choisit une scène adaptée à l'habitant,
## dose l'humour (directeur d'humour) et se souvient de ce qui a été dit (etat() / restaurer()).

const PARTIR := "See you around."
const EMOTIONS_SANS_BLAGUE := ["triste", "furieux", "agace", "decu"]
const TONS_DROLES := ["playful", "absurd", "humor"]
const STYLES_BON_PUBLIC := ["geek", "enthousiaste", "bon_public", "sarcastique", "naif", "papy_meme"]

var d: Dictionary
var tons: Dictionary
var rng := RandomNumberGenerator.new()
var jour := 0
var pnj := {}          # id -> {scenes: {id: jour}, dites: {texte: n}, humour, rencontres}
var joueur := {"entendues": [], "scenes": {}, "clins": {}, "domaines": {}, "gags": {}}
var scenes_par_pnj := {}
var noeuds: Dictionary
var conv := {}         # conversation en cours

func _init(chemin_v9: String = "", chemin_emotions: String = "", graine: int = 1) -> void:
	if chemin_v9 == "":
		chemin_v9 = CharabiaVoix.chemin_donnees("dialogues_v9.json")
	if chemin_emotions == "":
		chemin_emotions = CharabiaVoix.chemin_donnees("emotions.json")
	d = JSON.parse_string(FileAccess.get_file_as_string(chemin_v9))
	tons = JSON.parse_string(FileAccess.get_file_as_string(chemin_emotions)).tons_v8
	rng.seed = graine
	noeuds = d.deep_trees.V1.nodes
	for s in d.scenes:
		if not s.get("disponible", true):
			continue
		for i in s.get("habitants", []):
			var k := str(int(i))
			if not scenes_par_pnj.has(k):
				scenes_par_pnj[k] = []
			scenes_par_pnj[k].append(s)

# --- mémoire ------------------------------------------------------------------------------------
func _m(pid: String) -> Dictionary:
	if not pnj.has(pid):
		pnj[pid] = {"scenes": {}, "dites": {}, "humour": 0.0, "rencontres": 0}
	return pnj[pid]

func etat() -> Dictionary:
	return {"pnj": pnj, "joueur": joueur}

func restaurer(e: Dictionary) -> void:
	pnj = e.get("pnj", {})
	var j: Dictionary = e.get("joueur", {})
	for cle in joueur:
		if j.has(cle):
			joueur[cle] = j[cle]

func _entendue(texte: String) -> bool:
	return texte in joueur.entendues

func _noter(pid: String, texte: String) -> void:
	var m := _m(pid)
	m.dites[texte] = int(m.dites.get(texte, 0)) + 1
	joueur.entendues.append(texte)
	if joueur.entendues.size() > 80:
		joueur.entendues.pop_front()

func _hab(pid: String) -> Dictionary:
	return d.distribution.habitants.get(pid, {"nom": "?", "famille": "visiteurs", "public": "adulte", "style": "bon_public", "appetit": 0.4, "gouts": []})

# --- directeur d'humour ----------------------------------------------------------------------------
func appetit(pid: String) -> float:
	var p := _hab(pid)
	var m := _m(pid)
	return clampf(float(p.appetit) * (0.6 + 0.4 * minf(1.0, int(m.rencontres) / 3.0)) * (1 + 0.25 * float(m.humour)), 0.0, 1.0)

func _public_ok(q: Dictionary, p: Dictionary) -> bool:
	if not (p.public in q.public):
		return false
	if q.has("style") and q.style != p.style:
		return false
	return q.domaine in p.gouts or (q.domaine in ["memes", "jeux_video"] and p.public == "ado")

func _cle_domaine(dom: String) -> String:
	return "%d|%s" % [jour, dom]

func _clin_doeil(fonction: String, pid: String) -> String:
	if int(conv.budget_clin) <= 0 or conv.emotion in EMOTIONS_SANS_BLAGUE or conv.tendu:
		return ""
	var p := _hab(pid)
	var cands := []
	for q in d.humour.repliques:
		if q.fonction == fonction and _public_ok(q, p) and jour - int(joueur.clins.get(q.id, -99)) >= 7 \
				and int(joueur.domaines.get(_cle_domaine(q.domaine), 0)) < 3:
			cands.append(q)
	if cands.is_empty():
		return ""
	var proba := appetit(pid) * (1.6 if conv.joueur_drole else 1.0) * 0.9
	if rng.randf() >= proba:
		return ""
	var q: Dictionary = cands[rng.randi() % cands.size()]
	if rng.randf() > {1: 1.0, 2: 0.75, 3: 0.45}.get(int(q.intensite), 1.0):
		return ""
	joueur.clins[q.id] = jour
	joueur.domaines[_cle_domaine(q.domaine)] = int(joueur.domaines.get(_cle_domaine(q.domaine), 0)) + 1
	conv.budget_clin = int(conv.budget_clin) - 1
	return q.texte

func _reaction(pid: String) -> Dictionary:
	var p := _hab(pid)
	var m := _m(pid)
	var aime: bool = p.style in STYLES_BON_PUBLIC and float(p.appetit) >= 0.35
	m.humour = clampf(float(m.humour) + (0.7 if aime else -0.6), -2.0, 3.0)
	if rng.randf() > 0.35:
		return {}
	var rec: Dictionary = d.humour.receptions[p.style]
	var cle := "plat" if (conv.emotion in EMOTIONS_SANS_BLAGUE or conv.tendu) else ("rit" if aime and float(m.humour) > 0 else "poli")
	var pool := _frais(rec[cle])
	return {"texte": pool[rng.randi() % pool.size()], "emotion": {"rit": "joyeux", "poli": "neutre", "plat": "agace"}[cle], "tag": "reaction"}

func _frais(pool: Array) -> Array:
	var out := []
	for l in pool:
		if not _entendue(l):
			out.append(l)
	return out if not out.is_empty() else pool

func _relance(pid: String, fonction: String, origine) -> Dictionary:
	var q := _clin_doeil(fonction, pid)
	if q != "":
		return {"texte": q, "emotion": "moqueur", "tag": "clin"}
	var fam: String = _hab(pid).famille
	var pool: Array = []
	pool.append_array(d.relances.commun.get(fonction, []))
	pool.append_array(d.relances.familles.get(fam, {}).get(fonction, []))
	if origine != null and origine != "" and not (origine in pool):
		pool.append(origine)
	var m := _m(pid)
	var frais := []
	for l in pool:
		if int(m.dites.get(l, 0)) == 0 and not _entendue(l):
			frais.append(l)
	if frais.is_empty():
		frais = _frais(pool)
	return {"texte": frais[rng.randi() % frais.size()], "emotion": "au_revoir" if fonction == "depart" else "neutre", "tag": "relance"}

# --- choix de scène --------------------------------------------------------------------------------
func _poids(s: Dictionary, pid: String) -> float:
	var p := _hab(pid)
	if joueur.scenes.has(s.id) or jour - int(_m(pid).scenes.get(s.id, -99)) < 7:
		return 0.0
	var w := 1.0
	if s.source == "V1":
		w = 1.5 if p.famille in ["cartes", "brocante"] else 0.0
	elif s.role_normalized != "ambient_resident":
		w = 2.0
	if s.get("humour_pop", false):
		if conv.tendu:
			return 0.0
		var premier := int(_m(pid).rencontres) == 0
		w *= appetit(pid) * (1.0 + 0.6 * float(_m(pid).humour)) * (0.4 if premier else 1.0) * 1.6
	return maxf(w, 0.0)

func _gag(pid: String) -> Array:
	for g in d.humour.running_gags:
		var et: Array = joueur.gags.get(g.id, [0, -1])
		var etape := int(et[0])
		if etape < g.etapes.size() and int(g.etapes[etape].jour_min) <= jour and int(et[1]) < jour and str(int(g.etapes[etape].get("qui", -1))) == pid:
			return [g, etape]
	return []

# --- déroulé -----------------------------------------------------------------------------------------
func _ligne(pid: String, texte: String, emotion: String = "neutre", tag: String = "") -> Dictionary:
	_noter(pid, texte)
	return {"texte": texte, "emotion": emotion, "tag": tag}

func commencer(id_habitant: int, tendu: bool = false) -> Dictionary:
	var pid := str(id_habitant)
	conv = {"pid": pid, "phase": "", "budget_clin": 1, "emotion": "neutre", "joueur_drole": false, "tendu": tendu, "options": []}
	var lignes := []
	var g := _gag(pid)
	if not g.is_empty() and not tendu and rng.randf() < 0.45 + 0.5 * appetit(pid):
		var e: Dictionary = g[0].etapes[g[1]]
		joueur.gags[g[0].id] = [int(g[1]) + 1, jour]
		lignes.append(_ligne(pid, e.texte, "joyeux", "gag"))
		conv.phase = "gag"
		var opts := []
		for r in d.humour.reactions_gag.joueur:
			opts.append(r.texte)
		return _etape(lignes, opts)
	var cands: Array = scenes_par_pnj.get(pid, [])
	var poids := []
	var total := 0.0
	for s in cands:
		var w := _poids(s, pid)
		poids.append(w)
		total += w
	if total <= 0.0:
		var h: Dictionary = d.conditional_hubs.neighborhood_smalltalk
		lignes.append(_ligne(pid, _frais(h.get("npc_variantes", [h.npc]))[0], "neutre", "raccord"))
		return _raccord_options(lignes, "neighborhood_smalltalk")
	var r := rng.randf() * total
	var scene: Dictionary = cands[-1]
	for i in cands.size():
		r -= poids[i]
		if r < 0:
			scene = cands[i]
			break
	joueur.scenes[scene.id] = true
	_m(pid).scenes[scene.id] = jour
	conv.scene = scene
	conv.phase = "scene"
	lignes.append(_ligne(pid, scene.opening, "neutre", "scene_pop" if scene.get("humour_pop", false) else "scene"))
	var opts := []
	for c in scene.choices:
		opts.append(c.player)
	return _etape(lignes, opts)

func choisir(i: int) -> Dictionary:
	var pid: String = conv.pid
	var opts: Array = conv.options
	if i < 0 or i >= opts.size() - 1 or opts[i] == PARTIR:   # la dernière option : partir
		return _partir()
	var lignes := []
	match conv.phase:
		"gag":
			var rg: Dictionary = d.humour.reactions_gag
			var pool := _frais(rg.get("pnj_par_reaction", {}).get(opts[i], rg.pnj))
			lignes.append(_ligne(pid, pool[rng.randi() % pool.size()], "joyeux"))
			return _etape(lignes, [])
		"scene":
			var c: Dictionary = conv.scene.choices[i]
			conv.emotion = tons.get(c.get("tone", ""), "neutre")
			if c.get("tone", "") in TONS_DROLES:
				conv.joueur_drole = true
				var re := _reaction(pid)
				if not re.is_empty():
					lignes.append(_ligne(pid, re.texte, re.emotion, "reaction"))
			var fonction = d.relances.fonctions.get(c.player)
			if fonction and c.get("npc"):
				var rl := _relance(pid, fonction, c.npc)
				lignes.append(_ligne(pid, rl.texte, rl.emotion, rl.tag))
			elif c.get("npc"):
				lignes.append(_ligne(pid, c.npc, conv.emotion))
			if conv.scene.source == "V1" and c.get("deep_tree_node"):
				conv.phase = "arbre"
				conv.noeud = c.deep_tree_node
				return _etape(lignes, _textes_noeud(conv.noeud))
			var fups: Array = c.get("followups", [])
			if not fups.is_empty():
				conv.phase = "relance"
				conv.fups = fups
				var o := []
				for f in fups:
					o.append(f.player)
				return _etape(lignes, o)
			if c.get("suggested_next_hub") and rng.randf() < 0.45:
				return _raccord(lignes, c.suggested_next_hub)
			return _etape(lignes, [])
		"relance":
			var f: Dictionary = conv.fups[i]
			var fonction = d.relances.fonctions.get(f.player)
			if fonction:
				if fonction == "depart":
					return _partir_avec(lignes, f.player)
				var rl := _relance(pid, fonction, f.get("npc"))
				lignes.append(_ligne(pid, rl.texte, rl.emotion, rl.tag))
				return _etape(lignes, [])
			if f.get("npc"):
				lignes.append(_ligne(pid, f.npc, "neutre"))
				return _etape(lignes, [])
			var o := str(f.get("outcome", ""))
			return _raccord(lignes, o.substr(4) if o.begins_with("hub:") else "neighborhood_smalltalk")
		"raccord":
			var c: Dictionary = conv.hub.choices[i]
			var vs: Array = c.get("npc_variantes", [c.npc])
			var pool := _frais(vs)
			lignes.append(_ligne(pid, pool[rng.randi() % pool.size()], "neutre"))
			return _etape(lignes, [])
		"arbre":
			var n: Dictionary = noeuds[conv.noeud]
			var c: Dictionary = n.choices[i]
			if c.has("next"):
				conv.noeud = c.next
				lignes.append(_ligne(pid, noeuds[c.next].npc_line, tons.get(c.get("intent", ""), "neutre")))
				return _etape(lignes, _textes_noeud(conv.noeud))
			lignes.append(_ligne(pid, c.get("npc_reply", ""), "au_revoir" if c.get("ending", "") == "leave" else "neutre"))
			return _etape(lignes, [])
	return _partir()

func _textes_noeud(nid: String) -> Array:
	var o := []
	for c in noeuds[nid].choices:
		o.append(c.text)
	return o

func _raccord(lignes: Array, hub_id: String) -> Dictionary:
	var fam: String = _hab(conv.pid).famille
	if hub_id in ["role_related", "local_work_or_smalltalk", "shipping_and_daily_work"] and fam in ["enfants", "ados", "retraites", "visiteurs"]:
		hub_id = "neighborhood_smalltalk"
	var h: Dictionary = d.conditional_hubs.get(hub_id, d.conditional_hubs.polite_exit)
	var vs := _frais(h.get("npc_variantes", [h.npc]))
	lignes.append(_ligne(conv.pid, vs[rng.randi() % vs.size()], "neutre", "raccord"))
	return _raccord_options(lignes, hub_id)

func _raccord_options(lignes: Array, hub_id: String) -> Dictionary:
	var h: Dictionary = d.conditional_hubs.get(hub_id, d.conditional_hubs.polite_exit)
	conv.hub = h
	conv.phase = "raccord"
	var o := []
	for c in h.choices:
		o.append(c.player)
	return _etape(lignes, o)

func _etape(lignes: Array, options: Array) -> Dictionary:
	var o := options.duplicate()
	o.append(PARTIR)          # on peut toujours partir
	conv.options = o
	return {"lignes": lignes, "options": o, "fin": false}

func _partir() -> Dictionary:
	return _partir_avec([], PARTIR)

func _partir_avec(lignes: Array, _texte_joueur: String) -> Dictionary:
	var pid: String = conv.get("pid", "0")
	var rl := _relance(pid, "depart", null)
	lignes.append(_ligne(pid, rl.texte, "au_revoir", rl.tag))
	_m(pid).rencontres = int(_m(pid).rencontres) + 1
	conv.options = []
	return {"lignes": lignes, "options": [], "fin": true}
