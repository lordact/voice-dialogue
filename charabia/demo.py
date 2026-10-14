"""Démonstration audible A/B : ancien système (10 phrases fixes) / charabia enrichi.

python3 charabia/demo.py --jeu CHEMIN_DU_PROJET_GODOT --sortie demo/
  CHEMIN_DU_PROJET_GODOT : dossier contenant Audio/voice_0.ogg ... (les anciennes voix) et
  les ambiances birds/fountain/wind (CC0). Les répliques viennent de la bibliothèque V8 et
  du module Economy (négociation réellement calculée, voir donnees/negociation_economy.json).
"""
import argparse, json, os, subprocess, sys
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from noyau import SR
from banque import BanqueProfil, charger_profils, inventaire_compact
import sequenceur as sq
import mixage

ICI = os.path.dirname(os.path.abspath(__file__))
DONNEES = os.path.join(ICI, '..', 'donnees')

# Habitants réels du Village_Demo (Donnees/habitants.json) -> profil vocal.
DISTRIBUTION = {
    'felix':    ('Felix Romero', 86, 'pro_presse'),
    'antonio':  ('Antonio Garcia', 28, 'vieil_habitue'),
    'ava':      ('Ava Washington', 36, 'enfant'),
    'rosa':     ('Rosa Garcia', 27, 'dame_distinguee'),
    'bob':      ('Bob Foster', 47, 'grand_gaillard'),
    'derek':    ('Derek Moss', 73, 'revendeur_assure'),
    'brittany': ('Brittany Price', 19, 'sarcastique'),
    'marcus':   ('Marcus Washington', 34, 'cuisinier_jovial'),
    'paige':    ('Paige Turner', 65, 'voisin_discret'),
    'marlene':  ('Marlene Baxter', 57, 'vendeuse_bavarde'),
    'wade':     ('Wade Baxter', 58, 'commercant_blase'),
    'colin':    ('Colin Pierce', 79, 'collectionneur_methodique'),
    'trevor':   ('Trevor Hayes', 54, 'revendeur_nerveux'),
    'amber':    ('Amber Morgan', 52, 'reveuse_artiste'),
    'scott':    ('Scott Walker', 43, 'agent_officiel'),
    'dylan':    ('Dylan Brooks', 10, 'ado_surexcite'),
    'jennifer': ('Jennifer Parker', 6, 'parent_chaleureux'),
}

LIBELLES_EMOTION = {'neutre': 'neutral', 'curieux': 'curious', 'joyeux': 'happy', 'surpris': 'surprised',
                    'decu': 'disappointed', 'mefiant': 'wary', 'triste': 'sad', 'agace': 'annoyed',
                    'furieux': 'furious', 'moqueur': 'mocking', 'embarrasse': 'embarrassed', 'fatigue': 'tired',
                    'ravi': 'delighted', 'au_revoir': 'goodbye'}


def decalage_f0(ident):
    """Deux habitants du même profil n'ont pas tout à fait la même hauteur (±6 %)."""
    return 1 + (((ident * 37) % 11) - 5) * .012


class Studio:
    def __init__(self, jeu):
        self.profils = charger_profils(os.path.join(DONNEES, 'profils_voix.json'))
        self.emotions = json.load(open(os.path.join(DONNEES, 'emotions.json'), encoding='utf-8'))['emotions']
        self.banques, self.durees, self.locuteurs = {}, {}, {}
        self.jeu = jeu
        self.anciennes = [self._decoder(os.path.join(jeu, 'Audio', 'voice_%d.ogg' % i)) for i in range(10)]
        self.compteur_ancien = 0

    def _decoder(self, chemin):
        b = subprocess.run(['ffmpeg', '-v', 'error', '-i', chemin, '-f', 's16le', '-ac', '1', '-ar', str(SR), '-'],
                           capture_output=True, check=True).stdout
        return np.frombuffer(b, np.int16).astype(float) / 32768

    def banque(self, pid):
        if pid not in self.banques:
            b = BanqueProfil(pid, self.profils[pid])
            self.banques[pid] = b
            self.durees[pid] = {'syllabes': {k: (len(s) / SR, a) for k, (s, a) in b.syllabes.items()},
                                'vocalises': {k: [len(x) / SR for x in l] for k, l in b.vocalises.items()},
                'inventaire': inventaire_compact(b.inventaire)}
        return self.banques[pid]

    def locuteur(self, qui):
        if qui not in self.locuteurs:
            nom, ident, pid = DISTRIBUTION[qui] if qui in DISTRIBUTION else (qui, 0, qui)
            self.locuteurs[qui] = sq.Locuteur(pid, self.profils[pid], ident, decalage_f0(ident))
        return self.locuteurs[qui]

    def dire(self, qui, texte, emotion='neutre', intensite=.7):
        loc = self.locuteur(qui)
        b = self.banque(loc.pid)
        evts, infos = sq.partition(texte, loc, emotion, self.emotions, self.durees[loc.pid], intensite, fps=60)
        return mixage.rendre(evts, b), infos

    def ancien(self, qui, emotion='neutre', ambiant=False):
        """Reproduit AudioVillage.speak() / la voix d'ambiance de Scripts/audio_village.gd."""
        ident = DISTRIBUTION[qui][1] if qui in DISTRIBUTION else 1
        if ambiant:
            var = (ident + self.compteur_ancien) % 10
            pitch = .9 + (ident % 7) * .04
            db = -30 + 13  # l'ambiance est jouée 17 dB sous le dialogue ; on garde l'écart relatif
        else:
            var = (abs(ident) * 3 + self.compteur_ancien) % 10
            pitch = min(1.3, max(.8, .86 + (abs(ident) % 9) * .045 + (.08 if emotion == 'curieux' else 0)))
            db = 0
        self.compteur_ancien += 1
        return mixage.reechantillonner(self.anciennes[var], pitch) * 10 ** (db / 20) * .55


def ambiance(studio, cles, gains_db):
    fond = None
    for cle, g in zip(cles, gains_db):
        x = studio._decoder(os.path.join(studio.jeu, 'Audio', cle + '.ogg')) * 10 ** (g / 20)
        fond = x if fond is None else fond[:min(len(fond), len(x))] + x[:min(len(fond), len(x))]
    return fond


def construire(studio, etapes, ambiant=False, fond=None, fond_db=-30.0):
    """Construit la version « nouvelle » et la version « ancienne » d'une scène, même minutage.
    etapes : ('pnj', qui, texte, emotion, intensite, spatial) | ('joueur', texte) | ('note', texte)
             | ('pause', s) | ('coupe', s)  [le joueur passe la ligne après s secondes]"""
    neuf, vieux = mixage.Piste(), mixage.Piste()
    t = .5
    dernier_ancien = []   # sons de l'ancien système à couper quand une nouvelle réplique arrive
    coupe_suivante = None
    for et in etapes:
        kind = et[0]
        if kind == 'pause':
            t += et[1]
        elif kind == 'coupe':
            coupe_suivante = et[1]
        elif kind == 'note':
            neuf.titre(t, t + 2.2, '', et[1], note='ui'); vieux.titre(t, t + 2.2, '', et[1], note='ui')
            t += .4
        elif kind == 'joueur':
            lecture = 1.0 + .045 * len(et[1])
            neuf.titre(t, t + lecture, 'You', et[1], joueur=True); vieux.titre(t, t + lecture, 'You', et[1], joueur=True)
            t += lecture + .25
        elif kind == 'pnj':
            _, qui, texte, emotion, intensite, spatial = (list(et) + [None] * 6)[:6]
            intensite = .7 if intensite is None else intensite
            spatial = spatial or {}
            mono, infos = studio.dire(qui, texte, emotion, intensite)
            if coupe_suivante is not None:
                coupe = int(coupe_suivante * SR); f = int(.06 * SR)
                mono = mono[:coupe + f].copy(); mono[coupe:] *= np.linspace(1, 0, len(mono[coupe:]))
            if spatial.get('ambiant'):
                mono = mono * 10 ** (-6 / 20)   # l'ambiance reste sous le dialogue ciblé
            stereo = _placer(mono, spatial)
            neuf.poser(t, stereo)
            vx = studio.ancien(qui, emotion, ambiant=bool(spatial.get('ambiant')))
            if coupe_suivante is not None:
                vx = vx[:int(coupe_suivante * SR)] * 1.0
            vieux_st = _placer(vx, spatial)
            vieux.poser(t, vieux_st)
            nom = DISTRIBUTION.get(qui, (qui,))[0]
            duree = len(mono) / SR
            note = 'interrupted' if coupe_suivante is not None else ''
            lib = LIBELLES_EMOTION.get(emotion, emotion)
            neuf.titre(t, t + max(duree, 1.2), nom, texte, lib, note=note)
            vieux.titre(t, t + max(duree, 1.2), nom, texte, lib, note=note)
            t += duree + spatial.get('apres', .55)
            coupe_suivante = None
    fins = []
    neuf.fin = vieux.fin = t
    for piste in (neuf, vieux):
        piste.sons = _couper_chevauchements(piste.sons) if piste is vieux and not ambiant else piste.sons
        fins.append(mixage.egaliser_sonie(piste.mixer(fond, fond_db)))
    return fins, neuf.titres


def _couper_chevauchements(sons):
    """L'ancien lecteur de dialogue n'a qu'une voix : une nouvelle réplique coupe la précédente."""
    out = []
    for i, (t, s) in enumerate(sons):
        if i + 1 < len(sons):
            fin = int((sons[i + 1][0] - t) * SR)
            if 0 < fin < len(s):
                s = s[:fin].copy(); f = min(len(s), int(.01 * SR)); s[-f:] *= np.linspace(1, 0, f)[:, None]
        out.append((t, s))
    return out


def _placer(mono, spatial):
    if 'trajet' in spatial:
        d, p = spatial['trajet']
        return mixage.spatialiser_trajet(mono, d, p)
    return mixage.spatialiser(mono, spatial.get('distance', 1.5), spatial.get('pan', 0.0))


def ecrire_mp3(chemin, stereo):
    tmp = chemin + '.wav'
    from banque import ecrire_wav
    ecrire_wav(tmp, stereo)
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', tmp, '-c:a', 'libmp3lame', '-b:a', '96k', chemin], check=True)
    os.remove(tmp)


def scenes(studio):
    neg = json.load(open(os.path.join(DONNEES, 'negociation_economy.json'), encoding='utf-8'))
    a, b = neg['accord'], neg['depart']
    S = []
    # 1. Palette : la même réplique par les 17 profils.
    pal = []
    for pid, p in studio.profils.items():
        pal += [('note', '%s — %s' % (p['label_en'], pid)),
                ('pnj', pid, 'Looks like rain again. The clouds have a personal problem with this town.', 'neutre', .6), ('pause', .5)]
    S.append(('palette', 'Voice palette — 17 profiles + original, same line', 'Chaque profil dit la même réplique V2 (neutre). « origine » = réglage des voix actuelles, rejoué par le nouveau moteur.', pal, {}))
    # 2. Passant neutre (le facteur passe, puis on lui parle). Scène V3 postal_worker.busy_monday.
    S.append(('passant', 'Neutral passer-by — Felix the mail carrier', 'Felix passe en disant bonjour, le joueur l’arrête. Lignes V3 « postal_worker.busy_monday ».', [
        ('pnj', 'felix', 'Monday mornings bring everyone’s weekend parcels.', 'neutre', .5, {'trajet': ([7, 4, 2.5], [-.7, -.3, -.1])}),
        ('joueur', 'Is Monday the busiest?'),
        ('pnj', 'felix', 'Usually, yes.', 'neutre', .6),
        ('joueur', 'Any quieter time?'),
        ('pnj', 'felix', 'Late afternoon, unless a holiday is coming.', 'curieux', .4),
        ('joueur', 'I should get going.'),
        ('pnj', 'felix', 'See you around.', 'au_revoir', .7)], {}))
    # 3. Deux timbres opposés : Antonio (78 ans) et Ava (9 ans).
    S.append(('opposes', 'Opposite timbres — Antonio (78) and Ava (9)', 'Scènes V3 « park_regular.weather » et V6 « v6_041 ».', [
        ('pnj', 'antonio', 'Looks like rain, but my knees are not a reliable forecast.', 'fatigue', .5),
        ('joueur', 'Are they usually right?'),
        ('pnj', 'antonio', 'They are usually dramatic.', 'moqueur', .5),
        ('pause', .6),
        ('pnj', 'ava', 'I found a wooden box under the bench and thought it was treasure.', 'ravi', .8),
        ('joueur', 'Was it filled with legendary socks?'),
        ('pnj', 'ava', 'Worse. Gardening gloves.', 'decu', .8)], {}))
    # 4. Passants qui bavardent entre eux au parc (le joueur passe à côté), puis silence.
    loin = {'ambiant': True}
    S.append(('parc', 'Park chatter between residents — Rosa and Bob', 'Conversation entre PNJ reprise d’une scène V2, entendue en passant (distance 9 m → 5 m → 10 m), puis chacun reprend sa routine : 6 s de silence.', [
        ('pnj', 'rosa', 'Looks like rain again. The clouds have a personal problem with this town.', 'moqueur', .4, {**loin, 'distance': 8, 'pan': .55, 'apres': .35}),
        ('pnj', 'bob', 'Is it supposed to last?', 'curieux', .6, {**loin, 'distance': 6.5, 'pan': .35, 'apres': .35}),
        ('pnj', 'rosa', 'Forecast says until lunch, which means dinner.', 'moqueur', .6, {**loin, 'distance': 5.5, 'pan': .2, 'apres': .3}),
        ('pnj', 'bob', 'Ha! At this point the ducks should pay property tax.', 'joyeux', .8, {**loin, 'distance': 5, 'pan': -.05, 'apres': .4}),
        ('pnj', 'rosa', 'Oh, this town never runs out.', 'fatigue', .6, {**loin, 'distance': 7, 'pan': -.4, 'apres': .3}),
        ('pause', 6.0)], {'fond': (['birds', 'fountain', 'wind'], [-6, -14, -10]), 'fond_db': -24, 'ambiant': True}))
    # 5. Négociation (vrais résultats Economy : lowball -> counter -> accept).
    S.append(('negociation', 'Negotiation — Derek Moss, reseller (accepted)', 'Lot et prix calculés par addons/economy (profil « reseller »), répliques = lignes du profil. La voix suit le résultat (lowball → furieux, counter → méfiant, accept → ravi), elle ne décide rien.', [
        ('pnj', 'derek', neg['intro'], 'neutre', .6),
        ('joueur', 'What are you asking for the lot?'),
        ('note', 'Lot of %d cards — asking $%.2f' % (neg['taille'], neg['prix'])),
        ('pnj', 'derek', neg['prix_ligne'], 'mefiant', .4),
        ('joueur', 'I can do $%.2f.' % a[0]['offre']),
        ('pnj', 'derek', a[0]['ligne'], 'furieux', .75),
        ('joueur', 'Fine. $%.2f.' % a[1]['offre']),
        ('note', 'Counter-offer: $%.2f' % a[1]['prix']),
        ('pnj', 'derek', a[1]['ligne'], 'mefiant', .7),
        ('joueur', 'Deal at $%.2f.' % a[2]['offre']),
        ('pnj', 'derek', a[2]['ligne'], 'ravi', .55)], {}))
    S.append(('negociation_rate', 'Negotiation — Derek walks away', 'Même vendeur, autre suite réelle Economy : lowball → refuse → counter → départ (patience épuisée).', [
        ('pnj', 'derek', neg['intro'], 'neutre', .6),
        ('joueur', 'I can do $%.2f.' % b[0]['offre']),
        ('pnj', 'derek', b[0]['ligne'], 'furieux', .9),
        ('joueur', 'Okay, $%.2f?' % b[1]['offre']),
        ('pnj', 'derek', b[1]['ligne'], 'agace', .7),
        ('joueur', '$%.2f?' % b[2]['offre']),
        ('note', 'Counter-offer: $%.2f' % b[2]['prix']),
        ('pnj', 'derek', b[2]['ligne'], 'mefiant', .7),
        ('joueur', '$%.2f, final offer.' % b[3]['offre']),
        ('pnj', 'derek', b[3]['ligne'], 'agace', .9)], {}))
    # 6. Même réplique, plusieurs voix et émotions (« See you around. » revient 140 fois dans la V8).
    S.append(('meme_replique', 'Same line, different voices and moods — “See you around.”', 'Même motif (graine = texte exact), réalisé par 6 voix ; Felix la dit deux fois : même motif, petites variations.', [
        ('pnj', 'felix', 'See you around.', 'au_revoir', .6), ('pause', .4),
        ('pnj', 'felix', 'See you around.', 'au_revoir', .6), ('pause', .4),
        ('pnj', 'brittany', 'See you around.', 'moqueur', .8), ('pause', .4),
        ('pnj', 'antonio', 'See you around.', 'fatigue', .8), ('pause', .4),
        ('pnj', 'derek', 'See you around.', 'agace', .8), ('pause', .4),
        ('pnj', 'ava', 'See you around!', 'joyeux', .9)], {}))
    # 7. Réactions aux choix du joueur (V4 cafe_coffee + V2) : la blague passe ou tombe à plat.
    S.append(('choix', 'Reacting to the player’s choices — Marcus and Brittany at the café', 'Deux branches V4 « cafe_coffee » (blague absurde / question pratique), puis une blague qui tombe à plat chez Brittany (V2).', [
        ('pnj', 'marcus', 'Someone ordered decaf with four shots of espresso.', 'moqueur', .6),
        ('joueur', 'A philosophical contradiction.'),
        ('pnj', 'marcus', 'I considered asking what they believed in.', 'joyeux', .9),
        ('joueur', 'You have to admit it was funny.'),
        ('pnj', 'marcus', 'You really are committed to that bit, huh?', 'moqueur', .7),
        ('note', '— replay, other choice —'), ('pause', .6),
        ('pnj', 'marcus', 'Someone ordered decaf with four shots of espresso.', 'moqueur', .6),
        ('joueur', 'What would you recommend?'),
        ('pnj', 'marcus', 'Our house blend. Simple and reliable.', 'neutre', .6),
        ('pause', .8),
        ('joueur', 'I had a better joke, but I forgot it.'),
        ('pnj', 'brittany', 'Probably for the best.', 'moqueur', .9)], {}))
    # 8. Émotions mêlées : Paige hésite à vendre (V3 casual_seller.no_sale + ligne Economy « keep »).
    S.append(('melange', 'Mixed feelings — Paige hesitates to sell', 'Gêne → méfiance → tristesse → petit rire : V3 « casual_seller.no_sale » et la ligne Economy « keep » du profil nostalgique.', [
        ('pnj', 'paige', 'I’m not sure I want to sell the whole pile.', 'embarrasse', .8),
        ('joueur', 'Would you sell some?'),
        ('pnj', 'paige', 'Maybe the duplicates.', 'mefiant', .5),
        ('joueur', 'What about that one?'),
        ('pnj', 'paige', 'I’m keeping that one. Childhood, you know?', 'triste', .7),
        ('joueur', 'That sounds like a lot to deal with.'),
        ('pnj', 'paige', 'It has its moments.', 'joyeux', .5)], {}))
    # 9. Brocante : plusieurs vendeurs à des distances différentes, budget de voix, interruption.
    S.append(('brocante', 'Flea market — several stalls, distance, voice budget, skipped line', 'Vendeurs à 3, 4, 6 et 9 m ; un 5e à 13 m n’est pas joué (au-delà de 11 m, comme dans le jeu). Deux voix se chevauchent au plus (règle du futur directeur d’ambiance, posée ici à la main). À la fin, le joueur passe une longue réplique : fondu de 60 ms.', [
        ('pnj', 'marlene', 'Found these cards while clearing a closet.', 'joyeux', .6, {'ambiant': True, 'distance': 3, 'pan': -.5, 'apres': -.6}),
        ('pnj', 'wade', 'I sell dishes and lamps. The cards are just part of the table.', 'fatigue', .5, {'ambiant': True, 'distance': 6, 'pan': .6, 'apres': 1.6}),
        ('pnj', 'colin', 'You and I may grade that corner differently.', 'mefiant', .6, {'ambiant': True, 'distance': 9, 'pan': -.2, 'apres': -.5}),
        ('pnj', 'trevor', 'I already scanned this lot last night.', 'embarrasse', .6, {'ambiant': True, 'distance': 4, 'pan': .3, 'apres': 1.4}),
        ('note', 'Out of earshot (13 m): Dylan’s line is subtitled in the log, not voiced.'), ('pause', 1.0),
        ('pnj', 'marlene', 'Sorry about the dust. This box was in the attic.', 'embarrasse', .5, {'ambiant': True, 'distance': 3, 'pan': -.45, 'apres': 1.0}),
        ('joueur', 'Do you have anything else?'),
        ('coupe', 1.1),
        ('pnj', 'marlene', 'There is more to it, but I cannot tell the whole story in one breath.', 'joyeux', .6),
        ('joueur', '[skips the line]'),
        ('pnj', 'marlene', 'Sure thing.', 'neutre', .5)], {'fond': (['birds', 'wind'], [-8, -8]), 'fond_db': -26, 'ambiant': True}))
    return S


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--jeu', required=True)
    ap.add_argument('--sortie', required=True)
    args = ap.parse_args()
    os.makedirs(args.sortie, exist_ok=True)
    studio = Studio(args.jeu)
    manifeste = []
    for cle, titre, desc, etapes, opts in scenes(studio):
        studio.locuteurs.clear()
        fond = ambiance(studio, *opts['fond']) if 'fond' in opts else None
        (neuf, vieux), titres = construire(studio, etapes, opts.get('ambiant', False), fond, opts.get('fond_db', -30))
        ecrire_mp3(os.path.join(args.sortie, cle + '_nouveau.mp3'), neuf)
        ecrire_mp3(os.path.join(args.sortie, cle + '_ancien.mp3'), vieux)
        manifeste.append({'cle': cle, 'titre': titre, 'description': desc, 'titres': titres,
                          'duree': round(len(neuf) / SR, 2)})
        print('%-18s %5.1f s  %d répliques' % (cle, len(neuf) / SR, sum(1 for x in titres if x['qui'] and not x['joueur'])))
    json.dump(manifeste, open(os.path.join(args.sortie, 'scenes.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
