"""Tests du charabia (python3 tests/test_charabia.py).
JEU=<projet Godot Card Hustle> active la comparaison avec les 10 voix d'origine."""
import json, os, re, subprocess, sys
import numpy as np

RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
sys.path.insert(0, os.path.join(RACINE, 'charabia'))
import noyau
import sequenceur as sq
from banque import BanqueProfil, charger_profils

PROFILS = charger_profils(os.path.join(RACINE, 'donnees', 'profils_voix.json'))
EMOTIONS = json.load(open(os.path.join(RACINE, 'donnees', 'emotions.json'), encoding='utf-8'))['emotions']
_BANQUES = {}
echecs, controles = [], 0


def verifier(ok, quoi):
    global controles
    controles += 1
    if not ok:
        echecs.append(quoi)
        print('ÉCHEC :', quoi)


def durees(pid):
    if pid not in _BANQUES:
        b = BanqueProfil(pid, PROFILS[pid])
        _BANQUES[pid] = {'syllabes': {k: (len(s) / noyau.SR, a) for k, (s, a) in b.syllabes.items()},
                         'vocalises': {k: [len(x) / noyau.SR for x in l] for k, l in b.vocalises.items()}}
    return _BANQUES[pid]


def dire(pid, texte, emotion='neutre', loc=None, intensite=.7, ident=1):
    loc = loc or sq.Locuteur(pid, PROFILS[pid], ident)
    return sq.partition(texte, loc, emotion, EMOTIONS, durees(pid), intensite)


def tetes(evts):
    """Syllabes jouées sans leur forme mélodique : 'ta_monte_long' -> 'ta', '_u_plat' -> '_u'."""
    return [re.sub(r'_(plat|monte|descend)(_long)?$', '', e['grain'][4:]) for e in evts if e['grain'].startswith('syl:')]


def test_origine():
    jeu = os.environ.get('JEU')
    if not jeu:
        print('(voix d’origine non comparées : JEU non défini)')
        return
    for i in range(10):
        b = subprocess.run(['ffmpeg', '-v', 'error', '-i', os.path.join(jeu, 'Audio', 'voice_%d.ogg' % i), '-f', 's16le',
                            '-ac', '1', '-ar', '44100', '-'], capture_output=True).stdout
        ref = np.frombuffer(b, np.int16) / 32768
        x = noyau.ligne_origine(i)
        n = min(len(x), len(ref))
        verifier(len(x) == len(ref) and np.corrcoef(x[:n], ref[:n])[0, 1] > .999, 'voice_%d reproduite' % i)


def test_determinisme_et_motif():
    a, _ = dire('vieil_habitue', 'Looks like rain, but my knees are not a reliable forecast.')
    b, _ = dire('vieil_habitue', 'Looks like rain, but my knees are not a reliable forecast.')
    verifier(a == b, 'même entrée, même partition')
    base = tetes(dire('vieil_habitue', 'They are usually dramatic.', 'neutre')[0])
    for emo in ('triste', 'joyeux', 'fatigue', 'ravi'):
        verifier(tetes(dire('vieil_habitue', 'They are usually dramatic.', emo)[0]) == base, 'motif conservé en %s' % emo)
    # colère, surprise : certaines consonnes se durcissent, mais voyelles et nombre de syllabes restent
    voy = lambda l: [x.lstrip('pbtdkmnlsfrch_') for x in l]
    for emo in ('furieux', 'surpris', 'agace'):
        t = tetes(dire('vieil_habitue', 'They are usually dramatic.', emo)[0])
        verifier(len(t) == len(base) and voy(t) == voy(base), 'voyelles et rythme conservés en %s' % emo)
    verifier(tetes(dire('enfant', 'They are usually dramatic.')[0]) != base, 'autre profil, autres sons')


def test_variation_et_alternance():
    loc = sq.Locuteur('pro_presse', PROFILS['pro_presse'], 86)
    e1, _ = dire('pro_presse', 'See you around.', 'au_revoir', loc)
    e2, _ = dire('pro_presse', 'See you around.', 'au_revoir', loc)
    verifier(tetes(e1) == tetes(e2), 'redite : même motif')
    verifier([round(e['t'], 4) for e in e1] != [round(e['t'], 4) for e in e2], 'redite : rythme légèrement différent')
    loc = sq.Locuteur('cuisinier_jovial', PROFILS['cuisinier_jovial'], 34)
    prises = []
    for i in range(12):
        ev, inf = dire('cuisinier_jovial', 'Line number %d, ha.' % i, 'joyeux', loc, 1.0)
        prises += [e['grain'] for e in ev if e['grain'].startswith('voc:rire:')]
    verifier(all(a != b for a, b in zip(prises, prises[1:])), 'deux rires de suite : prises différentes')
    verifier(len(prises) < 12, 'pas un rire à chaque réplique')


def test_longueur():
    court = dire('origine', 'Sure.')[1]
    long_ = dire('origine', 'Honestly, I could talk about this binder for hours, but the line behind you is getting longer and my coffee is getting colder by the minute.')[1]
    verifier(court['syllabes'] <= 2 and court['duree'] < 1.0, 'réplique courte, voix courte (%.2f s)' % court['duree'])
    verifier(long_['syllabes'] <= 18 and long_['duree'] < 7.0, 'réplique longue plafonnée (%d syl, %.2f s)' % (long_['syllabes'], long_['duree']))
    verifier(long_['duree'] > court['duree'] * 3, 'réplique longue plus longue')


def test_interjections_et_chiffres():
    ev, inf = dire('origine', 'Hmm.')
    verifier(len(ev) == 1 and ev[0]['grain'].startswith('voc:hmm'), '« Hmm. » = un seul bourdonnement')
    ev, _ = dire('revendeur_nerveux', 'Uh... I think these shiny ones are worth a lot?', 'embarrasse')
    verifier(ev[0]['grain'].startswith('voc:euh'), '« Uh... » commence par une hésitation')
    ev, _ = dire('revendeur_assure', 'Two hundred. Not a dollar less.')
    premiere = next(e for e in ev if e['grain'].startswith('syl:'))
    verifier(premiere['t'] >= .3, 'silence avant la somme (%.2f s)' % premiere['t'])
    ev, _ = dire('enfant', 'Is it real?', 'curieux')
    syl = [e for e in ev if e['grain'].startswith('syl:')]
    verifier(syl[-1]['grain'].endswith('monte_long'), 'question : la fin monte')


def test_bibliotheque_v8():
    d = json.load(open(os.path.join(RACINE, 'donnees', 'CARD_HUSTLE_DIALOGUES_CONSOLIDES_V8.json'), encoding='utf-8'))
    lignes = set()
    for s in d['scenes']:
        lignes.add(s['opening'])
        for c in s['choices']:
            if c.get('npc'):
                lignes.add(c['npc'])
            for f in c.get('followups', []):
                if f.get('npc'):
                    lignes.add(f['npc'])
    for n in d['deep_trees']['V1']['nodes'].values():
        lignes.add(n['npc_line'])
    lignes = sorted(lignes)
    pids, emos = list(PROFILS), list(EMOTIONS)
    pire, vides = 0.0, 0
    for i, l in enumerate(lignes):
        ev, inf = dire(pids[i % len(pids)], l, emos[i % len(emos)], ident=i)
        vides += not ev
        pire = max(pire, inf['duree'])
    verifier(vides == 0, 'aucune réplique V8 muette (%d)' % vides)
    verifier(pire < 8.0, 'durée maximale raisonnable sur %d répliques V8 (%.2f s)' % (len(lignes), pire))
    print('  %d répliques V8 uniques, pire durée %.2f s' % (len(lignes), pire))


if __name__ == '__main__':
    for t in [test_origine, test_determinisme_et_motif, test_variation_et_alternance, test_longueur,
              test_interjections_et_chiffres, test_bibliotheque_v8]:
        t()
    print('%d contrôles, %d échecs' % (controles, len(echecs)))
    sys.exit(1 if echecs else 0)
