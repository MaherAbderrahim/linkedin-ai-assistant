# Registre des décisions d’architecture

Date : 13 novembre 2026, Mission 0.6. **Socle validé :** Python + SQLite central, Telegram principal, n8n facultatif, Tunisie/`Africa/Tunis`, API officielle LinkedIn, 0 € sans paiement obligatoire ni fallback payant, validations texte/image distinctes puis finale, fournisseurs modulaires, archive textuelle durable sans fichiers images. **Décisions du 13 novembre :** hébergement local (PC utilisateur), Groq/OpenRouter à comparer, tableau de bord local, rappel quotidien 10 h modifiable, skill Apify audité. Les ADR ci-dessous détaillent ce socle ; les modalités signalées proposées (seuils, durées, RAM seule) restent à approuver. Aucune décision ne prouve un accès fournisseur ni n’autorise une action externe.

## Comparaison des architectures

| Option | Atouts pour ce projet | Coûts/limites | Conclusion |
|---|---|---|---|
| A. n8n Community seul | Planification et assemblage visuel de connecteurs ; bonne lisibilité d’un flux simple | Corrections conversationnelles, snapshots d’approbation, concurrence et envoi incertain deviennent vite complexes ; éditeur/base internes à maintenir ; Telegram Trigger natif nécessite webhook HTTPS | Possible, mais pas le plus simple pour les invariants de sécurité demandés |
| B. n8n + service Python + SQLite métier | Interface visuelle pour orchestration, code précis pour publication/recherche | Deux environnements et deux persistances potentielles, authentification inter-services, reprise distribuée ; risque de deux chemins de publication | À réserver à un besoin explicite de workflows visuels |
| C. Python modulaire + SQLite | Un état métier, un déploiement, tests de panne précis ; long polling sans webhook public Telegram | Moins d’édition visuelle ; code applicatif à maintenir ; besoin d’un hôte actif | **Option recommandée** |
| D. Fonctions serverless + scheduler + base hébergée | Pas de VM à administrer en apparence | Quotas, stockage/cron/webhook dispersés, durée de tâches et sommeil gratuits variables, dépendance accrue au cloud ; gratuité complète non vérifiée | Non retenue sans nécessité démontrée |

Ce choix résulte du besoin de validations fiables et de maintenance simple, pas de la popularité d’un framework.

## ADR-01 — Un monolithe modulaire Python

**Décision proposée :** un processus et des adaptateurs internes ; modules conversation, recherche, rédaction, images, préférences, publication et exploitation. Pas de framework d’agents autonome ni de service web permanent par défaut.

**Pourquoi :** l’essentiel du risque est dans les états, versions et effets de bord, pas dans le débit. Une personne et quelques posts ne nécessitent pas de microservices.

**Alternative gratuite :** n8n CE ; combinaison n8n/Python si un éditeur visuel devient un besoin confirmé.

**Limites :** nécessite de développer une petite logique métier ; l’indisponibilité de l’hôte arrête toutes les fonctions.

**Remplacement :** adaptateurs remplaçables séparément. Un changement d’orchestrateur devra préserver les contrats d’approbation et de stockage ; ce n’est pas un simple changement de configuration.

**Reconsidérer si :** plusieurs workflows indépendants doivent être entretenus visuellement par une personne non développeuse, ou la charge réelle l’exige.

## ADR-02 — SQLite, pas une base pour chaque service

**Décision (validée) :** une base métier locale centrale, avec transactions, révisions immuables, registre d’envoi distinct de l’archive historique, file d’événements légère, profil descriptif et règles confirmées séparés. Aucun binaire image en base ni sur disque (RAM seule proposée) ; pas de base vectorielle.

**Pourquoi :** reprise et anti-doublon exigent une persistance transactionnelle. Fichiers de conversation ou état n8n seuls ne prouvent pas l’unicité d’un envoi.

**Alternative gratuite :** PostgreSQL auto-hébergé ; fichier JSON pour paramètres statiques uniquement, pas pour les garanties d’envoi.

**Limites :** un hôte actif, stockage local, écritures courtes ; pas de partage SQLite par réseau ni de réplication multi-écrivains. Sauvegarde WAL cohérente et restauration contrôlée nécessaires.

**Remplacement :** frontière de dépôt interne ; migration possible vers PostgreSQL avec reprise des clés d’unicité et tests de concurrence. Pas d’ORM obligatoire avant qu’un besoin apparaisse.

## ADR-03 — Telegram en long polling

**Décision proposée :** Bot API officielle, chat privé, propriétaire autorisé, réception par long polling.

**Pourquoi :** dialogue et rappels individuels sans coût par message ordinaire, pas de domaine ni de serveur public entrant pour Telegram.

**Alternative gratuite :** webhook Telegram si un HTTPS fiable existe déjà ; WhatsApp Cloud API pour des réponses réactives dans ses quotas, mais pas une garantie de rappels gratuits hors fenêtre.

**Limites :** bot à démarrer par l’utilisateur, événements conservés 24 h maximum côté Telegram, service hôte actif ; chat bot non chiffré de bout en bout.

**Remplacement :** adaptateur conversation. L’ajout d’un canal doit reproduire des validations explicites et traçables, pas simplement transmettre du texte.

**Point non résolu par ce choix :** callback OAuth LinkedIn ; le vérifier indépendamment.

## ADR-04 — API LinkedIn officielle et capabilities séparées

**Décision proposée :** cible `/rest/posts`, version supportée explicitement choisie ; `w_member_social` pour publier. Autorisations de lecture historique et statut média suivies séparément.

**Pourquoi :** respecter l’exigence officielle et éviter un bot de navigateur fragile/suspendable. Le guide moderne remplace UGC, mais son accès effectif doit être testé pour l’application.

**Alternative gratuite :** aucune alternative automatisée retenue si les permissions officielles ne sont pas obtenues. Fournir le brouillon à l’utilisateur préserve la préparation mais **ne remplit pas** la fonction de publication automatique.

**Limites :** applications/produits, OAuth, scopes, renouvellement non garanti, versionnement, quotas et permissions images. `r_member_social` est restreint ; `w_member_social` seul ne lit pas le statut image versionné.

**Vérification du 13 novembre 2026 :** aucune intégration LinkedIn antérieure trouvée dans l'espace de travail (uniquement des scrapers d'offres publics sans rapport). La publication personnelle `w_member_social` + OIDC ne requiert pas intrinsèquement de page entreprise (LI-9 : « certaines fonctionnalités et certains produits »), mais toute intégration OAuth officielle exige une application Developer (`client_id`). Vérifier le portail pour une application existante avant toute création ; ne rien contourner. Interface `Publisher` abstraite et remplaçable, simulateur en place jusqu'à l'accès réel. **Mise à jour du 14 novembre 2026 :** l'accès OAuth est désormais provisionné via treg (proxy de credentials, ADR-16) — connexion `linkedin` health=ok, `w_member_social` et identité vérifiés, sans application Developer propre ; la publication réelle reste NON TESTÉE et exige une autorisation distincte.

**Remplacement :** changer la version ou l’adaptateur officiel après tests ; jamais une API privée ou Apify comme solution de publication.

**Gate :** validation du compte, du texte et de l’image dans des tests séparés, chaque action réelle autorisée.

## ADR-05 — Archive centrale multi-provenance et import indépendant du fournisseur

**Décision (principe validé, modalités proposées) :** SQLite conserve durablement tous les textes de publications dont la rétention est permise, sans plafond de trois posts. Source A : texte original exact archivé avec le reçu et le succès dans une transaction locale atomique, seulement après confirmation fiable de LinkedIn. Source B : import via un contrat indépendant d’Apify (originaux utilisateur, export autorisé du skill audité, autre outil conforme, API conforme), avec droits vérifiés avant persistance, parsing borné, comparaison, aperçu immuable, accord lot/éléments et commit idempotent.

**Pourquoi :** la continuité éditoriale exige un historique réel, pas une fenêtre de trois exemples ; ne pas rendre le cœur dépendant d’un skill externe ni d’un droit de lecture non acquis. Distinguer publication, lecture, conservation et transfert.

**Déduplication proposée :** identifiant LinkedIn typé complet prioritaire (pas d’assimilation des suffixes share/ugcPost/activity) ; repli conservateur texte normalisé versionné + date précise + auteur + métadonnées. Même ID/texte changé ⇒ nouvelle version confirmée ; null n’écrase pas connu ; IDs différents/textes proches peuvent être des posts distincts ; absence d’un lot ≠ suppression ; ambiguïtés arbitrées humainement. Provenance réelle et observations conservées ; un export API remis par l’utilisateur reste d’origine API. Un import ne résout jamais automatiquement `UNKNOWN_OUTCOME`.

**Alternative gratuite :** originaux copiés/exportés par l’utilisateur ; lecture officielle si le scope restreint et les conditions sont obtenus. Le skill Apify a été audité le 13 novembre 2026 (voir [APIFY_SKILL_AUDIT.md](APIFY_SKILL_AUDIT.md)) : intégration par l’import générique (export utilisateur préféré), original inchangé, collecte non conforme hors socle.

**Limites :** l’import demande une action humaine et des droits vérifiés par origine/usage/destination ; l’application ne détecte pas les posts externes non importés. Les 48 h des Data Storage Requirements visent l’activité sociale des Marketing APIs, pas tous les originaux ni toute collecte Apify ; la règle applicable plus stricte prime, y compris contre l’objectif d’archive complète. Droits inconnus ⇒ aucune persistance provisoire.

**Remplacement :** adaptateurs ImportProvider/HistoryProvider interchangeables ; le schéma d’archive et les règles de versionnement restent stables quel que soit le fournisseur de collecte.

## ADR-06 — Contrôle déterministe des validations

**Décision proposée :** texte approuvé + image ou absence approuvée + autorisation finale courte, à usage unique, liée au manifeste exact. Le LLM n’a pas accès à l’outil de publication.

**Pourquoi :** une conversation naturelle n’est pas une autorisation vérifiable ; les versions doivent empêcher qu’un ancien bouton publie un nouveau contenu.

**Alternative gratuite :** commande déterministe avec référence et confirmation explicite plutôt que boutons ; mêmes règles de portée requises. Une décision LLM « l’utilisateur semble d’accord » est exclue.

**Limites :** davantage de confirmations, volontairement. Une modification nécessite une revalidation adaptée ; aucune transformation cachée après accord.

**Remplacement :** changer la présentation Telegram sans modifier le contrat d’approbation. Passage à une publication différée/autonome hors scope et nécessitant une nouvelle décision utilisateur.

## ADR-07 — Envoi au plus une tentative incertaine, pas de promesse exactly-once

**Décision proposée :** registre durable, verrou par compte, unicité par brouillon et comparaison d’empreinte de contenu entre brouillons. Un envoi incertain n’est jamais rejoué automatiquement.

**Pourquoi :** un timeout peut survenir après création chez LinkedIn. Sans idempotence serveur garantie ni transaction distribuée, le client seul ne peut pas prouver exactement une publication dans toutes les pannes.

**Alternative gratuite :** réconciliation par lecture officielle si autorisée, sinon vérification manuelle. Un retry systématique n’est pas une alternative acceptable.

**Limites :** le service peut bloquer pour éviter un doublon ; une absence immédiate dans le fil n’est pas une preuve de non-publication. Après restauration d’une sauvegarde, réconciliation préalable obligatoire.

**Remplacement :** une garantie d’idempotence officielle future pourrait améliorer l’adaptateur, après vérification ; garder les contrôles locaux.

## ADR-08 — LLM hébergés Groq + OpenRouter, comparaison avant sélection

**Décision utilisateur (13 novembre 2026) :** retenir **Groq (API officielle) et OpenRouter (API unifiée)** pour comparer plusieurs modèles des deux fournisseurs. Critères : qualité du français, suivi des instructions, reproduction du style, latence, limites d’usage. Changement de modèle/fournisseur facile via un contrat `LLMProvider` unique et un paramètre. **Aucun modèle sélectionné définitivement avant les tests comparatifs.** Clés fournies par l’utilisateur via `.env`.

**Pourquoi :** pas de modèle local requis ni de crédits achetés ; comparer sur des tâches réelles autorisées plutôt que sur un classement non mesuré. Groq documente des contrôles ZDR ; la confidentialité d’OpenRouter dépend aussi du fournisseur amont.

**Alternative gratuite :** Gemini Free (clause informations personnelles interdisant l’envoi automatique des posts bruts), Workers AI — documentées, non retenues au socle. Édition manuelle temporaire si aucun fournisseur conforme n’est accessible.

**Limites :** free tiers changeants, modèles retirés, contextes/débits variables, données traitées par des tiers. OpenRouter : variantes `:free` uniquement, plafond supérieur lié à un achat exclu, aucun routage payant.

**Remplacement :** `LLMProvider` ; recette de non-régression et revue des données avant bascule. **Aucun fournisseur payant sans autorisation, aucun basculement automatique vers du payant** ; quota épuisé = arrêt.

## ADR-09 — Recherche Tavily basic et extraction locale bornée

**Décision proposée :** Tavily Free pour trouver les sources, HTTP contrôlé + Trafilatura pour lire les pages publiques, dossier d’affirmations traçables avant rédaction.

**Pourquoi :** 1 000 crédits récurrents/mois sans carte documentés ; extraction indépendante limitant la dépendance au moteur. Recherche approfondie signifie corroboration et traçabilité, pas crawler illimité.

**Alternative gratuite :** Brave sous prépayé 0 $, carte et absence d’auto-reload vérifiées ; RSS/sites sélectionnés/liens utilisateur pour une couverture partielle.

**Limites :** les moteurs ne prouvent pas les faits ; pages inaccessibles, droits, sources contradictoires et quotas. Brave et grounding peuvent entraîner des frais si mal configurés.

**Remplacement :** SearchProvider/Extractor distincts ; aucune représentation spécifique Tavily ne doit traverser l’interface métier.

## ADR-10 — Images existantes, génération non nécessaire

**Décision (principe validé, modalité proposée) :** une image statique maximum, Commons en priorité, dossier de droits et fichier figé avant approbation ; génération désactivée ; **aucun archivage de fichier image**. Modalité proposée : octets en RAM seule de bout en bout (pas de BLOB, fichier temporaire applicatif ni sauvegarde binaire), seules métadonnées/empreintes/droits autorisés persistés. Perte du tampon ⇒ nouvel aperçu et approbations image/finale ; aucune promesse sur le swap OS ni les copies Telegram/LinkedIn.

**Pourquoi :** minimum de coût, de complexité et de risques ; l’image n’est pas nécessaire à chaque post. Valider le texte ne valide pas une image trouvée ensuite.

**Alternative gratuite :** photo fournie par l’utilisateur avec droits confirmés, Pexels après lecture des conditions ; Unsplash après clarification de hotlinking/republication.

**Limites :** licences fichier par fichier, droit à l’image/marques, métadonnées imparfaites, éventuelles obligations de crédit et gate technique LinkedIn distinct. Gratuit ne signifie pas libre de toute condition.

**Remplacement :** ImageProvider ; extension de génération uniquement si gratuité récurrente, droits et confidentialité démontrés. Si le fournisseur échoue, proposer « sans image » et demander une nouvelle validation, jamais retirer l’image automatiquement.

## ADR-11 — Deux couches de mémoire et consultation ciblée

**Décision (principe validé, seuils proposés) :** archive textuelle autorisée d’une part ; profil rédactionnel compact persistant d’autre part, séparé des règles normatives. Le profil contient des observations descriptives recalculables (longueurs, ton, structures, thèmes, évolution) avec références de versions, période, couverture et confiance ; les textes assistant sont identifiés pour éviter de renforcer le style IA comme préférence humaine. Toute règle permanente exige une confirmation distincte de son texte exact ; aucune inférence d’attribut sensible.

**Consultation proposée :** filtres SQLite indexés (auteur/date/provenance/droits) + FTS5 si disponible, échantillons récents/thématiques/par période, au plus 6 posts et 12 000 caractères cumulés, profil ≤4 000 caractères ; règles confirmées fournies séparément, jamais tronquées silencieusement. Trois posts récents = échantillon, pas limite de stockage. Jamais toute l’archive relue/transmise à chaque génération ; reconstruction exceptionnelle locale par lots bornés.

**Pourquoi :** continuité éditoriale sans mémoire opaque ni dérive normative ; un résumé n’est pas une consigne. Les dérivés (profil, index FTS, empreintes soumises aux règles) héritent des restrictions et effacements de leurs sources ; vérifier les droits à la lecture et juste avant chaque destination, Telegram inclus.

**Alternative gratuite :** règles dans un fichier modifiable manuellement ; recherche LIKE bornée si FTS5 absent. Pas de base vectorielle ni de corpus de conversations.

**Limites :** profil partiel si sources partielles ; un profil mixte non exportable doit être exclu/recalculé avant transfert. Conservation du registre d’envoi tant que le service est actif, dans les limites permises ; aucune promesse d’effacer les copies des fournisseurs.

**Remplacement :** export des règles acceptées et des observations autorisées, import validé ; le moteur de retrieval peut changer sans modifier le contrat d’approbation.

## ADR-12 — PC de l’utilisateur pour dev/tests, cloud étudié plus tard

**Décision utilisateur (13 novembre 2026) :** développement et premiers tests sur le **PC de l’utilisateur**. **Oracle Always Free à étudier plus tard** ; PC d’un ami en secours. **Aucune installation ni déploiement distant maintenant** ; le développement n’est pas bloqué par le choix d’hébergement définitif.

**Pourquoi :** pas d’attente d’allocation cloud ni de VM gratuite promise avant création réelle ; un seul processus reste facile à déplacer.

**Alternative gratuite :** Oracle éligible dans quotas effectifs, sans conversion payante, après étude ; autre matériel existant autorisé.

**Limites :** disponibilité du PC, administrateur ayant accès aux secrets, électricité ; Oracle peut refuser la capacité ou récupérer une instance inactive. Les anciennes allocations Oracle ne sont pas reprises comme garanties.

**Remplacement :** sauvegarde cohérente, arrêt de l’ancien hôte, restauration du nouveau en publication bloquée, réconciliation, réactivation. Ne pas lancer les deux hôtes simultanément.

## ADR-13 — Budget 0 € comme contrainte de sécurité

**Décision proposée :** comptes/offres gratuits vérifiés, aucun PAYG/auto-reload/billing activé par le bot, réservations de quota avant appel, pause explicite au plafond. Allocation gratuite récurrente admise ; crédit initial seul refusé.

**Pourquoi :** un plafond d’alerte n’est pas nécessairement un plafond de facturation. Les garanties doivent venir à la fois de la configuration du compte et de l’application.

**Alternative gratuite :** réduire le volume, attendre le renouvellement ou utiliser une alternative déjà approuvée ; pas de multiplication de comptes pour contourner les limites.

**Limites :** impossible de garantir éternellement l’offre d’un tiers ni zéro coût d’électricité. Si aucun fournisseur conforme n’est accessible, la fonction concernée reste bloquée.

**Remplacement :** nouvelle vérification datée des termes, test et consentement ; aucune modification du budget sans décision utilisateur distincte.

## ADR-14 — Tableau de bord web local, configuration partagée

**Décision utilisateur (13 novembre 2026) :** tableau de bord web **local** (localhost, port 8000 proposé), simple/clair/moderne, à développement progressif. Sections : configuration générale, éditoriale, IA (fournisseurs/modèles/benchmarks), recherches, historique (archive + statuts), état système (services/erreurs/quotas/dernières exécutions). **Telegram et tableau de bord partagent la même configuration SQLite** (`settings`), une seule source de vérité.

**Pourquoi :** visualiser et ajuster les paramètres progressifs sans dupliquer la logique métier ; garder un seul processus et une seule base.

**Alternative gratuite :** configuration par commandes Telegram seule (déjà possible) ; le tableau de bord est un confort, pas un prérequis.

**Limites :** lié à 127.0.0.1, aucune exposition publique au socle ; un administrateur de l’hôte accède aux processus/données. **Si exposition Internet ultérieure : authentification et protection des secrets obligatoires** avant accessibilité. Pas de second chemin de publication : mêmes validations déterministes et même registre d’intentions.

**Remplacement :** serveur HTTP stdlib remplaçable ; le contrat de configuration et les validations restent stables.

## ADR-15 — Secrets par fichier d’environnement local

**Décision utilisateur (13 novembre 2026) :** secrets dans `.env` local (ignoré par git), `.env.example` factice versionné avec commentaires. L’utilisateur crée lui-même le vrai `.env`.

**Pourquoi :** aucune clé dans le code ni versionnée ; séparation secrets (`.env`) / paramètres non secrets (`config.toml` + SQLite).

**Règles :** ne jamais intégrer de clé dans le code ; ne jamais afficher les clés dans les logs ; ne jamais demander de coller une clé dans une conversation ou un prompt ; vérifier les variables manquantes au démarrage par leur nom, avec messages explicites sans révéler leur contenu.

**Limites :** un fichier local reste lisible par l’administrateur de l’hôte ; permissions minimales, pas de secret en base ni dans Telegram.

**Remplacement :** coffre du système possible plus tard sans changer le contrat de chargement.

## ADR-16 — Accès de publication via treg, proxy de credentials

**Décision utilisateur (14 novembre 2026) :** l'accès à l'API officielle LinkedIn passe par **treg** (treg.to), proxy de credentials hébergé, piloté par le CLI `tools-registry` 0.30.0 (pip --user). L'utilisateur a créé puis reconnecté la connexion `linkedin` (capability `write`, consentement navigateur) ; le secret OAuth est détenu par treg, jamais par l'application ni par un fichier local. Connexion vérifiée : `treg call linkedin v2/userinfo` → 200, scope `w_member_social` présent, expiration attestée 2027-01-13.

**Pourquoi :** résout le point laissé ouvert par ADR-03 (callback OAuth LinkedIn sans serveur public) sans créer d'application Developer propriétaire ni gérer de secret local LinkedIn, tout en restant sur l'API officielle `/rest/posts` avec l'OAuth propre du membre. Publication non mesurée (0 $) car elle emprunte l'OAuth du membre via treg, pas un quota de service.

**Fonctionnement attesté par le catalogue treg (pas encore éprouvé par un POST réel) :** `treg call linkedin rest/posts --method POST` avec en-têtes `LinkedIn-Version: YYYYMM` et `X-Restli-Protocol-Version: 2.0.0`, corps JSON fourni par fichier. Succès attendu **HTTP 201 avec l'URN dans l'en-tête `x-restli-id`** (corps vide) — seule preuve de publication acceptable, jamais le scraping treg. Corps : `author` = `urn:li:person:UkLKzuK9bT` (resource_ref fournie par treg, utilisée telle quelle), `commentary` (échappement backslash des caractères `( ) [ ] { } < > @ | ~`), `visibility` PUBLIC ou CONNECTIONS annoncée à l'utilisateur, distribution `MAIN_FEED`, `lifecycleState` PUBLISHED, `isReshareDisabledByAuthor` false.

**Rotation (contrainte forte pour l'adaptateur) :** la rotation périodique de treg révoque les secrets ; chaque reconnexion crée un nouveau nom `linkedin-N`. **L'adaptateur Publisher futur doit résoudre dynamiquement la connexion `linkedin` health=ok via `treg connections ls`** — jamais de nom ni de secret en dur. L'ancien doublon révoqué est laissé en place (inoffensif).

**Coûts et précautions :** crédit d'essai unique treg de 1,00 $ (reste 0,9921 $ au 14 nov) ; la publication est 0 $. **Endpoints mesurés à éviter :** `treg.linkedin.user.posts`, `treg.linkedin.post.detail`, `treg.google.serp.organic` (~0,008 $ déjà consommés lors de la découverte). Recherche web : Tavily, jamais treg. Les analytics de posts membres ne sont pas exposées par treg (réservées aux Pages). Bug machine connu : `NO_PROXY` système contient `[::1],::1`, mal parsé par httpx, ce qui fait planter chaque commande treg ; palliatif = préfixer `NO_PROXY=` (vide) à chaque invocation, sans modifier la configuration globale.

**Limites :** dépendance à un service tiers hébergé (disponibilité, conditions, confidentialité du flux d'appels) ; secret détenu à distance ; télémétrie treg désactivée (`TREG_TELEMETRY=0`) ; skill treg installé en mode CLI-only volontaire, sans fan-out de skills. Aucun test de publication réel effectué à ce stade : la qualification documentaire de `/rest/posts` via le catalogue treg ne prouve pas un POST réussi — celui-ci exigera une autorisation distincte sur le contenu exact (Phase 6). Les 8 Mo et formats d'image annoncés par le catalogue restent à vérifier au test.

**Remplacement :** le contrat `Publisher` reste abstrait (SimulatedPublisher en place) ; un adaptateur `TregPublisher` n'est codé qu'après bouclage du volet A de la Phase 1 et accord explicite. Si treg devient inutilisable, l'interface reste remplaçable par un adaptateur OAuth direct (application Developer, ADR-04) sans changer le socle ni les validations.

## Décisions encore humaines

Déjà résolus : Python + SQLite, Telegram principal/n8n facultatif, Tunisie/`Africa/Tunis`, API officielle, 0 €, validations séparées, archive textuelle sans fichiers images ; hébergement local (PC utilisateur), Groq/OpenRouter à comparer, tableau de bord local, rappel quotidien 10 h modifiable, audit du skill Apify ; accès de publication via treg (ADR-16, 14 nov 2026, identité vérifiée, publication NON TESTÉE). Restent : validation des modalités proposées (seuils, durées, RAM seule), qualification réelle de `/rest/posts` et du parcours image par un test autorisé distinct, consentements restants par usage/destination, droits des imports, sujets et paramètres éditoriaux progressifs, jours des rappels et seuil 120 h, sélection du modèle après comparaison, validation du périmètre Phase 1 (volet B validé le 14 nov avec ordre ajusté : secrets, rappel 10 h, contrat Publisher d'abord), autorisation future de tests de publication séparés. Voir [README.md](../README.md) et [feuille de route](DEVELOPMENT_ROADMAP.md).

## Références de décision

Les chiffres, offres et niveaux de preuve sont centralisés dans [FREE_SERVICES_BENCHMARK.md](FREE_SERVICES_BENCHMARK.md). Les scopes, endpoints et sources LinkedIn sont centralisés dans [API_INTEGRATIONS.md](API_INTEGRATIONS.md). Les règles normatives de comportement sont dans [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md) et les invariants techniques dans [TECHNICAL_ARCHITECTURE.md](TECHNICAL_ARCHITECTURE.md).
