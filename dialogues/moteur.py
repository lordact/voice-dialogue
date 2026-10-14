"""Moteur de conversation de référence (V9) avec directeur d'humour.

Il choisit une scène pour un habitant, la déroule selon les choix du joueur, varie les réponses
génériques et dose l'humour pop culture. Il est déterministe (graine) pour les tests et la
simulation ; le portage Godot suivra la même logique.

Le directeur d'humour applique ces règles :
  - l'appétit d'humour dépend du personnage (style, âge, goûts) et grandit quand on se connaît ;
  - réciprocité : si le joueur plaisante et que le personnage aime ça, il plaisante plus ; s'il
    n'aime pas, il plaisante moins ; un joueur sérieux reçoit peu de blagues ;
  - jamais de blague quand le personnage est triste, en colère, déçu ou en pleine négociation tendue ;
  - budget par rencontre : au plus une scène pop OU un running gag, plus une réplique-clin d'œil ;
  - le joueur n'entend jamais deux fois la même réplique-clin d'œil dans la semaine, et pas plus de
    trois références d'un même domaine (jeux vidéo, mèmes, films…) par jour ;
  - les références suivent l'âge : un enfant ne cite pas de film d'espionnage, un retraité utilise
    les mèmes de travers (style « papy_meme ») ;
  - les running gags avancent d'une étape au plus par jour, et seulement avec leurs habitants.
"""
import collections, json, os, random

RACINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
TONS_EMOTION = json.load(open(os.path.join(RACINE, 'donnees', 'emotions.json'), encoding='utf-8'))['tons_v8']
EMOTIONS_SANS_BLAGUE = {'triste', 'furieux', 'agace', 'decu'}
TONS_DROLES = {'playful', 'absurd', 'humor'}
STYLES_BON_PUBLIC = {'geek', 'enthousiaste', 'bon_public', 'sarcastique', 'naif', 'papy_meme'}


class MemoirePNJ:
    def __init__(self):
        self.scenes = {}                     # id de scène -> jour
        self.dites = collections.Counter()   # répliques déjà dites par ce personnage
        self.humour = 0.0                    # complicité humoristique avec le joueur (-2..3)
        self.rencontres = 0


class MemoireJoueur:
    def __init__(self):
        self.entendues = collections.deque(maxlen=80)   # dernières répliques entendues (tous habitants)
        self.scenes = set()
        self.clins = {}                                  # id de réplique humour -> jour
        self.domaines = collections.Counter()            # (jour, domaine) -> nombre
        self.gags = {}                                   # id de gag -> (étape suivante, jour de la dernière)


class Moteur:
    def __init__(self, v9=None, graine=1):
        self.d = v9 or json.load(open(os.path.join(RACINE, 'donnees', 'dialogues_v9.json'), encoding='utf-8'))
        self.rng = random.Random(graine)
        self.habitants = self.d['distribution']['habitants']
        self.rel = self.d['relances']
        self.hum = self.d['humour']
        self.hubs = self.d['conditional_hubs']
        self.pnj = collections.defaultdict(MemoirePNJ)
        self.joueur = MemoireJoueur()
        self.jour = 0
        self.scenes_par_pnj = collections.defaultdict(list)
        for s in self.d['scenes']:
            for i in s.get('habitants', []):
                self.scenes_par_pnj[str(i)].append(s)
        self.stats = collections.Counter()

    # --- directeur d'humour -----------------------------------------------------------------
    def appetit(self, pid):
        p, m = self.habitants[pid], self.pnj[pid]
        a = p['appetit'] * (.6 + .4 * min(1.0, m.rencontres / 3)) * (1 + .25 * m.humour)
        return max(0.0, min(1.0, a))

    def public_ok(self, q, p):
        if p['public'] not in q['public']:
            return False
        if q.get('style') and q['style'] != p['style']:
            return False
        return q['domaine'] in p['gouts'] or q['domaine'] in ('memes', 'jeux_video') and p['public'] == 'ado'

    def domaine_ok(self, dom):
        return self.joueur.domaines[(self.jour, dom)] < 3

    def compter_ref(self, dom, quoi):
        self.joueur.domaines[(self.jour, dom)] += 1
        self.stats['ref_' + quoi] += 1
        self.stats['dom_' + dom] += 1

    def clin_doeil(self, fonction, pid, ctx):
        """Une réplique pop culture à la place d'une réponse générique, si c'est le bon moment."""
        p = self.habitants[pid]
        if ctx['budget_clin'] <= 0 or ctx['emotion'] in EMOTIONS_SANS_BLAGUE or ctx.get('tendu'):
            return None
        cands = [q for q in self.hum['repliques'] if q['fonction'] == fonction and self.public_ok(q, p)
                 and self.jour - self.joueur.clins.get(q['id'], -99) >= 7 and self.domaine_ok(q['domaine'])]
        if not cands:
            return None
        proba = self.appetit(pid) * 1.0 * (1.6 if ctx['joueur_drole'] else 1.0) * \
            {'blagueur': 1.3, 'neutre': .9, 'serieux': .35}.get(ctx.get('persona'), .9)
        if self.rng.random() >= proba:
            return None
        q = self.rng.choice(cands)
        if self.rng.random() > {1: 1.0, 2: .75, 3: .45}[q['intensite']]:
            return None
        self.joueur.clins[q['id']] = self.jour
        ctx['budget_clin'] -= 1
        self.compter_ref(q['domaine'], 'clin')
        return q['texte']

    def reaction(self, pid, ctx):
        """Le personnage réagit à la blague du joueur, selon son style ; la complicité évolue."""
        p, m = self.habitants[pid], self.pnj[pid]
        aime = p['style'] in STYLES_BON_PUBLIC and p['appetit'] >= .35
        m.humour = max(-2.0, min(3.0, m.humour + (.7 if aime else -.6)))
        if self.rng.random() > .35:
            return None
        rec = self.hum['receptions'][p['style']]
        cle = 'plat' if ctx['emotion'] in EMOTIONS_SANS_BLAGUE or ctx.get('tendu') else 'rit' if aime and m.humour > 0 else 'poli'
        self.stats['reaction_' + cle] += 1
        frais = [l for l in rec[cle] if l not in self.joueur.entendues] or rec[cle]
        return self.rng.choice(frais)

    # --- réponses variées aux relances ---------------------------------------------------------
    def repondre_relance(self, pid, fonction, origine, ctx):
        q = self.clin_doeil(fonction, pid, ctx)
        if q:
            return q, 'clin'
        fam = self.habitants[pid]['famille']
        pool = list(self.rel['commun'].get(fonction, [])) + list(self.rel['familles'].get(fam, {}).get(fonction, []))
        if origine and origine not in pool:
            pool.append(origine)
        m = self.pnj[pid]
        frais = [l for l in pool if m.dites[l] == 0 and l not in self.joueur.entendues] or \
                [l for l in pool if l not in self.joueur.entendues] or pool
        return self.rng.choice(frais), 'relance'

    # --- choix de scène --------------------------------------------------------------------------
    def poids_scene(self, s, pid, persona):
        p = self.habitants[pid]
        if s['id'] in self.joueur.scenes or self.jour - self.pnj[pid].scenes.get(s['id'], -99) < 7:
            return 0.0
        w = 1.0
        if s['source'] == 'V1':
            w = 1.5 if p['famille'] in ('cartes', 'brocante') else 0.0
        elif s['role_normalized'] != 'ambient_resident':
            w = 2.0
        if s.get('humour_pop'):
            premier = self.pnj[pid].rencontres == 0
            w *= self.appetit(pid) * (3.6 if persona == 'blagueur' else 1.8 if persona == 'neutre' else .3) * (.4 if premier else 1)
        return w

    def gag_pret(self, pid):
        for g in self.hum['running_gags']:
            if int(pid) not in g['habitants']:
                continue
            etape, dernier = self.joueur.gags.get(g['id'], (0, -1))
            if etape < len(g['etapes']) and g['etapes'][etape]['jour_min'] <= self.jour and dernier < self.jour \
                    and str(g['etapes'][etape].get('qui', pid)) == pid:
                return g, etape
        return None, None

    # --- une rencontre ---------------------------------------------------------------------------
    def rencontre(self, pid, persona='neutre', tendu=False):
        pid = str(pid)
        p, m = self.habitants[pid], self.pnj[pid]
        trans = []
        ctx = {'budget_clin': 1, 'emotion': 'neutre', 'joueur_drole': False, 'tendu': tendu, 'humour_majeur': 0, 'persona': persona}

        def dit(qui, texte, tag=''):
            trans.append({'qui': p['nom'] if qui == 'pnj' else 'You', 'texte': texte, 'tag': tag})
            if qui == 'pnj':
                m.dites[texte] += 1
                if texte in self.joueur.entendues:
                    self.stats['redites_entendues'] += 1
                self.joueur.entendues.append(texte)

        # 1. Running gag (au plus une étape par jour et par gag).
        g, etape = self.gag_pret(pid)
        if g and not tendu and self.rng.random() < .45 + .5 * self.appetit(pid):
            e = g['etapes'][etape]
            dit('pnj', e['texte'], 'gag:%s:%d' % (g['id'], etape))
            self.joueur.gags[g['id']] = (etape + 1, self.jour)
            self.compter_ref(e.get('domaine', 'village'), 'gag')
            # Le gag est le sujet de la rencontre : on y réagit, puis on se quitte.
            rg = self.hum['reactions_gag']
            c = self.choisir(rg['joueur'], persona, lambda o: o['ton'])
            dit('joueur', c['texte'])
            pool = rg.get('pnj_par_reaction', {}).get(c['texte'], rg['pnj'])
            frais = [l for l in pool if l not in self.joueur.entendues] or pool
            dit('pnj', self.rng.choice(frais))
            dit('joueur', 'See you around.')
            texte, tag = self.repondre_relance(pid, 'depart', None, ctx)
            dit('pnj', texte, tag)
            m.rencontres += 1
            self.stats['rencontres'] += 1
            self.stats['rencontres_avec_humour'] += 1
            self.stats['elements_humour'] += 1 + (tag == 'clin')
            return trans
        # 2. Scène.
        cands = self.scenes_par_pnj.get(pid, [])
        poids = [self.poids_scene(s, pid, persona) * (0 if (ctx['humour_majeur'] or tendu) and s.get('humour_pop') else 1) for s in cands]
        if sum(poids) <= 0:
            self.stats['sans_scene'] += 1
            dit('pnj', self.rng.choice(self.hubs['neighborhood_smalltalk'].get('npc_variantes', [self.hubs['neighborhood_smalltalk']['npc']])))
            s = None
        else:
            s = self.rng.choices(cands, weights=poids)[0]
            self.joueur.scenes.add(s['id'])
            m.scenes[s['id']] = self.jour
            tag = 'scene_pop' if s.get('humour_pop') else 'scene'
            if s.get('humour_pop'):
                self.compter_ref('scene', 'scene')
                ctx['humour_majeur'] = 1
            dit('pnj', s['opening'], tag + ':' + s['id'])
            self.jouer_scene(s, pid, persona, ctx, dit)
        # 3. Fin polie si la scène n'a pas fermé.
        if not trans or trans[-1]['qui'] == 'You' or len(trans) < 4:
            dit('joueur', 'See you around.')
            texte, tag = self.repondre_relance(pid, 'depart', None, ctx)
            dit('pnj', texte, tag)
        m.rencontres += 1
        self.stats['rencontres'] += 1
        humour = sum(1 for x in trans if x['tag'].startswith(('scene_pop', 'gag', 'clin')))
        self.stats['rencontres_avec_humour'] += humour > 0
        self.stats['elements_humour'] += humour
        return trans

    def choisir(self, options, persona, ton):
        """Choix du joueur selon sa personnalité : blagueur, neutre ou sérieux."""
        w = []
        for o in options:
            t = ton(o)
            if persona == 'blagueur':
                w.append(3.0 if t in TONS_DROLES else 1.0)
            elif persona == 'serieux':
                w.append(.15 if t in TONS_DROLES else 2.0)
            else:
                w.append(1.0)
        return self.rng.choices(options, weights=w)[0]

    def jouer_scene(self, s, pid, persona, ctx, dit):
        c = self.choisir(s['choices'], persona, lambda o: o.get('tone'))
        dit('joueur', c['player'])
        ctx['emotion'] = TONS_EMOTION.get(c.get('tone'), 'neutre')
        if c.get('tone') in TONS_DROLES:
            ctx['joueur_drole'] = True
            r = self.reaction(pid, ctx)
            if r:
                dit('pnj', r, 'reaction')
        if s['source'] == 'V1' and c.get('deep_tree_node'):
            dit('pnj', c['npc'])
            self.jouer_arbre(c['deep_tree_node'], persona, dit)
            return
        fonction = self.rel['fonctions'].get(c['player'])
        if fonction and c.get('npc'):
            texte, tag = self.repondre_relance(pid, fonction, c['npc'], ctx)
            dit('pnj', texte, tag)
        elif c.get('npc'):
            dit('pnj', c['npc'])
        fups = c.get('followups', [])
        if fups:
            f = self.choisir(fups, persona, lambda o: 'playful' if 'joke' in o['player'].lower() or 'funny' in o['player'].lower() else 'practical')
            dit('joueur', f['player'])
            fonction = self.rel['fonctions'].get(f['player'])
            if fonction:
                texte, tag = self.repondre_relance(pid, fonction, f.get('npc'), ctx)
                dit('pnj', texte, tag)
                return
            if f.get('npc'):
                dit('pnj', f['npc'])
                return
            hub = str(f.get('outcome', ''))[4:] if str(f.get('outcome', '')).startswith('hub:') else 'neighborhood_smalltalk'
            self.jouer_raccord(hub, pid, persona, ctx, dit)
            return
        if c.get('suggested_next_hub'):
            if self.rng.random() < .45:   # le raccord n'est pas systématique : souvent, on se quitte là-dessus
                self.jouer_raccord(c['suggested_next_hub'], pid, persona, ctx, dit)

    def jouer_raccord(self, hub_id, pid, persona, ctx, dit):
        if hub_id in ('role_related', 'local_work_or_smalltalk', 'shipping_and_daily_work') and \
                self.habitants[pid]['famille'] in ('enfants', 'ados', 'retraites', 'visiteurs'):
            hub_id = 'neighborhood_smalltalk'   # pas de « mon travail » pour un enfant ou un retraité
        h = self.hubs.get(hub_id) or self.hubs['polite_exit']
        variantes = [v for v in h.get('npc_variantes', [h['npc']]) if v not in self.joueur.entendues] or h.get('npc_variantes', [h['npc']])
        dit('pnj', self.rng.choice(variantes), 'raccord:' + hub_id)
        if h['choices']:
            c = self.choisir(h['choices'], persona, lambda o: 'practical')
            dit('joueur', c['player'])
            vs = c.get('npc_variantes', [c['npc']])
            dit('pnj', self.rng.choice([v for v in vs if v not in self.joueur.entendues] or vs))

    def jouer_arbre(self, nid, persona, dit):
        nodes = self.d['deep_trees']['V1']['nodes']
        for _ in range(4):
            n = nodes[nid]
            c = self.choisir(n['choices'], persona, lambda o: 'practical')
            dit('joueur', c['text'])
            if 'next' in c:
                nid = c['next']
                dit('pnj', nodes[nid]['npc_line'])
            else:
                dit('pnj', c.get('npc_reply', ''))
                return
