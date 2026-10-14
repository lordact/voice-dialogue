"""Exporte la banque de grains de tous les profils pour Godot : banque/<profil>/*.ogg + index.json.

python3 charabia/exporter_banque.py [--profils a,b,c]
"""
import argparse, os, sys, time
sys.path.insert(0, os.path.dirname(__file__))
from banque import BanqueProfil, charger_profils

RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--profils', default='')
    args = ap.parse_args()
    profils = charger_profils(os.path.join(RACINE, 'donnees', 'profils_voix.json'))
    choix = args.profils.split(',') if args.profils else list(profils)
    total = 0
    for pid in choix:
        t0 = time.time()
        idx = BanqueProfil(pid, profils[pid]).exporter(os.path.join(RACINE, 'banque', pid))
        taille = sum(os.path.getsize(os.path.join(RACINE, 'banque', pid, f)) for f in os.listdir(os.path.join(RACINE, 'banque', pid)))
        total += taille
        print('%-26s %3d syllabes %2d vocalises  %6.0f Ko  %.1f s' % (pid, len(idx['syllabes']), len(idx['vocalises']), taille / 1024, time.time() - t0))
    print('total %.1f Mo' % (total / 1048576))
