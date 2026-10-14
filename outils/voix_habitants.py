"""Attribue un profil vocal à chaque habitant du Village_Demo -> donnees/voix_habitants.json.

Règles : âge (enfant, ado, adulte, senior), sexe (registre médium pour les hommes,
médium-aigu pour les femmes), famille de métier, puis exceptions tirées des histoires.
Deux habitants du même profil diffèrent encore de ±6 % de hauteur (CharabiaLocuteur).
"""
import json, os, sys

RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.join(RACINE, 'dialogues'))
from distribution import distribution

CHOIX = {  # (famille, sexe) -> profils possibles, attribués à tour de rôle
    ('cafe', 'M'): ['cuisinier_jovial', 'pro_presse'], ('cafe', 'F'): ['sarcastique', 'vendeuse_bavarde'],
    ('commerce', 'M'): ['commercant_blase', 'cuisinier_jovial'], ('commerce', 'F'): ['vendeuse_bavarde', 'parent_chaleureux'],
    ('services_publics', 'M'): ['agent_officiel', 'pro_presse'], ('services_publics', 'F'): ['parent_chaleureux', 'pro_presse'],
    ('secours', 'M'): ['grand_gaillard', 'agent_officiel'], ('secours', 'F'): ['agent_officiel', 'parent_chaleureux'],
    ('cartes', 'M'): ['collectionneur_methodique', 'revendeur_assure'], ('cartes', 'F'): ['reveuse_artiste', 'voisin_discret'],
    ('brocante', 'M'): ['commercant_blase', 'grand_gaillard', 'cuisinier_jovial'], ('brocante', 'F'): ['vendeuse_bavarde', 'parent_chaleureux'],
    ('techniques', 'M'): ['grand_gaillard', 'commercant_blase', 'pro_presse'], ('techniques', 'F'): ['voisin_discret', 'pro_presse'],
    ('visiteurs', 'M'): ['pro_presse', 'voisin_discret'], ('visiteurs', 'F'): ['reveuse_artiste', 'vendeuse_bavarde'],
}
EXCEPTIONS = {
    73: 'revendeur_assure', 54: 'revendeur_nerveux', 79: 'collectionneur_methodique', 19: 'sarcastique', 85: 'sarcastique',
    34: 'cuisinier_jovial', 30: 'cuisinier_jovial', 96: 'pro_presse', 43: 'agent_officiel', 5: 'grand_gaillard',
    66: 'grand_gaillard', 61: 'dame_distinguee', 100: 'dame_distinguee', 28: 'vieil_habitue', 52: 'reveuse_artiste',
    65: 'voisin_discret', 86: 'pro_presse', 87: 'agent_officiel', 46: 'pro_presse', 23: 'parent_chaleureux', 38: 'collectionneur_methodique',
}


def attribuer():
    dist = distribution()
    hs = json.load(open(os.path.join(RACINE, 'donnees', 'habitants_village_demo.json'), encoding='utf-8'))
    compteurs, out = {}, {}
    for h in hs:
        i, age, sexe = h['id'], h['age'], h['sexe']
        p = dist['habitants'][str(i)]
        if i in EXCEPTIONS:
            pid = EXCEPTIONS[i]
        elif age < 13:
            pid = 'enfant'
        elif age < 20:
            pid = 'ado_surexcite' if p['style'] in ('geek', 'enthousiaste', 'sarcastique') else 'voisin_discret'
        elif age >= 62 and p['famille'] in ('retraites', 'brocante', 'cartes', 'visiteurs'):
            pid = 'dame_distinguee' if sexe == 'F' else 'vieil_habitue'
        else:
            cles = CHOIX.get((p['famille'], sexe), ['pro_presse'])
            n = compteurs.get((p['famille'], sexe), 0)
            compteurs[(p['famille'], sexe)] = n + 1
            pid = cles[n % len(cles)]
        out[str(i)] = pid
    return out


if __name__ == '__main__':
    voix = attribuer()
    json.dump(voix, open(os.path.join(RACINE, 'donnees', 'voix_habitants.json'), 'w', encoding='utf-8'), indent=1)
    import collections
    print(collections.Counter(voix.values()).most_common())
