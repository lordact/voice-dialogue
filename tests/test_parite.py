"""Compare les partitions Python et Godot (même texte, même profil, même mémoire).
python3 tests/test_parite.py CHEMIN/parite_godot.json"""
import json, os, sys
RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.join(RACINE, 'charabia'))
import sequenceur as sq


def durees_index(pid):
    idx = json.load(open(os.path.join(RACINE, 'banque', pid, 'index.json')))
    return {'syllabes': {k: (v['duree'], v['attaque']) for k, v in idx['syllabes'].items()}, 'vocalises': idx['vocalises']}


def partitions_python():
    profils = json.load(open(os.path.join(RACINE, 'donnees', 'profils_voix.json'), encoding='utf-8'))['profils']
    emotions = json.load(open(os.path.join(RACINE, 'donnees', 'emotions.json'), encoding='utf-8'))['emotions']
    cas = json.load(open(os.path.join(RACINE, 'godot', 'tests', 'cas_parite.json'), encoding='utf-8'))['cas']
    out = []
    for c in cas:
        loc = sq.Locuteur(c['profil'], profils[c['profil']], c['ident'], 1 + (((c['ident'] * 37) % 11) - 5) * .012)
        d = durees_index(c['profil'])
        out.append([sq.partition(t, loc, e, emotions, d, i, fps=60) for t, e, i in c['repliques']])
    return out


if __name__ == '__main__':
    godot = json.load(open(sys.argv[1]))
    py = partitions_python()
    ecarts, total = 0, 0
    for gc, pc in zip(godot, py):
        for g, (pe, pi) in zip(gc, pc):
            ge = g['evenements']
            total += 1
            same = len(ge) == len(pe) and all(a['grain'] == b['grain'] and abs(a['t'] - b['t']) < 1e-9 and
                                              abs(a['pitch'] - b['pitch']) < 1e-9 and abs(a['pitch_fin'] - b['pitch_fin']) < 1e-9 and abs(a['db'] - b['db']) < 1e-9
                                              for a, b in zip(ge, pe))
            if not same:
                ecarts += 1
                print('ÉCART', pi['motif'])
                for a, b in list(zip(ge, pe))[:40]:
                    print('   G', a['grain'], round(a['t'], 4), round(a['pitch'], 4), '| P', b['grain'], round(b['t'], 4), round(b['pitch'], 4))
                print('   longueurs', len(ge), len(pe))
    print('%d/%d partitions identiques' % (total - ecarts, total))
    sys.exit(1 if ecarts else 0)
