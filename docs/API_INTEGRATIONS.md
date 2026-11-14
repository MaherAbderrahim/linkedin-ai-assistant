# Intégrations API et vérification de faisabilité

Date de référence : 13 novembre 2026, Mission 0.6 ; **mise à jour du 14 novembre 2026 (décision treg, ADR-16)**. **Vérification documentaire uniquement : aucune publication ni aucun transfert média réalisé.** Le socle local (archive SQLite, import générique, profil, retrieval, rappels) est implémenté et testé sans réseau ; les endpoints ci-dessous restent des spécifications pour les phases futures, pas des appels exécutés — exception : l'identité LinkedIn a été vérifiée une fois via treg (`v2/userinfo` → 200), sans publication. L'archive centrale et l'import indépendant sont décrits dans [l'architecture](TECHNICAL_ARCHITECTURE.md) ; ce document fixe les protocoles et conditions par intégration.

## 1. Registre des capacités

| Intégration/capacité | État documentaire | État sur compte utilisateur | Conséquence |
|---|---|---|---|
| Telegram : messages et rappels après démarrage du bot | Documentée | NON TESTÉ | Créer/configurer le bot ultérieurement avec autorisation |
| LinkedIn : OAuth et identification du membre | Documentés ; produits/scopes requis | **ACCÈS VÉRIFIÉ via treg** (14 nov : `v2/userinfo` → 200, `w_member_social`, expiration 2027-01-13) | Secret détenu par treg, jamais localement ; adaptateur à résolution dynamique de connexion |
| LinkedIn : publier un texte personnel | `w_member_social` documenté pour création ; parcours treg attesté par le catalogue | NON TESTÉ (aucun POST réel) | Endpoint exact à éprouver après consentement spécifique à une publication de test (Phase 6) |
| LinkedIn : lire l’historique des posts | `r_member_social` restreint | NON TESTÉ, accès non présumé | Import indépendant (originaux utilisateur, skill audité, autre source conforme) comme solution de départ |
| Archive centrale SQLite et import générique | Contrats internes | IMPLÉMENTÉ localement (tests sans réseau) | Indépendant d’Apify et du droit de lecture ; droits par origine avant persistance |
| LinkedIn : initialiser/téléverser une image | Documenté avec permissions adaptées | NON TESTÉ | Gate indépendant du texte |
| LinkedIn : lire le statut d’une image | `w_member_social` seul insuffisant pour GET versionné | NON TESTÉ | Ne pas baser le pipeline sur un polling inaccessible |
| Groq : génération | Offre et conservation documentées | NON TESTÉ | Retenu pour comparaison avec OpenRouter ; modèle/quota/région/consentement à qualifier |
| OpenRouter : génération unifiée | Variantes `:free` documentées | NON TESTÉ | Comparaison multi-modèles ; aucun routage payant ; confidentialité amont à vérifier |
| Tavily : recherche basic | Gratuit récurrent documenté | NON TESTÉ | Compte Free sans PAYG, test ultérieur |
| Commons : recherche et métadonnées | API publique documentée | NON TESTÉ en intégration | Vérifier licences et conditions fichier par fichier |
| Skill Apify | Fichiers locaux lus | AUDITÉ (documentaire, 13 nov) | Voir APIFY_SKILL_AUDIT.md ; Actors community/PPE ; aucune exécution ; import générique préféré |
| treg (proxy de credentials) | Catalogue lu, identité vérifiée via connexion `linkedin` | **CONNEXION ACTIVE** (secret côté treg, rotation connue) | Publication via `/rest/posts` (0 $) ; éviter les endpoints mesurés ; preuve = 201 + URN `x-restli-id` |
| Tableau de bord web local | Architecture proposée | NON IMPLÉMENTÉ | localhost, même SQLite que Telegram ; jamais public sans protection |
| Génération d’image | Aucune offre compatible établie | NON ACTIVÉ | Hors socle |
| Oracle Always Free | Offre documentée | NON TESTÉ | Capacité, carte, région, coûts et conditions à valider |

**Une page officielle qui décrit un scope ne prouve pas que l’application l’a reçu ; un scope reçu ne prouve pas à lui seul le fonctionnement de tous les endpoints.** Stocker séparément produits autorisés, scopes consentis, résultat des tests et date de vérification.

## 2. LinkedIn — choix de protocole

### 2.1 Périmètre

Publier sur le **profil personnel du membre authentifié**, pas une organisation. Aucun commentaire/like, message privé, automatisation de navigateur, cookie LinkedIn ou API privée. Aucun outil Apify n’est un adaptateur de publication.

La documentation Share on LinkedIn présente `w_member_social` comme une permission ouverte ajoutable en self-service dans les produits de l’application. Elle illustre encore le chemin historique `POST /v2/ugcPosts`. La documentation moderne Posts API indique que **Posts remplace ugcPosts** et documente `POST /rest/posts` avec `w_member_social` pour les membres. [LI-1 à 3]

**Choix proposé : cibler `/rest/posts`, sous réserve de validation effective pour cette application.** Cette divergence entre guide self-service historique et documentation versionnée n’est pas masquée. Si le produit/scopes effectivement obtenus ne donnent pas accès au chemin moderne, suspendre l’intégration et vérifier une voie officielle encore supportée avec LinkedIn ; ne pas basculer silencieusement vers un ancien endpoint ni du scraping.

La documentation consultée affiche `202610` comme version la plus récente de sa page de versionnement. C’est une référence documentaire, pas une preuve qu’une application peut l’utiliser. Au développement, choisir explicitement une version alors supportée et testée ; ne pas calculer la version à partir du mois courant. [LI-8]

### 2.2 Prérequis d’application

1. Application dans le portail développeur LinkedIn ; produits visibles et accordés.
2. Vérifier si l’association à une Page LinkedIn et sa validation par une personne super-administratrice sont requises dans le parcours réel. L’aide dit « pour certaines fonctionnalités et certains produits » : ce n’est pas automatiquement une permission de publier sur cette Page. [LI-9]
3. Produit Share on LinkedIn et scope `w_member_social` disponibles pour la publication personnelle.
4. Produit Sign in with LinkedIn using OpenID Connect, scopes `openid profile` pour l’identité ; `email` inutile au besoin et non demandé par défaut. [LI-4]
5. URL de redirection exacte enregistrée et chemin OAuth réellement utilisable depuis le navigateur de l’utilisateur.
6. Conditions d’utilisation acceptées par l’utilisateur et secrets installés par un canal local sûr, pas dans Telegram ni cette documentation.

Ne pas promettre une approbation automatique de produit, l’absence de conditions de Page ni une disponibilité universelle selon les régions/comptes.

**Vérification de l'existant (13 novembre 2026) :** aucune intégration LinkedIn antérieure trouvée dans l'espace de travail `D:\PFE` — uniquement des scrapers d'offres d'emploi publics (`_work/li_crawl.py`, `li.py`, `li_filter.py`) sans rapport avec la publication, aucune application Developer, aucun `client_id`/secret/jeton. La « méthode précédente » n'existe que dans la documentation. **Action utilisateur :** vérifier au portail développeur si une application existe déjà avant toute création. La publication personnelle `w_member_social` + OIDC ne requiert pas intrinsèquement de page entreprise (LI-9), mais une application Developer reste nécessaire pour l'OAuth. L'interface `Publisher` est abstraite et remplaçable ; simulateur en place jusqu'à l'accès réel. Aucun contournement.

**Mise à jour du 14 novembre 2026 (treg, ADR-16) :** le parcours retenu n'exige plus d'application Developer propre ni de callback OAuth local. L'accès passe par treg (proxy de credentials hébergé), dont la connexion `linkedin` (capability `write`) a été créée puis reconnectée **par l'utilisateur avec consentement navigateur** après une révocation de rotation. Connexion vérifiée : `treg call linkedin v2/userinfo` → 200, `sub` membre `UkLKzuK9bT`, scope `w_member_social`, expiration 2027-01-13. Le secret reste côté treg ; aucun jeton LinkedIn n'est stocké localement. **Conséquences :** (1) les prérequis 1 à 5 ci-dessus sont couverts par la connexion treg, pas par une application de l'utilisateur ; (2) la rotation périodique de treg crée un nouveau nom `linkedin-N` à chaque reconnexion — **l'adaptateur doit résoudre dynamiquement la connexion `linkedin` health=ok via `treg connections ls`, jamais de nom ni de secret en dur** ; (3) la qualification réelle de `/rest/posts` (POST + image) reste NON TESTÉE et attend une autorisation distincte.

### 2.3 OAuth, identité et renouvellement

Endpoints officiels documentés :

| Opération | Endpoint | Contrôle |
|---|---|---|
| Autorisation membre | `GET https://www.linkedin.com/oauth/v2/authorization` | Code flow, client_id, scopes minimaux, redirect_uri exacte, state aléatoire |
| Échange code/jeton | `POST https://www.linkedin.com/oauth/v2/accessToken` | Secret gardé côté application, code à usage unique, redirection cohérente |
| Identité | `GET https://api.linkedin.com/v2/userinfo` | Scope adéquat, vérifier compte attendu, ne pas demander email inutilement |

Le guide de partage renvoie à OIDC pour obtenir l’identité permettant l’auteur `urn:li:person:{identifiant}`. Vérifier le `sub` renvoyé pour l’application, son emploi selon le guide en vigueur, et le compte affiché dans le préflight ; ne pas extraire un identifiant depuis une URL publique de profil. Les identifiants OIDC sont pairwise : ne pas supposer un identifiant universel réutilisable entre applications. Si l’ID token est utilisé, valider signature, issuer, audience, expiration et nonce par une bibliothèque appropriée. [LI-4, 5]

Le guide annonce une durée de 60 jours pour les jetons d’accès ; **`expires_in` de la réponse fait foi**. Les refresh tokens programmatiques ne sont disponibles que pour certaines applications/partenaires éligibles : ne pas les supposer fournis par Share on LinkedIn. Prévoir une nouvelle autorisation interactive si nécessaire, une alerte avant expiration et le maintien des fonctions éditoriales. Un refresh token, lorsqu’il existe, a sa propre expiration et peut être révoqué. [LI-5, 6]

Le long polling Telegram ne fournit pas un callback LinkedIn. Vérifier le mode de redirection local ou HTTPS avant développement ; l’acceptation d’un callback local n’est pas affirmée ici. Pas de flux device-code LinkedIn inventé, ni de jeton échangé en clair dans la messagerie.

### 2.4 Publication texte

Cible : `POST https://api.linkedin.com/rest/posts`.

En-têtes : `Authorization: Bearer …`, `Content-Type: application/json`, `X-Restli-Protocol-Version: 2.0.0`, `Linkedin-Version: YYYYMM` supporté et vérifié.

Contrat de contenu : auteur membre, commentaire/texte exact, visibilité approuvée, distribution appropriée et état de publication conforme à l’API. L’adaptateur construit la représentation attendue ; il n’ajoute jamais de texte, hashtags, lien ou image non présent dans le manifeste final.

La documentation décrit un succès **201** avec identifiant du post dans **`x-restli-id`**. Conserver l’URN officielle comme preuve ; ne pas fabriquer un permalien si le contrat ne permet pas de le construire de façon fiable. Un échec d’envoi du message de confirmation Telegram ne doit pas relancer le post LinkedIn. [LI-3]

Le guide UGC historique documente une longueur de 3 000 caractères ; c'est une indication utile, pas un test du comptage exact de `/rest/posts`. Vérifier les contraintes actuelles, Unicode, liens et texte alternatif avant recette. [LI-11]

**Parcours d'appel via treg (14 novembre 2026, catalogue attesté, POST réel NON TESTÉ) :** `treg call linkedin rest/posts --method POST --header "LinkedIn-Version: YYYYMM" --header "X-Restli-Protocol-Version: 2.0.0" --data '@post.json'`. Catalogue : `linkedin.linkedin.user.post.create` → `POST https://api.linkedin.com/rest/posts`, gratuit et non mesuré (OAuth propre du membre via treg). Succès attendu **201, URN dans l'en-tête `x-restli-id`, corps vide** — seule preuve retenue, jamais le scraping treg. Corps JSON fourni par fichier : `author` = `urn:li:person:UkLKzuK9bT` (resource_ref fournie par treg, telle quelle), `commentary` avec échappement backslash des caractères `( ) [ ] { } < > @ | ~`, `visibility` PUBLIC ou CONNECTIONS (annoncée à l'utilisateur avant validation), `distribution` `{"feedDistribution":"MAIN_FEED","targetEntities":[],"thirdPartyDistributionChannels":[]}`, `lifecycleState` PUBLISHED, `isReshareDisabledByAuthor` false. **Contrainte de rotation :** résoudre dynamiquement la connexion `linkedin` health=ok via `treg connections ls` (les reconnexions créent des `linkedin-N`) ; jamais de nom ni de secret en dur. **Bug machine connu :** `NO_PROXY` système contient `[::1],::1` mal parsé par httpx ⇒ préfixer chaque commande treg de `NO_PROXY=` (vide) ; configuration globale inchangée. **Endpoints mesurés à éviter** (crédit d'essai unique de 1,00 $, reste 0,9921 $ au 14 nov) : `treg.linkedin.user.posts`, `treg.linkedin.post.detail`, `treg.google.serp.organic` (~0,008 $ déjà consommés). Recherche web : Tavily, jamais treg. Analytics de posts membres non exposées (réservées Pages).

### 2.5 Lecture de l’historique et archive centrale

La lecture des posts d’un membre avec le finder d’auteur de `/rest/posts` exige `r_member_social`, décrit comme **restreint, pour utilisateurs approuvés seulement**. `w_member_social` n’inclut pas cette permission. OpenID Connect fournit une identité, pas l’historique des posts. [LI-3]

Si accès accordé : vérifier pagination, ordre réel, dates, doublons/reposts et couverture ; ne pas supposer que les premiers résultats sont les publications souhaitées. Surtout, un scope accordé ne lève pas les restrictions de conservation/transfert de la section 2.8 : la lecture automatique pour le style reste désactivée tant que la conformité n’est pas démontrée.

Si accès absent : l’archive centrale est alimentée par (A) les publications du bot confirmées — texte original exact archivé atomiquement avec le reçu — et (B) un import indépendant du fournisseur : originaux datés fournis par l’utilisateur, export autorisé du skill Apify après audit, autre outil ou API conforme. Trois posts récents sont un échantillon de consultation, pas une limite de stockage. **Les publications effectuées hors bot et non importées ne sont pas détectées**, ce qui limite la fiabilité du rappel d’inactivité ; le dire explicitement. Aucune collecte non officielle n’est nécessaire pour démarrer.

### 2.6 Images — gate distinct

Cible d’initialisation : `POST https://api.linkedin.com/rest/images?action=initializeUpload`, avec propriétaire membre. La réponse fournit une URN et une URL de téléversement ; envoyer le fichier exact avec la méthode et les en-têtes du protocole documenté. Respecter l’expiration de l’URL et ne jamais l’enregistrer en clair dans un journal. [LI-7]

**Limite critique documentée :** un token avec uniquement `w_member_social` ne peut pas faire un `GET` versionné sur `/rest/images` pour lire le statut. L’API Images ne prend pas en charge `SYNCHRONOUS_UPLOAD`. Ne pas ajouter un polling `GET` supposé disponible ni utiliser l’exception legacy non versionnée comme contournement.

Conséquences :

- L’upload réussi ne prouve pas à lui seul que l’image est immédiatement disponible pour le post.
- Le parcours complet upload → publication doit être éprouvé avec les permissions réellement accordées et les états/erreurs officiels.
- Si une lecture de statut est accessible, l’adaptateur peut l’utiliser selon le scope attesté ; sinon un parcours officiel sans cette lecture doit être confirmé avant activation.
- Tant que ce parcours n’est pas fiable, **publication avec image bloquée**, texte seul proposé avec nouvelle validation explicite de l’absence d’image et du texte si le crédit change.
- Aucun retry aveugle du `POST` créateur si le résultat est ambigu.

La documentation mentionne JPG, GIF, PNG et moins de 36 152 320 pixels. Le MVP privilégie une image statique JPEG ou PNG ; taille en octets, dimensions, durée de validité et traitement effectif à vérifier lors du test. Pas de supposition sur un plafond en mégaoctets non relevé. [LI-7]

Le fichier doit être approuvé avant tout transfert LinkedIn. Le transfert média intervient après l'autorisation finale portant sur son empreinte ; il ne constitue pas à lui seul une publication, mais reste un envoi de données à un tiers.

**Parcours image via treg (14 novembre 2026, catalogue attesté, upload réel NON TESTÉ) :** `initializeUpload` → URL de téléversement pré-signée → envoi du fichier par **`curl.exe -X PUT --upload-file`** (pas Invoke-WebRequest, dont le comportement PUT est défaillant ici) → référence `content.media{id}` pour 1 image, `content.multiImage{images:[{id,altText}]}` pour 2+. Formats PNG/JPG/GIF, ≤ 8 Mo selon le catalogue treg (à vérifier au test, la documentation LinkedIn susmentionnée ne donne pas le même plafond). Un **422 sur multiImage** ⇒ repli `media` (image unique) — jamais de retry aveugle. Aucun binaire persisté : le fichier transite uniquement par le tampon approuvé.

### 2.7 Quotas, versions et erreurs

- La page générale de rate limiting précise que les plafonds dépendent des endpoints/application/membre et ne sont pas généralement publiés ; ils sont consultables dans Analytics après une requête sur l’endpoint concerné. [LI-10]
- Le guide Share historique affiche 150 requêtes/membre/jour et 100 000/application/jour. **Ne pas transposer ces valeurs à tous les endpoints modernes ou au compte de l’utilisateur.** Conserver le quota effectivement observé, avec date et endpoint. [LI-2, 10]
- Aucun appel créateur ne sera envoyé uniquement pour révéler un quota sans autorisation explicite de publication.
- Versionnement mensuel, versions annoncées supportées au moins un an, avec exceptions possibles. Prévoir revue avant sunset ; une version n’est pas « à vie ». [LI-8]
- 401 : reconnexion ; 403 : accès à vérifier ; 429 : respecter limitation. Pour le POST de publication, classifier selon documentation si rejet certain ou résultat incertain ; ne pas appliquer un retry HTTP générique.
- Timeout, crash ou réponse serveur ambiguë après départ possible : `UNKNOWN_OUTCOME`, verrou du compte et réconciliation. Les garanties et limites d’anti-doublon sont décrites dans l’architecture.

### 2.8 Origine des données, conservation et envoi à un LLM

Les règles des Marketing APIs ne se résument pas aux scopes. La documentation des usages restreints indique notamment des limites d’export/transfert des données membres et de leurs dérivés. Les Data Storage Requirements précisent **48 heures pour l’activité sociale des membres** lue par ces API ; les données de profil d’autres membres ont un cache limité à 24 heures. Les identifiants et données de profil du membre authentifié ont des exceptions de durée, avec consentement et obligations de suppression. La règle applicable dépend du champ, du produit et de l’origine. [LI-12, 13]

La documentation précise que ces durées ne s’appliquent pas aux données fournies indépendamment par les clients et non récupérées via les Marketing APIs. Notre socle utilise donc les textes originaux fournis directement par l’utilisateur et les brouillons créés dans l’application. Faire transiter artificiellement une réponse API par un export utilisateur ne la rend pas indépendante.

**Avant toute lecture automatique de l’historique :** déterminer les conditions applicables à l’application réelle, la conservation champ par champ, les dérivés et l’autorisation éventuelle de transmettre au LLM/Telegram. Un scope `r_member_social` accordé n’autorise pas à lui seul cette réutilisation. En attendant, cet adaptateur reste désactivé pour l’analyse de style ; ne pas envoyer ces données au LLM.

Pour les données API auxquelles la limite s’applique : durée maximale 48 h, aucun renouvellement artificiel par copie dans un brouillon/préférence/profil/index, aucune sauvegarde de 30 jours contenant ces données. Si les purges et restrictions de transfert ne peuvent pas être garanties, ne pas collecter. Conserver les seules preuves locales d’intention, empreintes du contenu fourni et dates opérationnelles ; ne pas conserver indéfiniment des réponses API brutes sous prétexte d’anti-doublon. Vérifier aussi les droits de conservation des identifiants/reçus spécifiques utilisés.

**Portée exacte :** les 48 h concernent l’activité sociale des membres reçue via les Marketing APIs, pas tous les contenus LinkedIn ni toute collecte Apify. Inversement, passer par Apify ou un export utilisateur ne rend pas une donnée API « indépendante » et n’exempte pas des conditions LinkedIn applicables. Chaque origine (original utilisateur, texte local, collecte Apify, autre API) porte sa propre matrice stockage/analyse/dérivation/transfert par destination, Telegram inclus ; droits inconnus ⇒ aucune persistance provisoire. Les conditions tunisiennes de protection des données et de transfert international restent non vérifiées ; un DPA ou des SCC européens ne prouvent pas la conformité en Tunisie.

## 3. Telegram

API officielle, clé de bot gérée localement. Long polling `getUpdates`, envoi `sendMessage`, prévisualisation `sendPhoto` ou document selon besoin et gestion des boutons par `answerCallbackQuery`.

- Autoriser explicitement le propriétaire numérique et le chat privé ; pas de confiance dans username, message transféré ou texte « je suis le propriétaire ».
- L’utilisateur doit commencer la conversation avant les rappels ; un bot bloqué ne peut pas forcer leur livraison.
- `getUpdates` et webhook mutuellement exclusifs ; un seul consommateur, offset avancé après persistance des événements acceptés. Relecture idempotente par `update_id`.
- Maximum 24 h de conservation des updates entrants par Telegram : un portable arrêté plusieurs jours peut manquer des messages. Les brouillons déjà persistés restent locaux.
- Les références `callback_data` sont limitées à 1–64 octets ; utiliser un identifiant opaque, pas le post complet. Contrôler acteur, chat, nonce, révision, état et expiration.
- Texte `sendMessage` jusqu’à 4 096 caractères après parsing des entités ; légende photo limitée à 1 024. Un post long doit être présenté en message séparé du média, pas tronqué dans la légende. Tous les segments de l’aperçu doivent correspondre au même manifeste.
- Un succès API d’envoi Telegram ne prouve pas que l’utilisateur a lu le message. Seule une action explicite valide le contenu.
- Pas de paid broadcasts, pas de webhook public au socle ; logs expurgés car le token figure dans la route Bot API.

La fenêtre de reprise, les limites de débit et la confidentialité sont sourcées dans [le comparatif](FREE_SERVICES_BENCHMARK.md), références MSG-1 à 3. Le chat bot n’est pas chiffré de bout en bout.

## 4. LLM, recherche et extraction

### LLMProvider — Groq + OpenRouter à comparer

Décision du 13 novembre 2026 : **Groq (API officielle) et OpenRouter (API unifiée)** retenus pour comparer plusieurs modèles. Aucun modèle sélectionné définitivement avant tests comparatifs (qualité du français, suivi des instructions, reproduction du style, latence, limites d’usage). Clés fournies par l’utilisateur via `.env` (`GROQ_API_KEY`, `OPENROUTER_API_KEY`) ; jamais dans le code, les logs ou le chat. Contrat `LLMProvider` unique, changement de modèle/fournisseur par paramètre.

Relever pour chaque modèle : identifiant exact, quota organisation/modèle, tailles de contexte/sortie, données envoyées, conditions de conservation, disponibilité géographique. API d’inférence standard sans batch ni fine-tuning au MVP. OpenRouter : variantes `:free` uniquement, plafond supérieur lié à un achat exclu, aucun routage automatique vers une variante payante ; confidentialité dépend aussi du fournisseur amont.

Contrat : texte/structure de réponse avec usage mesuré ; sortie traitée comme non fiable. Aucune autorisation, aucun secret LinkedIn ni transcript complet envoyé. Contexte borné : profil descriptif compact (≤4 000 caractères proposés) + échantillon ciblé de l’archive (≤6 posts/12 000 caractères proposés) + règles confirmées séparées ; jamais toute l’archive ni un post dont le transfert n’est pas autorisé. Un changement de modèle peut changer qualité et limites : recette française avant acceptation, sans performance inventée. **Aucun fournisseur payant sans autorisation, aucun basculement automatique.**

Gemini Free exige une attention particulière : les conditions interdisent l’envoi d’informations sensibles, confidentielles ou personnelles aux Unpaid Services. Les données publiques ne sont pas automatiquement non personnelles. ZDR Groq est documenté mais pas configuré ; aucun réglage de compte n’est changé dans cette mission. Voir GEM-5/GROQ-3 dans le comparatif.

### SearchProvider et Extractor

Tavily `basic`, plafond explicite par appel et par période, PAYG non activé. Ne pas substituer automatiquement Advanced, Research ou Crawl. Les recherches portent sur le sujet, pas sur le profil privé de l’utilisateur.

Les URLs des résultats passent par un téléchargement sécurisé et une extraction locale. Refuser réseaux privés et endpoints métadonnées, vérifier redirections/DNS, borner taille/décompression/temps, appliquer règles des sites. Une erreur d’extraction n’est pas une source vérifiée. Pas de contournement d’accès ni d’envoi automatique de pages complètes à un second extracteur payant.

Brave est remplaçable sous condition prépayé 0 $, carte acceptée par l’utilisateur et auto-reload désactivé. Les quotas chiffrés et preuves de gratuité sont centralisés dans le comparatif.

## 5. Images : ImageProvider

Commencer par Commons : recherche de fichiers, `imageinfo` et `extmetadata`, puis lecture de la page de provenance. Extraire licence/version, auteur réel, attribution, source et restrictions ; échapper le HTML des champs de métadonnées. Les fichiers multilicences nécessitent vérification humaine, pas sélection automatique de la licence la moins restrictive.

Conserver la preuve utile des droits dans le brouillon : lien de page, URL/texte de licence, auteur, crédit prévu, date de consultation et modifications. L’image n’est approuvable qu’après figement du fichier et présentation de son usage envisagé. Éviter personnes identifiables, marques et allégations d’endossement.

Pexels/Unsplash restent des adaptateurs futurs après revue des conditions API et de la republication. Pas d’intégration de moteur d’images qui copierait arbitrairement une image trouvée sur le web. Fournir une image personnelle nécessite également confirmation des droits.

## 6. Import indépendant et skill Apify

### 6.1 Contrat d’import indépendant du fournisseur

Le cœur ne dépend pas d’Apify. Enveloppe structurée proposée (à figer après audit de la sortie réelle) :

| Champ | Contenu | Contrôle |
|---|---|---|
| `source` | Origine réelle : `user_original`, `assistant_published`, `apify_skill`, `other_api`, `other_tool` ; méthode d’obtention | Jamais réétiquetée ; un export API remis par l’utilisateur reste d’origine API |
| `provider` | Fournisseur/Actor/version si connus, référence de lot | Métadonnée opaque, pas de logique métier spécifique |
| `posts[]` | Texte intégral exact, auteur, identifiants **typés complets** (`share`/`ugcPost`/`activity`/URN), URL attestée, `published_at` + précision + fuseau, visibilité/médias si connus | Champs absents = null, jamais inventés ; taille et nombre bornés (proposition 100 éléments/2 Mio par lot) |
| `coverage` | Période couverte, pagination, complétude déclarée | Ne prouve pas l’exhaustivité ; absence ≠ suppression |
| `policy` | Droits vérifiés par champ : stockage, analyse, dérivation, transferts autorisés, échéances | Inconnu ⇒ refus de persistance ; la plus stricte prime |

Pipeline : droits → parsing borné non fiable → comparaison (ID typé prioritaire, repli conservateur texte normalisé versionné + date précise + auteur + métadonnées) → plan immuable (nouveau/connu/version/conflit/ambigu/incomplet/refus) → accord lot/éléments → transaction idempotente avec revalidation. Détails et invariants dans [l’architecture](TECHNICAL_ARCHITECTURE.md) et [les tests](TEST_STRATEGY.md). Un import ne publie rien et ne résout jamais automatiquement `UNKNOWN_OUTCOME`.

### 6.2 Skill Apify — audit réalisé (13 novembre 2026)

Le skill `apify-ultimate-scraper` a été **audité en lecture seule** (fichiers locaux : `SKILL.md`, `references/actor-index.md`, `references/gotchas.md`, guides de workflows). Rapport complet : [APIFY_SKILL_AUDIT.md](APIFY_SKILL_AUDIT.md). Aucun Actor exécuté, aucun compte/jeton, original inchangé.

Constats : skill d’agent pilotant le **CLI Apify** (npm `apify-cli` ≥ 1.5.0, auth `APIFY_TOKEN`/OAuth) ; Actors LinkedIn tous **community/PPE** (`harvestapi/linkedin-profile-posts` : `profiles`+`maxPosts` → `postText`/`publishedAt`/`url`/`likes`/`comments` ; `harvestapi/linkedin-company-posts` ; `apimaestro/linkedin-post-detail`…) ; coûts indicatifs ~0,001–0,02 $/résultat à recontrôler ; LinkedIn bloque le scraping à grande échelle (lots < 100 profils, runs ≥ 5 min d’intervalle, résultats vides occasionnels, posts privés → vide sans erreur) ; sessions/cookies gérés en interne. Les guides ne garantissent pas d’URN typé → repli de comparaison conservateur. **Scraper LinkedIn, même ses propres posts, peut violer les conditions LinkedIn** ; un compte Apify autorisé n’est pas une autorisation LinkedIn.

**Modes d’intégration, par ordre de préférence :** (1) l’utilisateur fournit un export autorisé que l’importeur générique ingère — aucun Actor exécuté par l’application (mode préféré, déjà implémenté) ; (2) adaptateur dédié traduisant la sortie réelle du skill vers l’enveloppe ci-dessus, après audit de sortie réelle, droits vérifiés et accord, skill original inchangé, coûts bornés/mesurés (Phase 3B optionnelle) ; (3) réutilisation des seules règles d’analyse/parsing conformes, sans collecte. Si la collecte n’est pas conforme, elle n’entre pas dans le socle ; l’import manuel reste disponible. Aucune publication par Apify n’est admise. Le skill reste un outil d’agent, pas une dépendance runtime du cœur.

## 7. Checklist humaine avant activation future

- [ ] Socle validé ; modalités restantes (seuils, durées, RAM images) et phase suivante explicitement approuvées.
- [ ] Propriétaire et profil personnel cible confirmés ; utilisation Tunisie/`Africa/Tunis` actée ; conditions tunisiennes/transferts vérifiées pour le traitement réel.
- [ ] Hôte décidé (PC utilisateur dev/tests) ; coûts indirects assumés ; secrets `.env` gérés localement.
- [x] **Accès publication provisionné via treg (14 nov)** : connexion `linkedin` health=ok créée par l'utilisateur (consentement navigateur), identité et `w_member_social` vérifiés par `v2/userinfo` → 200 ; sans application Developer propre.
- [ ] Qualification réelle de `/rest/posts` (POST texte puis image) après autorisation distincte sur le contenu exact ; gestion de la rotation treg (résolution dynamique de connexion) vérifiée dans l'adaptateur.
- [ ] Identité auteur confirmée dans le préflight de chaque publication ; parcours de reconnexion treg (après rotation) prévu.
- [ ] Droits d'import définis par origine/usage/destination ; skill Apify audité (fait) ; adaptateur éventuel seulement après droits/accord ; complétude de l'historique et limites des rappels expliquées.
- [ ] Fournisseurs LLM (Groq/OpenRouter) et recherche, clés `.env` fournies, comparaison réalisée, modèle exact choisi après tests, régions/confidentialité/quotas et absence de facturation automatique vérifiés.
- [ ] Publication texte testée seulement après autorisation séparée du contenu réel ; preuve officielle (201 + URN `x-restli-id`) conservée ; archive atomique vérifiée.
- [ ] Images non activées avant test indépendant du parcours officiel (initializeUpload → PUT pré-signé → référence média), des validations de droits et de l'absence d'archive binaire.
- [ ] Un échec d'accès ne débloque aucun mécanisme non officiel ; aucun appel treg mesuré sans autorisation.

## 8. Sources officielles LinkedIn

Consultées le 13 novembre 2026. LI-1 à 8, LI-10, LI-12 et LI-13 : texte officiel lu directement ; LI-9, LI-11 et LI-LEGAL : extraits officiels indexés, conditions intégrales à revoir lors de l’activation.

- LI-1 [Getting Access — permissions ouvertes](https://learn.microsoft.com/en-us/linkedin/shared/authentication/getting-access).
- LI-2 [Share on LinkedIn — guide self-service](https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/share-on-linkedin).
- LI-3 [Posts API — version documentaire 2026-10](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/posts-api?view=li-lms-2026-10).
- LI-4 [Sign in with LinkedIn using OpenID Connect](https://learn.microsoft.com/en-us/linkedin/consumer/integrations/self-serve/sign-in-with-linkedin-v2).
- LI-5 [Authorization Code Flow](https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow).
- LI-6 [Programmatic Refresh Tokens](https://learn.microsoft.com/en-us/linkedin/shared/authentication/programmatic-refresh-tokens).
- LI-7 [Images API — permissions et traitement](https://learn.microsoft.com/en-us/linkedin/marketing/community-management/shares/images-api?view=li-lms-2026-10).
- LI-8 [Versionnement LinkedIn Marketing](https://learn.microsoft.com/en-us/linkedin/marketing/versioning?view=li-lms-2026-10).
- LI-9 [Créer une application associée à une Page](https://www.linkedin.com/help/linkedin/answer/a1667239).
- LI-10 [Rate limiting — quotas effectifs](https://learn.microsoft.com/en-us/linkedin/shared/api-guide/concepts/rate-limits).
- LI-11 [UGC historique — limite de texte](https://learn.microsoft.com/en-us/linkedin/compliance/integrations/shares/ugc-post-api).
- LI-12 [Usages restreints — transfert et données membres](https://learn.microsoft.com/en-us/linkedin/marketing/restricted-use-cases?view=li-lms-2026-10).
- LI-13 [Data Storage Requirements — durées par origine/champ](https://learn.microsoft.com/en-us/linkedin/marketing/data-storage-requirements?view=li-lms-2026-10).
- LI-LEGAL [LinkedIn — conditions d’utilisation](https://www.linkedin.com/legal/user-agreement) et [logiciels interdits](https://www.linkedin.com/help/linkedin/answer/a1341387).

Pour Telegram, LLM, recherche, images, n8n, Apify et Oracle : sources officielles et niveaux de preuve dans [FREE_SERVICES_BENCHMARK.md](FREE_SERVICES_BENCHMARK.md).
