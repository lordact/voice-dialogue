extends SceneTree
const ECONOMY := preload("res://addons/economy/economy.gd")
func _init() -> void:
	var e: Node = ECONOMY.new()
	e.setup(7, EcoConfig.DEFAULT_ECONOMY_PATH, {})
	e.load_catalog_file("res://Economie/sample_data/catalog.json")
	e.set_seller("npc:73", "reseller")
	var lot: Dictionary = e.flea_stall("stall_1", "npc:73")[0]
	var out := {"price": lot.price, "size": lot.size, "lines": lot.get("lines", {}), "rounds": []}
	var a: Dictionary = e.haggle_offer(lot, 12.0)
	out.rounds.append({"bid": 12.0, "res": a})
	var b: Dictionary = e.haggle_offer(lot, 31.0)
	out.rounds.append({"bid": 31.0, "res": b})
	var c: Dictionary = e.haggle_offer(lot, float(b.price))
	out.rounds.append({"bid": b.price, "res": c})
	print("JSON:" + JSON.stringify(out))
	e.free()
	quit()
