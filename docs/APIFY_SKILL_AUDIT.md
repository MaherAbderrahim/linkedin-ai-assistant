# Audit du skill Apify — `apify-ultimate-scraper`

Date : 13 novembre 2026 (Mission 0.6). **Audit documentaire en lecture seule des fichiers du skill installés sur la machine.** Aucun Actor exécuté, aucun compte Apify créé ou configuré, aucun appel réseau, aucune modification du skill original. Les sorties décrites proviennent des guides du skill, pas d'exécutions réelles : les schémas exacts restent à vérifier dynamiquement avant tout usage.

## 1. Identité et emplacement

- Chemin : `C:\Users\maher\.agents\skills\apify-ultimate-scraper\`.
- Fichiers lus : `SKILL.md`, `references/actor-index.md`, `references/gotchas.md`, guides `references/workflows/` (dont `social-media-analytics.md`, `company-research.md`, `contact-enrichment.md`, `knowledge-base-and-rag.md`).
- Nature : **skill d'agent** (instructions destinées à l'assistant), pas une bibliothèque Python ni un service. Il pilote le **CLI Apify**. Le cœur de l'assistant n'en dépend pas et reste sans dépendance runtime.

## 2. Fonctionnement et instructions

- Prérequis : Apify CLI ≥ 1.5.0 (`npm install -g apify-cli`) et session authentifiée.
- Authentification : `apify login` (OAuth navigateur) ou variable `APIFY_TOKEN` (environnement / `.env`). Le jeton ne transite ni par le chat ni par les logs.
- Règles imposées à chaque commande : `--json`, `--user-agent apify-agent-skills/apify-ultimate-scraper`, `2>/dev/null`.
- Flux : choisir un Actor (`actor-index.md`) → lire son schéma d'entrée (`apify actors info ACTOR --input --json`) → consulter `gotchas.md` → exécuter (`apify actors call --input-file input.json`, ou `start` + sondage `runs info` pour les lots longs) → récupérer les résultats (`apify datasets get-items DATASET --format json|csv`).
- Sortie : items JSON d'un dataset, **champs spécifiques à chaque Actor** ; pas de schéma universel. Estimation de coût obligatoire avant tout Actor payant à l'événement.

## 3. Actors LinkedIn recensés (index du skill)

Tous **community-maintained** et **PPE (pay-per-event)**. Entrées/sorties ci-dessous = champs documentés dans les guides du skill, non vérifiés sur une exécution réelle.

| Actor | Usage | Entrées documentées | Sorties documentées |
|---|---|---|---|
| `harvestapi/linkedin-profile-posts` | Posts d'un profil personnel | `profiles` (URLs), `maxPosts` | `postText`, `publishedAt`, `likes`, `comments`, `url` |
| `harvestapi/linkedin-company-posts` | Posts d'une page entreprise | `companyUrl`, `maxPosts`, `publishedAfter` | `text`, `publishedAt`, `url`, `likesCount`, `commentsCount`, `repostsCount` |
| `apimaestro/linkedin-batch-profile-posts-scraper` | Posts par lots de profils | lot de profils | posts (schéma à relever) |
| `apimaestro/linkedin-post-detail` | Détail d'un post | `urls` | `reactions{}`, `topComments[]`, `impressions` |
| `harvestapi/linkedin-post-comments` | Commentaires d'un post | `postUrl`, `maxComments` | `commenter.*`, `commentText`, `timestamp` |
| Autres (`profile-search`, `profile-scraper`, `company`, `job-search`, `post-search`…) | Recherche/profils/entreprises/offres | selon Actor | selon Actor |

Les guides ne garantissent pas d'identifiant LinkedIn **typé** (`share`/`ugcPost`/`activity`/URN) dans la sortie ; `url` est une URL attestée, pas un URN. Conséquence pour l'archive : repli de comparaison conservateur (texte normalisé + date précise + auteur), ambiguïtés arbitrées humainement.

## 4. Coûts et garde-fous (gotchas du skill)

- Tarification par événement/résultat, variable : `harvestapi/` ~0,001–0,01 $/résultat ; `apimaestro/` ~0,005–0,02 $/résultat ; `dev_fusion/` intermédiaire. **Valeurs indicatives du skill**, à recontrôler via `actors info` (`.currentPricingInfo`).
- Protocole imposé : estimer le coût avant exécution ; avertir au-delà de ~5 $ ; confirmation explicite au-delà de ~20 $. Toute estimation est approximative, jamais présentée comme exacte.
- Plateforme : l'offre Free documentée en Mission 0 (5 USD renouvelés/mois, sans carte) reste une **preuve datée à recontrôler** ; calcul, stockage, transferts et proxys consomment aussi le crédit. Aucun quota gratuit n'est garanti par le présent audit.

## 5. Dépendances et limites techniques

- Dépendances : CLI npm, compte Apify authentifié, réseau, proxy éventuel. **Aucune dépendance Python ajoutée au projet.**
- LinkedIn bloque activement le scraping à grande échelle : lots < 100 profils, exécutions espacées d'au moins 5 minutes, résultats vides occasionnels à prévoir.
- Posts privés/restreints : dataset vide **sans erreur**.
- Sessions/cookies gérés en interne par les Actors ; aucun `li_at` ni mot de passe à fournir dans le chat.
- Noms de champs de limite variables (`maxItems`, `maxPosts`, `resultsLimit`…) : toujours vérifier le schéma de l'Actor.

## 6. Conditions d'utilisation et conformité

- Le skill documente des contre-mesures techniques (proxy, rotation d'empreintes), **pas une autorisation juridique**.
- Scraper LinkedIn — même ses propres posts — peut violer les conditions LinkedIn (LI-LEGAL). Un compte Apify autorisé ne vaut pas autorisation LinkedIn ; les conditions Apify et LinkedIn sont distinctes et cumulatives.
- Données chez Apify : rétention propre (dix dernières exécutions ~4 mois, stockages nommés différents — preuve Mission 0 à recontrôler) ; DPA distinct ; conformité tunisienne et transferts non vérifiés.
- **Décision projet :** le cœur reste sur l'API officielle LinkedIn et les imports autorisés. La collecte Apify n'entre pas dans le socle par défaut ; aucune publication par Apify n'est admise.

## 7. Réutilisation pour l'archive SQLite

Mapping proposé vers l'enveloppe d'import générique ([API_INTEGRATIONS.md §6.1](API_INTEGRATIONS.md)) :

| Champ du skill | Champ d'archive | Traitement |
|---|---|---|
| `postText` / `text` | texte intégral exact | conservé tel quel, non reformulé |
| `publishedAt` | `published_at` | précision/fuseau à qualifier ; date seule ≠ heure exacte |
| `url` | URL attestée | pas d'URN typé fiable ; ne pas fabriquer d'identifiant |
| profil/auteur | `account` | auteur attendu vérifié |
| `likes`/`comments`/`reactions` | observations | non nécessaires au style ; droits séparés |

- Provenance : `source=apify_skill`, `provider=actor/version`, **jamais réétiqueté** `user_original`.
- Droits : matrice stockage/analyse/dérivation/transfert par destination (Telegram inclus) vérifiée **avant persistance** ; droits inconnus ⇒ refus, aucune copie provisoire.
- Le pipeline existant (droits → parse borné → comparaison → aperçu immuable → accord lot/éléments → commit idempotent) s'applique sans modification.

## 8. Modes d'intégration, par ordre de préférence

1. **Export fourni par l'utilisateur → importeur générique** (déjà implémenté et testé). Aucun Actor exécuté par l'application. Mode préféré.
2. **Adaptateur de traduction** sortie du skill → enveloppe d'import, après audit d'une sortie réelle, droits vérifiés et accord utilisateur ; skill original inchangé ; coûts bornés et mesurés avant usage (Phase 3B optionnelle de la feuille de route).
3. **Réutilisation des seules règles d'analyse/parsing conformes**, sans collecte.

Le skill demeure un outil d'agent pour des recherches ponctuelles autorisées, pas une dépendance d'exécution de l'assistant.

## 9. Ce qui n'a pas été fait

Aucune exécution d'Actor, aucun login, aucun jeton obtenu, aucune modification du skill, aucun compte créé. Les schémas de sortie réels, les prix effectifs et les conditions à jour restent à vérifier avant toute intégration de mode 2.

## 10. Conclusion

Skill compris et audité ; réutilisable pour l'archive **via l'import générique, sans dépendance du cœur**. La collecte LinkedIn par scraping étant non conforme par défaut, elle reste hors socle ; l'archive démarre avec les originaux utilisateur et les publications confirmées du bot. L'original du skill est inchangé.

Sources : fichiers locaux du skill (lus le 13 novembre 2026) ; [FREE_SERVICES_BENCHMARK.md](FREE_SERVICES_BENCHMARK.md) (APIFY-1 à 5) ; [API_INTEGRATIONS.md](API_INTEGRATIONS.md) (LI-LEGAL, §6).