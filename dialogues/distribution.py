"""Distribution des dialogues sur les vrais habitants du Village_Demo.

Pour chaque habitant : famille d'écriture, public (enfant, ado, adulte, senior), style d'humour,
goûts pop culture, appétit pour l'humour (0..1). Pour chaque rôle de la bibliothèque V8 : les
habitants qui peuvent le jouer (aucun habitant inventé). Les règles générales se déduisent de
l'âge et du métier ; les exceptions viennent des histoires des habitants (habitants.json).
"""
import json, os

RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')

FAMILLE_METIER = {
    'café': 'cafe', 'boulangerie': 'commerce', 'épicerie': 'commerce', 'pharmacie': 'commerce', 'coiffeuse': 'commerce', 'bricolage': 'commerce',
    'commercial': 'commerce', 'immobilier': 'commerce', 'mairie': 'services_publics', 'administration': 'services_publics',
    'poste': 'services_publics', 'bus': 'services_publics', 'livraison': 'services_publics', 'livreur': 'services_publics',
    'municipal': 'services_publics', 'événements': 'services_publics', 'enseignante': 'services_publics',
    'caserne': 'secours', 'police': 'secours', 'hôpital': 'secours', 'soins': 'secours',
    'retraité': 'retraites', 'retraitée': 'retraites', 'boutique': 'cartes', 'collectionneur': 'cartes',
    'collectionneuse': 'cartes', 'revendeur': 'cartes', 'vendeur': 'brocante', 'vendeuse': 'brocante',
    'électricien': 'techniques', 'mécanicien': 'techniques', 'réparateur': 'techniques', 'déchetterie': 'techniques',
    'éoliennes': 'techniques', 'jardinier': 'techniques', 'informatique': 'techniques', 'comptable': 'techniques',
    'extérieur': 'techniques', 'illustratrice': 'visiteurs', 'proche': 'visiteurs', 'visiteur': 'visiteurs',
    'visiteuse': 'visiteurs'}

# id : (style, appétit, goûts ajoutés) — tirés des histoires des habitants.
EXCEPTIONS = {
    19: ('sarcastique', .8, ['series', 'memes']), 85: ('pince_sans_rire', .6, ['series']), 43: ('serieux', .3, []),
    79: ('geek', .6, ['cartes', 'memes']), 68: ('geek', .75, ['jeux_societe']), 84: ('geek', .6, ['jeux_societe']),
    48: ('geek', .6, ['memes', 'jeux_video']), 10: ('geek', .7, ['jeux_video']), 35: ('geek', .7, ['jeux_video']),
    45: ('sarcastique', .6, []), 25: ('enthousiaste', .5, ['anime']), 38: ('geek', .55, ['cartes']),
    73: ('pince_sans_rire', .3, ['cartes']), 54: ('sarcastique', .5, ['cartes']), 71: ('serieux', .15, ['cartes']),
    82: ('serieux', .15, ['cartes']), 92: ('serieux', .2, []), 55: ('serieux', .25, []), 34: ('bon_public', .6, ['films']),
    83: ('bon_public', .5, ['films']), 20: ('bon_public', .5, ['films']), 28: ('bon_public', .5, []),
    27: ('papy_meme', .4, []), 32: ('pince_sans_rire', .5, []), 51: ('pince_sans_rire', .3, []), 61: ('papy_meme', .5, []),
    75: ('papy_meme', .4, ['cartes']), 86: ('pince_sans_rire', .4, []), 87: ('pince_sans_rire', .4, []),
    2: ('bon_public', .5, ['films']), 17: ('enthousiaste', .7, ['memes']), 18: ('sarcastique', .5, ['jeux_video']),
    97: ('enthousiaste', .5, []), 98: ('enthousiaste', .5, []), 52: ('enthousiaste', .5, ['anime']),
    90: ('serieux', .2, []), 15: ('serieux', .25, []), 7: ('enthousiaste', .6, ['series']), 22: ('geek', .55, ['jeux_video']),
    26: ('naif', .6, ['cartes']), 8: ('naif', .7, ['cartes']), 81: ('bon_public', .35, ['cartes']), 66: ('pince_sans_rire', .35, []),
    95: ('pince_sans_rire', .45, []), 46: ('serieux', .3, []), 99: ('pince_sans_rire', .3, []), 100: ('papy_meme', .45, ['films']),
}

# Rôle V8 -> habitants (métiers, ids, ou groupes d'âge). None = rôle sans habitant possible.
ROLES = {
    'ambient_resident': 'adultes', 'neighbor': 'adultes', 'cafe_regular': 'adultes', 'friend': 'jeunes', 'parent': 'parents',
    'dad': [2, 34, 48, 37, 38, 14, 69], 'roommate': [17, 18, 19], 'student': 'ados', 'teenager': 'ados', 'fashion_teen': 'ados',
    'child': 'enfants', 'basketball_player': 'ados+', 'school_friend': 'ados', 'parent_at_home': [1, 2],
    'baker': [30, 96], 'cafe_owner': [83, 34, 19, 22], 'barista': [19, 22, 7], 'radio_host': [19, 22],
    'grocer': [6, 9], 'shopkeeper': [6, 9, 30], 'shop_employee': [22, 38, 9], 'clothing_clerk': [59, 64], 'pharmacist': [49],
    'postal_worker': [86, 12], 'post_worker': [86], 'delivery_driver': [88, 17], 'bus_driver': [87, 32], 'taxi_driver': [87],
    'police_officer': [43, 85], 'police': [43, 85], 'night_guard': [85, 43], 'firefighter': [5, 84],
    'mayor': [1, 29, 92], 'mayor_clerk': [29, 92, 1], 'office_worker': [55, 24, 48], 'teacher': [33], 'science_teacher': [33],
    'librarian': [62, 13], 'gardener': [37], 'farmer': [37], 'zookeeper': [99, 37], 'lifeguard': None, 'sailor': 'adultes',
    'car_mechanic': [18, 3], 'mechanic': [18, 3, 40], 'electrician': [14], 'repair_worker': [40], 'maintenance_worker': [53, 91],
    'construction_worker': [53, 91, 47], 'traffic_worker': [47, 53], 'cleaner': [41], 'woodworker': [40],
    'tech_hobbyist': [48, 24], 'hobbyist': 'adultes', 'boardgame_fan': [68, 84, 39], 'comic_fan': [38, 68],
    'gym_regular': 'adultes', 'hiker': [99, 98, 94], 'dog_walker': 'adultes', 'dog_owner': 'adultes', 'cat_owner': 'adultes',
    'tourist': [97, 98, 99, 100], 'park_regular': 'seniors', 'old_timer': 'seniors', 'elder': 'seniors', 'grandparent': 'seniors',
    'retired_neighbor': 'seniors', 'collector': 'collectionneurs', 'card_collector': 'collectionneurs', 'old_collector': [75, 81, 71],
    'card_shop_worker': [23, 38], 'card_shop_owner': [23], 'card_seller': 'vendeurs_cartes', 'casual_seller': 'vendeurs',
    'flea_vendor': 'vendeurs', 'market_vendor': 'vendeurs', 'antique_seller': [61, 57, 67], 'parking_vendor': [54, 66, 69],
    'parking_seller': [54, 66, 69], 'parent_vendor': [59, 69, 70], 'professional_reseller': [54, 73], 'online_buyer': None,
    'regular_customer': [71, 82, 72, 81], 'flower_seller': [64, 57],
}


def charger_habitants():
    return json.load(open(os.path.join(RACINE, 'donnees', 'habitants_village_demo.json'), encoding='utf-8'))


def public_de(age):
    return 'enfant' if age < 13 else 'ado' if age < 20 else 'adulte' if age < 60 else 'senior'


def profil_humour(h):
    age, metier = int(h['age']), h['metier']
    public = public_de(age)
    if metier in ('école', 'études', 'formation'):
        famille = 'enfants' if age < 13 else 'ados'
    else:
        famille = FAMILLE_METIER.get(metier, 'visiteurs')
    style, appetit, gouts = {'enfant': ('naif', .6, ['jeux_video', 'cartes']),
                             'ado': ('geek', .65, ['jeux_video', 'memes', 'series', 'anime']),
                             'adulte': ('bon_public', .45, ['films', 'series'] + (['jeux_video', 'memes'] if age < 45 else [])),
                             'senior': ('papy_meme', .35, ['films', 'series'])}[public]
    gouts = list(gouts)
    if famille == 'cartes':
        gouts.append('cartes')
    if h['id'] in EXCEPTIONS:
        style, appetit, plus = EXCEPTIONS[h['id']]
        gouts += [g for g in plus if g not in gouts]
    return {'id': h['id'], 'nom': h['nom'], 'age': age, 'metier': metier, 'famille': famille, 'public': public,
            'style': style, 'appetit': appetit, 'gouts': gouts}


def candidats(role, habitants):
    regle = ROLES.get(role, 'adultes')
    if regle is None:
        return []
    if isinstance(regle, list):
        return regle
    hs = habitants
    if regle == 'adultes':
        return [h['id'] for h in hs if 20 <= h['age']]
    if regle == 'jeunes':
        return [h['id'] for h in hs if 15 <= h['age'] < 35]
    if regle == 'parents':
        return [h['id'] for h in hs if 30 <= h['age'] < 60 and h['maison'] > 0]
    if regle == 'ados':
        return [h['id'] for h in hs if 13 <= h['age'] < 20]
    if regle == 'ados+':
        return [h['id'] for h in hs if 13 <= h['age'] < 40]
    if regle == 'enfants':
        return [h['id'] for h in hs if h['age'] < 13]
    if regle == 'seniors':
        return [h['id'] for h in hs if h['age'] >= 60]
    if regle == 'collectionneurs':
        return [h['id'] for h in hs if h['metier'] in ('collectionneur', 'collectionneuse')]
    if regle == 'vendeurs':
        return [h['id'] for h in hs if h['metier'] in ('vendeur', 'vendeuse')]
    if regle == 'vendeurs_cartes':
        return [h['id'] for h in hs if h['metier'] in ('vendeur', 'vendeuse', 'revendeur', 'boutique')]
    return []


def distribution():
    hs = charger_habitants()
    return {'habitants': {str(h['id']): profil_humour(h) for h in hs},
            'roles': {r: candidats(r, hs) for r in ROLES}}


if __name__ == '__main__':
    d = distribution()
    import collections
    print(collections.Counter(p['famille'] for p in d['habitants'].values()))
    print(collections.Counter(p['style'] for p in d['habitants'].values()))
    print({r: len(v) for r, v in d['roles'].items() if len(v) == 0})
