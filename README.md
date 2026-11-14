# LinkedIn AI Assistant

Assistant personnel pour rechercher, rédiger, corriger et publier du contenu LinkedIn depuis Telegram, **uniquement après validations explicites**.

**Statut au 14 novembre 2026 : Phase 1 (volet B) livrée — loader `.env` stdlib + validation par nom au démarrage, rappel 10 h `Africa/Tunis` modifiable, paramètres progressifs partagés Telegram/dashboard (`/settings`), contrat `Publisher` formalisé avec résolution dynamique treg, contrat `LLMProvider` + adaptateurs simulés Groq/OpenRouter + harness de comparaison (`llm_benchmarks`, aucun appel réel), squelette du tableau de bord local `127.0.0.1:8000` (config, état, benchmarks, archive — aucune publication) — 143 tests sans réseau. Phases 2 à 4 et rappels locaux déjà livrées. Scaffolding Phase 5 simulé livré (SearchProvider + budget, extracteur SSRF). Accès de publication LinkedIn provisionné via treg (proxy de credentials, ADR-16) — connexion active, identité et `w_member_social` vérifiés ; publication réelle NON TESTÉE. Chaque action externe exige une autorisation distincte. Dépôt privé : github.com/MaherAbderrahim/linkedin-ai-assistant.**

## Architecture : décisions validées et propositions

- **Validés : Python + SQLite modulaires**, fournisseurs interchangeables, **Telegram principal**, n8n facultatif ; utilisation en **Tunisie, `Africa/Tunis`**.
- **Archive centrale durable de tous les textes dont la rétention est permise**, profil de style compact persistant, règles explicites séparées ; SQLite garde aussi paramètres, brouillons versionnés, approbations, reprise et anti-doublon. Les **trois posts récents sont un échantillon, jamais une limite de stockage**.
- **Source A — publications du bot :** après confirmation LinkedIn fiable seulement, conserver le texte original exact envoyé et enregistrer preuve de succès + archive dans une transaction locale atomique, jamais une transaction réseau. ID/URL restent nullables ; `published_at` attesté (précision/fuseau), `confirmed_at` observé et `imported_at` acquis sont distincts. Brouillon ou `UNKNOWN_OUTCOME` n’est pas une publication réussie.
- **Source B — import indépendant du fournisseur :** droits vérifiés avant persistance, parsing borné, comparaison, aperçu immuable, accord lot/éléments puis transaction idempotente. Provenance réelle, observations et versions conservées ; identifiants LinkedIn typés, ambiguïtés humaines, aucun export API réétiqueté en original utilisateur. Un import ne résout pas automatiquement un envoi incertain.
- **Profil descriptif recalculable et référencé**, sans inférence sensible ; textes assistant identifiés, aucune règle normative permanente sans confirmation séparée du texte exact. Retrieval proposé : filtres SQLite + FTS5 si disponible, échantillons récents/thématiques/par période, au plus **6 posts / 12 000 caractères cumulés**, profil **4 000 caractères** ; règles confirmées séparées, jamais tronquées silencieusement. Pas d’envoi de toute l’archive à chaque génération.
- **Aucune archive binaire d’images.** RAM seule de bout en bout proposée, sans BLOB, disque temporaire ni sauvegarde ; seules métadonnées/empreintes/droits autorisés sont persistables. Perte du tampon ou redémarrage : nouvel aperçu, nouvelles approbations image et finale ; aucune suppression Telegram/LinkedIn ni absence de swap OS promise.
- **API officielle LinkedIn validée en principe**, `/rest/posts` visée sous réserve d’accès réel ; validations **texte + image/absence distinctes + aperçu exact + autorisation finale à usage unique**. Le LLM ne peut ni autoriser ni déclencher une publication.
- **Décisions du 14 novembre 2026 (treg, ADR-16) :** l'accès de publication LinkedIn passe par **treg** (proxy de credentials hébergé), avec l'OAuth propre du membre détenu côté treg — aucune application Developer propre ni callback local requis. Connexion `linkedin` active (capability `write`, consentement utilisateur), identité et `w_member_social` vérifiés par `v2/userinfo` → 200 (expiration 2027-01-13). Publication prévue via `POST /rest/posts` (0 $, non mesurée), preuve = HTTP 201 + URN dans `x-restli-id`, jamais le scraping treg ; rotation treg ⇒ l'adaptateur résoudra dynamiquement la connexion (aucun nom/secret en dur). Endpoints treg mesurés à éviter ; recherche = Tavily. **Publication réelle toujours NON TESTÉE** ; chaque test exigera une autorisation distincte.
- **Décisions du 13 novembre 2026 :** hébergement sur le **PC de l'utilisateur** pour le développement et les premiers tests (Oracle Always Free à étudier plus tard, PC ami en secours ; aucune installation distante maintenant, développement non bloqué). LLM **Groq + OpenRouter à comparer** (qualité du français, suivi des instructions, reproduction du style, latence, limites), aucun modèle figé avant tests comparatifs, clés fournies par l'utilisateur via `.env`. **Tableau de bord web local** planifié (localhost, même configuration SQLite que Telegram, jamais exposé publiquement sans protection). **Rappel quotidien à 10 h 00 `Africa/Tunis`, modifiable** ; paramètres éditoriaux progressifs configurables.
- **Proposés, non intégrés :** processus unique, Telegram long polling (implémentés localement) ; Tavily Free basic + extraction HTTP/Trafilatura, Wikimedia Commons avec droits vérifiés ; génération d’images désactivée. Recherche bornée à **3 requêtes / 5 pages par tour**.
- **Rappels facultatifs en `Africa/Tunis` :** heure 10 h 00 choisie, jours/activation et seuil **120 h proposés** ; date de publication acceptée, jamais date d’import, au plus un rappel/jour, fusion et reprise sans rafale. Le bot fonctionne sans rappels.

## Faisabilité et limites honnêtes

**0 € et aucun paiement obligatoire ni fallback payant** : quota gratuit épuisé ou conditions ambiguës, arrêt de la capacité concernée. Aucun accès de compte, SLA ou gratuité perpétuelle présumé ; matériel, Internet et électricité de l’hôte restent à prendre en charge explicitement.

**Vérification de l'existant (13 novembre 2026) : aucune intégration LinkedIn antérieure n'a été trouvée dans l'espace de travail** — uniquement des scrapers d'offres d'emploi publics (`_work/`), sans rapport avec la publication, aucune application Developer, aucun `client_id`/secret/jeton. La « méthode précédente » n'existe que dans la documentation. La publication personnelle via `w_member_social` + OpenID Connect ne requiert pas intrinsèquement de page entreprise (l'association de Page vise « certaines fonctionnalités et certains produits »), mais **toute intégration OAuth officielle exige une application Developer** (`client_id`). Vérifier le portail développeur pour une application existante avant toute création ; ne rien contourner. **Mise à jour du 14 novembre 2026 :** le parcours retenu passe désormais par treg (ADR-16), qui fournit l'OAuth sans application Developer propre — connexion active, identité et `w_member_social` vérifiés ; la publication réelle reste NON TESTÉE. L'interface de publication est abstraite et remplaçable, avec simulateur en place jusqu'à l'accès réel.

La publication personnelle via `w_member_social` est documentée, pas attestée pour un compte :

- La lecture de l’historique via `r_member_social` est restreinte ; import autorisé et déclaration datée ne valent pas surveillance automatique des posts externes.
- **`w_member_social` seul ne permet pas le GET versionné du statut d’image.** Preuves et qualification texte/image séparées ; endpoint réellement utilisable et renouvellement OAuth restent à vérifier.
- Timeout après envoi possible : **`UNKNOWN_OUTCOME`, verrou du compte, zéro retry automatique**, réconciliation explicite. Ni brouillon ni import ne prouvent automatiquement le succès d’un envoi ; aucune garantie réseau « exactly once ».

**Conformité par origine et usage :** vérifier séparément stockage, analyse, dérivation et transfert vers chaque destination, **Telegram compris**. La règle des **48 h des Marketing APIs vise l’activité sociale issue de ces APIs**, pas tous les originaux ou imports Apify. Un export conserve son origine API ; le consentement ne neutralise pas les conditions. Droits inconnus : aucune persistance provisoire. Restrictions plus strictes et effacements requis/demandés se propagent aux versions, dérivés, index et profil ; la purge proposée des brouillons à 30 jours n’efface pas l’archive autorisée. Conditions tunisiennes et transferts restent non vérifiés.

Le **skill Apify a été audité le 13 novembre 2026** (lecture seule de ses fichiers ; voir [APIFY_SKILL_AUDIT.md](docs/APIFY_SKILL_AUDIT.md)) : skill d’agent pilotant le CLI Apify, Actors LinkedIn tous community/PPE, scraping bloqué à grande échelle et non conforme par défaut. Original inchangé, aucune exécution. Réutilisation pour l’archive via l’**import générique** (export utilisateur préféré, adaptateur optionnel après droits et accord) ; jamais une dépendance du cœur ni un moyen de publication.

## Documents de référence

| Fichier | Contenu |
|---|---|
| [README.md](README.md) | Synthèse Mission 0.6, statut et décisions |
| [AGENTS.md](AGENTS.md) | Consignes pour les prochaines sessions, règles non négociables et index |
| [PRODUCT_REQUIREMENTS.md](docs/PRODUCT_REQUIREMENTS.md) | Besoin complet, périmètre, parcours, exigences et critères d’acceptation |
| [TECHNICAL_ARCHITECTURE.md](docs/TECHNICAL_ARCHITECTURE.md) | Modules, interfaces, états, validations, données, conservation et exploitation |
| [ARCHITECTURE_DECISIONS.md](docs/ARCHITECTURE_DECISIONS.md) | Comparaison de quatre architectures, raisons, alternatives et limites des choix |
| [DEVELOPMENT_ROADMAP.md](docs/DEVELOPMENT_ROADMAP.md) | Phases, dépendances, gates et autorisations avant développement/actions réelles |
| [API_INTEGRATIONS.md](docs/API_INTEGRATIONS.md) | Capacités documentées vs accès non testés, OAuth, endpoints, limites et sources LinkedIn |
| [FREE_SERVICES_BENCHMARK.md](docs/FREE_SERVICES_BENCHMARK.md) | Comparaison documentaire datée, quotas, pays, confidentialité, cartes et frais possibles |
| [TEST_STRATEGY.md](docs/TEST_STRATEGY.md) | Tests futurs, invariants de sécurité, pannes, recette humaine et preuves attendues |
| [APIFY_SKILL_AUDIT.md](docs/APIFY_SKILL_AUDIT.md) | Audit du skill Apify : fonctionnement, Actors, coûts, limites, conformité, intégration |
| [QUALIFICATION_TREG.md](docs/QUALIFICATION_TREG.md) | Runbook de qualification réelle treg (`/rest/posts` + image), prêt mais non exécuté ; chaque étape exige une autorisation distincte |

Les documents de spécification sont liés ci-dessus. Code : `src/linkedin_assistant/` (bibliothèque standard uniquement), tests dans `tests/`. Installation locale : `python -m venv .venv` puis `.venv/Scripts/python -m pip install -e ".[dev]"` ; tests : `.venv/Scripts/python -m pytest -q` ; démarrage : `.venv/Scripts/linkedin-assistant --config config.toml` (mode simulation sans jeton, voir `config.example.toml`) ; test interactif sans réseau : ajouter `--local`. Secrets : copier `.env.example` vers `.env` (ignoré par git) et renseigner vos clés en local ; ne jamais les coller dans le chat ni les logger.

## Risques et blocages prioritaires

| Risque | Effet | Réponse proposée |
|---|---|---|
| Application/scopes/OAuth non attestés (aucune app trouvée en local) | Publication ou renouvellement indisponibles | ~~Vérifier le portail pour une app existante avant toute création ; preuves d'accès séparées ; aucun contournement~~ **Couvert par treg (14 nov, ADR-16) : connexion active, identité et `w_member_social` vérifiés.** Reste : qualification réelle du POST et du parcours image, par test autorisé distinct ; gestion de la rotation treg |
| Historique incomplet | Couverture du style et rappels incertains | Import indépendant après droits/aperçu/accord (skill Apify audité) ; dates et couverture visibles, jamais trois posts comme plafond |
| Doublons, versions ou dates ambiguës | Fusion erronée ou mauvais rappel | ID typé prioritaire, repli conservateur texte + date précise/auteur/métadonnées ; arbitrage humain, pas de suppression silencieuse ni de null écrasant une valeur connue |
| Droits/transferts/conditions tunisiennes non vérifiés | Stockage ou destination interdits | Vérifier chaque usage/destination, refus sans droits, effacement propagé ; consentement insuffisant à lever une interdiction |
| Image non qualifiée ou tampon perdu | Autorisation image devenue inutilisable | Preuve image séparée ; nouvel aperçu et approbations image/finale, texte seul uniquement par choix explicite |
| Quota gratuit ou hôte indisponible | Traitement interrompu | Arrêt sans paiement, hôte et coûts indirects acceptés ; reprise/sauvegarde des seules données autorisées, jamais des binaires images |
| Réponse LinkedIn perdue | Doublon possible | Verrou du compte, zéro retry automatique, réconciliation ; import seul insuffisant |

## Décisions encore ouvertes avant développement

Résolus le 13 novembre 2026 : hébergement (PC utilisateur pour dev/tests, Oracle à étudier plus tard, ami en secours), fournisseurs LLM (Groq + OpenRouter à comparer, clés via `.env`), tableau de bord local planifié, rappel quotidien 10 h modifiable, audit du skill Apify. Restent à décider ou à fournir :

1. ~~**Application LinkedIn** : vérifier au portail développeur si une application existe déjà (aucune trouvée en local) ; produits/scopes visibles, callback OAuth réellement utilisable, identité et scopes vérifiés sans publier.~~ **Résolu le 14 novembre 2026 par treg (ADR-16)** : la connexion `linkedin` de treg (capability `write`, consentement utilisateur) fournit l'OAuth — identité (`sub`) et `w_member_social` vérifiés par `v2/userinfo` → 200, expiration 2027-01-13, sans application Developer propre ni callback local. **Restent :** qualification réelle du POST `/rest/posts` et du parcours image (tests distincts autorisés), acceptation des conditions/confidentialité du service treg, gestion de la rotation.
2. **Clés et consentements** : l'utilisateur crée le `.env` local (Groq, OpenRouter, Telegram, recherche) ; droits séparés stockage/analyse/dérivation/transfert par destination (Telegram inclus) ; restrictions tunisiennes et transferts à vérifier.
3. **Paramètres de données** : rétentions par origine, purge des brouillons proposée à 30 j sans toucher l’archive autorisée, RAM seule pour images ; seuils retrieval 6 posts/12 000 caractères et profil 4 000 caractères proposés ; seuil d’inactivité 120 h proposé.
4. **Préférences éditoriales progressives** : thèmes, public, ton, longueur, langue, exclusions, fréquence/horaires, préférences recherche/images, modèle LLM et fournisseur recherche — configurables (Telegram + tableau de bord, même SQLite), sans figer arbitrairement ; confirmation séparée de toute règle normative permanente.
5. ~~**Validation du périmètre de la Phase 1 révisée** avant de poursuivre le codage~~ **Validé le 14 novembre 2026, avec ordre ajusté :** 1. secrets/`.env` + validation au démarrage, 2. rappel 10 h, 3. contrat `Publisher` (prêt pour l'adaptateur treg), puis paramètres partagés, abstraction LLM + harness, squelette dashboard. Voir [feuille de route](docs/DEVELOPMENT_ROADMAP.md).

## Prochaine étape

Les phases 2 à 4 et le cœur local des rappels sont livrés (75 tests, publication simulée). Le périmètre de la Phase 1 volet B est **validé (14 novembre 2026)** : implémentation locale simulée en cours, sans action externe (secrets `.env` + validation au démarrage, rappel 10 h, contrat `Publisher` avec résolution dynamique treg, paramètres partagés, abstraction LLM Groq/OpenRouter + harness, squelette du tableau de bord local). La publication réelle via treg (`POST /rest/posts`) reste **NON TESTÉE** et exigera une autorisation distincte sur le contenu exact. Chaque action externe exige une autorisation distincte ; le skill Apify original reste inchangé.
