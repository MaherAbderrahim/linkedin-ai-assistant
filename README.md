# LinkedIn AI Assistant

Assistant personnel pour rechercher, rédiger, corriger et publier du contenu LinkedIn depuis Telegram, **uniquement après validations explicites**.

**Statut au 13 novembre 2026 : phases 2 et 3 implémentées localement (socle conversationnel, archive centrale, import générique) — 50 tests sans réseau, publication simulée. Aucun bot/compte créé, aucune intégration authentifiée ni publication réelle. Dépôt privé : github.com/MaherAbderrahim/linkedin-ai-assistant.**

## Architecture : décisions validées et propositions

- **Validés : Python + SQLite modulaires**, fournisseurs interchangeables, **Telegram principal**, n8n facultatif ; utilisation en **Tunisie, `Africa/Tunis`**.
- **Archive centrale durable de tous les textes dont la rétention est permise**, profil de style compact persistant, règles explicites séparées ; SQLite garde aussi paramètres, brouillons versionnés, approbations, reprise et anti-doublon. Les **trois posts récents sont un échantillon, jamais une limite de stockage**.
- **Source A — publications du bot :** après confirmation LinkedIn fiable seulement, conserver le texte original exact envoyé et enregistrer preuve de succès + archive dans une transaction locale atomique, jamais une transaction réseau. ID/URL restent nullables ; `published_at` attesté (précision/fuseau), `confirmed_at` observé et `imported_at` acquis sont distincts. Brouillon ou `UNKNOWN_OUTCOME` n’est pas une publication réussie.
- **Source B — import indépendant du fournisseur :** droits vérifiés avant persistance, parsing borné, comparaison, aperçu immuable, accord lot/éléments puis transaction idempotente. Provenance réelle, observations et versions conservées ; identifiants LinkedIn typés, ambiguïtés humaines, aucun export API réétiqueté en original utilisateur. Un import ne résout pas automatiquement un envoi incertain.
- **Profil descriptif recalculable et référencé**, sans inférence sensible ; textes assistant identifiés, aucune règle normative permanente sans confirmation séparée du texte exact. Retrieval proposé : filtres SQLite + FTS5 si disponible, échantillons récents/thématiques/par période, au plus **6 posts / 12 000 caractères cumulés**, profil **4 000 caractères** ; règles confirmées séparées, jamais tronquées silencieusement. Pas d’envoi de toute l’archive à chaque génération.
- **Aucune archive binaire d’images.** RAM seule de bout en bout proposée, sans BLOB, disque temporaire ni sauvegarde ; seules métadonnées/empreintes/droits autorisés sont persistables. Perte du tampon ou redémarrage : nouvel aperçu, nouvelles approbations image et finale ; aucune suppression Telegram/LinkedIn ni absence de swap OS promise.
- **API officielle LinkedIn validée en principe**, `/rest/posts` visée sous réserve d’accès réel ; validations **texte + image/absence distinctes + aperçu exact + autorisation finale à usage unique**. Le LLM ne peut ni autoriser ni déclencher une publication.
- **Proposés, non intégrés :** processus unique, Telegram long polling ; Groq Free/modèle à qualifier, Tavily Free basic + extraction HTTP/Trafilatura, Wikimedia Commons avec droits vérifiés ; génération d’images désactivée. Recherche bornée à **3 requêtes / 5 pages par tour**.
- **Hôte à choisir :** machine existante de confiance, ou Oracle Always Free conditionnel. Rappels facultatifs en `Africa/Tunis` : activation/heure/jours et seuil **120 h proposés** ; date de publication acceptée, jamais date d’import, au plus un rappel/jour, fusion et reprise sans rafale. Le bot fonctionne sans rappels.

## Faisabilité et limites honnêtes

**0 € et aucun paiement obligatoire ni fallback payant** : quota gratuit épuisé ou conditions ambiguës, arrêt de la capacité concernée. Aucun accès de compte, SLA ou gratuité perpétuelle présumé ; matériel, Internet et électricité de l’hôte restent à prendre en charge explicitement.

La publication personnelle via `w_member_social` est documentée, pas attestée pour un compte :

- La lecture de l’historique via `r_member_social` est restreinte ; import autorisé et déclaration datée ne valent pas surveillance automatique des posts externes.
- **`w_member_social` seul ne permet pas le GET versionné du statut d’image.** Preuves et qualification texte/image séparées ; endpoint réellement utilisable et renouvellement OAuth restent à vérifier.
- Timeout après envoi possible : **`UNKNOWN_OUTCOME`, verrou du compte, zéro retry automatique**, réconciliation explicite. Ni brouillon ni import ne prouvent automatiquement le succès d’un envoi ; aucune garantie réseau « exactly once ».

**Conformité par origine et usage :** vérifier séparément stockage, analyse, dérivation et transfert vers chaque destination, **Telegram compris**. La règle des **48 h des Marketing APIs vise l’activité sociale issue de ces APIs**, pas tous les originaux ou imports Apify. Un export conserve son origine API ; le consentement ne neutralise pas les conditions. Droits inconnus : aucune persistance provisoire. Restrictions plus strictes et effacements requis/demandés se propagent aux versions, dérivés, index et profil ; la purge proposée des brouillons à 30 jours n’efface pas l’archive autorisée. Conditions tunisiennes et transferts restent non vérifiés.

Le **skill Apify exact n’est pas fourni ni audité** : ne pas lui substituer un skill générique et ne pas l’invoquer. Examiner d’abord fichiers, instructions, dépendances, Actor(s) exact(s) et entrées/sorties anonymisées, puis accès/coûts/droits. Adaptations seulement proposées, original inchangé ; aucune collecte ou publication non conforme.

## Documents de référence

| Fichier | Contenu |
|---|---|
| [README.md](README.md) | Synthèse Mission 0.5, statut et décisions ouvertes |
| [AGENTS.md](AGENTS.md) | Consignes pour les prochaines sessions, règles non négociables et index |
| [PRODUCT_REQUIREMENTS.md](docs/PRODUCT_REQUIREMENTS.md) | Besoin complet, périmètre, parcours, exigences et critères d’acceptation |
| [TECHNICAL_ARCHITECTURE.md](docs/TECHNICAL_ARCHITECTURE.md) | Modules, interfaces, états, validations, données, conservation et exploitation |
| [ARCHITECTURE_DECISIONS.md](docs/ARCHITECTURE_DECISIONS.md) | Comparaison de quatre architectures, raisons, alternatives et limites des choix |
| [DEVELOPMENT_ROADMAP.md](docs/DEVELOPMENT_ROADMAP.md) | Phases, dépendances, gates et autorisations avant développement/actions réelles |
| [API_INTEGRATIONS.md](docs/API_INTEGRATIONS.md) | Capacités documentées vs accès non testés, OAuth, endpoints, limites et sources LinkedIn |
| [FREE_SERVICES_BENCHMARK.md](docs/FREE_SERVICES_BENCHMARK.md) | Comparaison documentaire datée, quotas, pays, confidentialité, cartes et frais possibles |
| [TEST_STRATEGY.md](docs/TEST_STRATEGY.md) | Tests futurs, invariants de sécurité, pannes, recette humaine et preuves attendues |

Les neuf documents sont liés ci-dessus. Code : `src/linkedin_assistant/` (bibliothèque standard uniquement), tests dans `tests/`. Installation locale : `python -m venv .venv` puis `.venv/Scripts/python -m pip install -e ".[dev]"` ; tests : `.venv/Scripts/python -m pytest -q` ; démarrage : `.venv/Scripts/linkedin-assistant --config config.toml` (mode simulation sans jeton, voir `config.example.toml`).

## Risques et blocages prioritaires

| Risque | Effet | Réponse proposée |
|---|---|---|
| Scopes/endpoint/OAuth non attestés | Publication ou renouvellement indisponibles | Preuves d’accès à obtenir séparément ; aucun compte présumé accessible, aucun contournement |
| Historique incomplet, skill exact manquant | Couverture du style et rappels incertains | Import indépendant après audit/droits/aperçu/accord ; dates et couverture visibles, jamais trois posts comme plafond |
| Doublons, versions ou dates ambiguës | Fusion erronée ou mauvais rappel | ID typé prioritaire, repli conservateur texte + date précise/auteur/métadonnées ; arbitrage humain, pas de suppression silencieuse ni de null écrasant une valeur connue |
| Droits/transferts/conditions tunisiennes non vérifiés | Stockage ou destination interdits | Vérifier chaque usage/destination, refus sans droits, effacement propagé ; consentement insuffisant à lever une interdiction |
| Image non qualifiée ou tampon perdu | Autorisation image devenue inutilisable | Preuve image séparée ; nouvel aperçu et approbations image/finale, texte seul uniquement par choix explicite |
| Quota gratuit ou hôte indisponible | Traitement interrompu | Arrêt sans paiement, hôte et coûts indirects acceptés ; reprise/sauvegarde des seules données autorisées, jamais des binaires images |
| Réponse LinkedIn perdue | Doublon possible | Verrou du compte, zéro retry automatique, réconciliation ; import seul insuffisant |

## Décisions encore ouvertes avant développement

Le socle Python/SQLite, le pays Tunisie et le fuseau `Africa/Tunis` sont déjà validés. Restent à décider ou à fournir :

1. **Hôte** : machine/administrateur, interruptions acceptées, coûts indirects, sécurité et sauvegarde des données autorisées.
2. **Fournisseurs et permissions** : modèles/offres réellement 0 €, restrictions tunisiennes et transferts, endpoints/scopes/OAuth texte et image ; éléments de preuve sans secret, aucun accès ou test autorisé par cette liste.
3. **Skill Apify exact** : fichiers/instructions/dépendances, Actor(s) et I/O anonymisées ; format des imports, origine réelle, droits, limites de parsing et modalités d’accord lot/éléments. Audit documentaire avant toute proposition d’adaptation ; original inchangé.
4. **Consentements et paramètres de données** : droits séparés stockage/analyse/dérivation/transfert par destination ; rétentions par origine, purge des brouillons proposée à 30 j sans toucher l’archive autorisée, suppression des dérivés, RAM seule pour images ; seuils retrieval 6 posts/12 000 caractères et profil 4 000 caractères proposés.
5. **Préférences éditoriales** : thèmes, public, ton, exclusions ; confirmation séparée de toute règle normative permanente.
6. **Rappels facultatifs** : activation, heure/jours et seuil 120 h proposés en `Africa/Tunis` ; dates de publication acceptées, clarification des dates imprécises/futures/en conflit ; `confirmed_at` du bot seulement comme approximation signalée sans heure serveur.

## Prochaine étape

L’utilisateur a autorisé le démarrage de l’implémentation (13 novembre 2026) : socle local d’abord (phases 2 à 4 de la feuille de route, adaptateurs simulés, aucun compte réel), puis les capacités externes après validation des décisions ouvertes et autorisation distincte de chaque action. Tout futur test de publication exigera une autorisation séparée sur le contenu exact ; aucune condition inconnue n’est réputée satisfaite. Le skill Apify original reste inchangé tant que ses fichiers n’ont pas été fournis et audités.
