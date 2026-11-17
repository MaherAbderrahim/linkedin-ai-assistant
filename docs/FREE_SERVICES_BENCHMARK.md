# Comparatif documentaire des services gratuits

**Vérifié documentairement le 13 novembre 2026 (Mission 0), complété en Missions 0.5 et 0.6 (archive centrale, import, profil, décisions utilisateur, audit du skill Apify).** Il ne s’agit pas d’un benchmark de performance ni d’un test des comptes de l’utilisateur. Aucun compte créé, aucune clé utilisée, aucun appel API authentifié, aucune mesure de qualité/latence réelle. Les offres peuvent changer ; les accès et quotas doivent être recontrôlés avant activation.

**Limite de revalidation Mission 0.5 :** les chiffres tarifaires ci-dessous sont les preuves datées de Mission 0, pas une revérification intégrale. Les pages conditions Apify, abonnements et stockage n’ont pas pu être rouvertes pendant la mise à jour ; leurs valeurs restent des preuves Mission 0 à recontrôler avant tout usage. Les conditions tunisiennes de protection des données/transferts ne sont pas vérifiées par ce document.

## 1. Méthode et définition de « gratuit »

- **Gratuit récurrent** : quota renouvelé, ou logiciel utilisable sans redevance dans le cadre autorisé. Ne garantit ni pérennité de l’offre ni disponibilité.
- **Essai** : durée ou crédits initiaux limités ; non retenu pour le fonctionnement normal.
- **Franchise payante** : partie gratuite d’un produit qui exige aussi de payer ; non assimilée à une solution à 0 €.
- Les dollars cités sont des unités tarifaires officielles, pas des dépenses autorisées.
- **D** dans les sources : texte officiel directement consulté, y compris documentation brute. **I** : extrait officiel indexé seulement ; lecture intégrale à compléter avant activation.
- Les pages dynamiques peuvent omettre des tableaux ou renvoyer une langue différente. En cas de doute, ne pas figer de quota ni inventer une absence de carte.
- Aucun des services ci-dessous n’est déclaré accessible sur le compte de l’utilisateur. Aucune restriction géographique inconnue n’est assimilée à une absence de restriction.

## 2. Synthèse des choix

| Besoin | Proposition | Alternative gratuite | Condition/limite principale | Remplacement |
|---|---|---|---|---|
| Orchestration | Python, processus unique | n8n Community Edition | Un peu de code métier sera nécessaire ; pas d’hébergement inclus | Les adaptateurs et états restent indépendants |
| Persistance | SQLite central : archive textuelle autorisée, profil compact, brouillons, registre d’envoi | PostgreSQL si besoin réel ; pas de base vectorielle | Un seul hôte/écrivain métier ; pas de stockage réseau partagé ; aucun binaire image | Frontière de stockage interne |
| Historique/import | Import générique : originaux utilisateur, export du skill audité, autre source conforme | Lecture officielle si scope et conditions obtenus | Droits par origine/usage/destination avant persistance ; skill audité le 13 nov (voir APIFY_SKILL_AUDIT.md) | Contrat ImportProvider indépendant d’Apify |
| Conversation | Telegram Bot API | WhatsApp Cloud API pour certains usages réactifs | Bot démarré par utilisateur ; chat non chiffré de bout en bout | Adaptateur conversation |
| Rédaction | Groq + OpenRouter à comparer (décision utilisateur), modèle non figé | Gemini Free sous contraintes, Workers AI | Comparaison avant sélection ; aucun payant automatique ; traitement de données à approuver | Contrat LLMProvider |
| Recherche web | Tavily Free `basic` | Brave Search avec prépayé 0 $, liens utilisateur/RSS sélectionnés | 1 000 crédits mensuels ; pas de PAYG | Contrat SearchProvider |
| Extraction | HTTP contrôlé + Trafilatura | Extraits autorisés fournis par l’utilisateur | Pages HTML publiques ; JavaScript, paywalls et protections non contournés | Contrat Extractor |
| Images | Wikimedia Commons, sélection prudente, octets en RAM (proposé) | Pexels après revue des conditions ; image fournie par utilisateur | Licence par fichier ; aucune archive binaire de fichiers images | Contrat ImageProvider |
| Publication | API officielle LinkedIn | Aucune alternative automatisée retenue | Accès application, OAuth, version et endpoint à éprouver | Adaptateur unique, toujours officiel |
| Hébergement | PC utilisateur (dev/tests, décidé) | Oracle Always Free à étudier plus tard ; PC ami en secours | Coûts d’électricité et disponibilité à accepter ; aucune installation distante maintenant | Même application, base et sauvegarde migrables |
| Génération d’images | Désactivée | Service futur réellement gratuit ou image personnelle | Aucune offre gratuite récurrente compatible démontrée | Extension facultative hors chemin critique |

## 3. LLM hébergés

### Groq Free — co-candidat avec OpenRouter, pas de sélection définitive du modèle

**Pourquoi :** API hébergée, offre Free distincte de Developer, contrôles explicites de conservation, absence de modèle local requis. La qualité rédactionnelle française et les capacités de sortie structurée doivent être testées sur le modèle réellement accessible.

- Les quotas dépendent du modèle : RPM, RPD, TPM et TPD selon l’offre. Le tableau effectif et les limites de l’organisation devront être relevés dans la console ; aucun chiffre par modèle n’est figé ici.
- Dépassement : HTTP 429 ; prendre en compte les unités et en-têtes réellement retournés. Les limites de tokens peuvent être atteintes avant celles de requêtes.
- Passage au Developer Plan : moyen de paiement valide demandé. L’exigence de carte à la création d’un compte Free n’a pas été confirmée dans les sources consultées : à vérifier, pas à supposer.
- La page de données indique qu’ordinairement les entrées/sorties d’inférence ne sont pas conservées, **avec exceptions** pour état applicatif et fiabilité/abus. Les journaux de fiabilité/abus peuvent être retenus jusqu’à 30 jours, davantage si obligation légale.
- Elle précise que **tous les clients peuvent activer Zero Data Retention** dans Data Controls. Ce réglage n’a pas été activé ni testé ici ; les fonctionnalités à état peuvent alors être désactivées. Les métadonnées d’usage restent collectées.
- Les données client conservées sont annoncées dans des buckets GCP aux États-Unis. Le document de conservation ne suffit pas, seul, à inventer une garantie contractuelle générale de non-entraînement : examiner les conditions en vigueur avant d’envoyer des exemples personnels.
- Pays, compte, modèle et acceptation des conditions : gates avant usage ; aucun contournement géographique.

**Verdict :** retenu avec OpenRouter pour comparaison (décision du 13 novembre 2026), ZDR recommandé si accessible comme documenté, données minimisées et consentement requis. Aucun modèle figé avant tests comparatifs (français, instructions, style, latence, limites). Contexte borné proposé : profil ≤4 000 caractères + ≤6 posts/12 000 caractères d’extraits autorisés + règles confirmées séparées ; jamais toute l’archive. Si le compte ou les conditions ne conviennent pas, ne pas activer la génération tant qu’une alternative conforme n’est pas validée. [GROQ-1 à 3]

### Gemini Developer API Free Tier — alternative restreinte

- Free Tier documenté, mais pas sur tous les modèles ni toutes les fonctions. Quotas RPM/TPM/RPD variables, à relever dans AI Studio pour le modèle exact. Aucun quota ancien repris par défaut.
- Activation du payant distincte ; ne pas confondre quota gratuit avec crédits promotionnels Google Cloud. Absence de carte à l’ouverture non reconfirmée ici.
- La Tunisie figure dans la liste officielle indexée ; l’utilisation depuis la Tunisie est confirmée par l’utilisateur, mais l’éligibilité de son compte reste à vérifier. [GEM-4, niveau I]
- Les conditions des **Unpaid Services** autorisent l’utilisation des entrées/sorties pour améliorer les produits, avec lecture possible par des humains. Elles disent : « Do not submit sensitive, confidential, or personal information to the Unpaid Services. »
- Un post public peut contenir des données personnelles. **Un simple consentement utilisateur ne neutralise pas cette interdiction contractuelle.** Ne pas envoyer automatiquement les posts bruts de l’archive, le profil de style personnel, un CV, des noms de tiers ou la conversation privée à ce service. Une anonymisation doit être effectivement suffisante, sinon exclure Gemini pour cette tâche.
- EEE/Suisse/Royaume-Uni : les conditions de données des Paid Services s’appliquent aussi à certains usages gratuits, mais une autre clause exige les Paid Services pour rendre des clients API disponibles à des utilisateurs dans ces territoires. L’application exacte à ce bot strictement personnel est à clarifier ; pas de promesse de déploiement gratuit dans ces pays.

**Verdict :** alternative pour contenu réellement non personnel/non confidentiel et zone autorisée, pas choix automatique pour une mémoire de style personnelle. [GEM-1 à 5]

### Autres candidats

| Service | Allocation documentée | Limites et confidentialité | Décision |
|---|---|---|---|
| Cloudflare Workers AI | 10 000 **Neurons/jour** gratuits | Unités de calcul, pas tokens/requêtes ; coût par modèle, exigences de compte/carte et conditions de données à confirmer ; dépassement nécessite Workers Paid | Candidat secondaire, niveau de preuve tarifaire I |
| OpenRouter, variantes `:free` | 20 requêtes/minute et 50/jour sans achat préalable | Le plafond supérieur lié à un achat est exclu ; modèles/fournisseurs changent, confidentialité dépend aussi de l’amont, requêtes en échec peuvent compter selon les règles | **Co-candidat retenu pour comparaison avec Groq** (décision du 13 nov) ; jamais routage vers une variante payante |

Sources [LLM-ALT-1 à 3]. Aucun classement de qualité du français ou de vitesse n’est inventé : la comparaison Groq/OpenRouter se fera sur des tâches réelles autorisées, avec les clés de l’utilisateur, avant toute sélection définitive. Aucun fournisseur n’est activé automatiquement en cas de panne ni basculé vers du payant : changer de destinataire des données nécessite un consentement compatible.

## 4. Recherche et extraction

### Tavily — retenu provisoirement

- **1 000 crédits gratuits par mois**, **sans carte bancaire** : il s’agit bien d’une allocation récurrente.
- Recherche `basic` : 1 crédit/appel ; `advanced` : 2. Le maximum arithmétique est donc 1 000 basic ou 500 advanced si l’enveloppe n’est utilisée pour rien d’autre.
- Extract : 1 crédit pour 5 extractions réussies en basic, 2 en advanced ; les produits Map/Crawl/Research ont d’autres coûts. Ils ne sont pas inclus automatiquement dans le MVP.
- Le PAYG permet une facturation après dépassement ; **ne pas l’activer**. Pas de passage automatique à un plan payant.
- Utiliser une profondeur explicite `basic`, pas une option automatique pouvant augmenter le coût sans maîtrise. Les métadonnées fournies par le moteur doivent être vérifiées à la source.
- Le moteur reçoit les requêtes et éventuellement des contenus si ses fonctions d’extraction sont utilisées. Ne pas transmettre les posts privés ni les règles personnelles ; garanties de conservation, région et compte à compléter avant activation.

**Pourquoi plutôt que Brave :** quota récurrent clairement chiffré et absence de carte explicitement documentée. Remplaçable par SearchProvider. [SEARCH-1, 2]

### Brave Search API — alternative conditionnelle

- **5 $ de crédits renouvelés chaque mois** ; tarif Search annoncé **5 $/1 000 requêtes**, soit jusqu’à 1 000 requêtes si toute l’allocation y est consacrée.
- Carte obligatoire. La FAQ décrit un **prépayé à 0 $** bénéficiant de l’allocation gratuite puis une suspension au solde épuisé.
- Le postpayé facture les dépassements ; **auto-reload** peut acheter des crédits. Son réglage par défaut n’est pas présumé : vérifier prépayé et recharge désactivée avant usage.
- Les crédits mensuels sont compatibles en principe avec 0 €, mais la carte et les réglages rendent l’erreur de facturation plus probable. Données de requêtes et conditions d’usage à examiner comme pour Tavily.

Sources [SEARCH-3, 4].

### Gemini Grounding with Google Search — non retenu au socle

La tarification dépend du modèle et du palier. Une ligne officielle indexée indique 5 000 recherches gratuites/mois pour certains modèles Gemini 3 et suivants **sur une offre payante**, avec Free Tier non disponible sur cette ligne. Cela ne prouve ni génération gratuite ni accès gratuit au grounding pour ce projet. Une recherche et un appel de génération n’ont pas nécessairement la même unité de facturation. Ne retenir cette option qu’après vérification du couple exact modèle/palier. [GEM-1, 6]

### HTTP et Trafilatura

Bibliothèque locale sans crédit propriétaire, licence Apache 2.0 pour les versions actuelles ; les versions antérieures à 1.8.0 avaient une autre licence. Le choix de version future sera explicite.

Extraction de texte/metadonnées depuis HTML public, sans rendu JavaScript obligatoire. Aucun contournement de paywall, CAPTCHA, authentification ou blocage. Examiner conditions du site et `robots.txt`, limiter fréquence, temps et taille ; respecter la sécurité SSRF définie dans l’architecture. `robots.txt` n’est ni une permission juridique générale ni une preuve de qualité. La licence de Trafilatura ne confère aucun droit sur les textes extraits. [EXTRACT-1 à 3]

RSS, sites institutionnels et liens donnés par l’utilisateur sont une solution gratuite partielle en cas de panne du moteur, pas un équivalent garanti d’un moteur web généraliste ou d’une mesure de tendances.

## 5. Images et Apify

### Banques d’images

| Option | Gratuité/quotas documentés | Contraintes | Verdict |
|---|---|---|---|
| Wikimedia Commons / MediaWiki | API publique ; documentation 2026 : 10 req/min client non identifié, 200 req/min bot non authentifié avec User-Agent conforme ; recommandation de 3 requêtes simultanées maximum | Quotas évolutifs ; licence par fichier ; métadonnées multilicences parfois non fiables ; auteur, attribution, restrictions et droits des personnes à vérifier | Premier choix, fonctionnement prévu très en dessous des plafonds |
| Pexels | API gratuite ; 200 req/h et 20 000/mois par défaut selon extraits officiels | Conditions/API distinctes de la licence ; crédit/lien Pexels et photographe selon conditions ; clauses de redistribution « Standalone » et d’endossement à lire intégralement | Alternative après revue ; accès intégral aux conditions non obtenu pendant cette mission |
| Unsplash | Démonstration 50 req/h ; production après approbation | Attribution API obligatoire, hotlinking, appel de download_location à la sélection ; ne pas supposer que la republication automatisée de l’original sur LinkedIn respecte ce parcours | Non retenu avant clarification du parcours de republication |

Sources [IMG-1 à 10]. Pour Commons, privilégier domaine public/CC0 établi ou CC BY avec crédit conforme, sans personnes reconnaissables ni marques dominantes. CC BY-SA et autres situations nécessitent examen spécifique ; ne pas supposer que la licence s’étend automatiquement à tout le texte accompagnant l’image. Aucun moteur ne garantit juridiquement les droits.

Génération d’images : **désactivée**. Aucune offre gratuite récurrente compatible n’a été établie dans cette étude ; ce constat n’affirme pas qu’il n’en existe aucune. Des crédits d’accueil ne répondraient pas au besoin.

### Apify — hors dépendance obligatoire

L’offre Free documentée prévoit **5 USD renouvelés chaque mois**, sans carte, puis suspension jusqu’au cycle suivant lorsque l’enveloppe est épuisée. Cela ne rend pas tous les Actors gratuits. Tarification par événement et/ou ressources ; calcul, stockage, transferts et proxys peuvent consommer le crédit. Pas d’estimation fiable « trois posts coûtent X » sans Actor et mesure.

La documentation des limites mentionne 5 exécutions simultanées et 16 384 Mo de mémoire cumulée en Free ; ce sont des plafonds, pas des besoins de l’assistant. Les données chez Apify peuvent subsister au-delà de la rétention locale : la documentation mentionne les dix dernières exécutions conservées quatre mois et un comportement différent pour les stockages nommés. Vérifier le type exact de stockage employé par le skill.

**Le skill `apify-ultimate-scraper` a été audité en lecture seule le 13 novembre 2026** (fichiers locaux ; voir [APIFY_SKILL_AUDIT.md](APIFY_SKILL_AUDIT.md)) : skill d’agent pilotant le CLI Apify, Actors LinkedIn tous community/PPE, coûts indicatifs ~0,001–0,02 $/résultat à recontrôler, scraping bloqué à grande échelle. Aucune exécution, original inchangé. Une collecte non officielle peut violer les conditions de LinkedIn même pour ses propres posts ; elle n’entre pas dans le socle retenu. L’archive centrale est alimentée par un **import indépendant d’Apify** (originaux utilisateur, export autorisé du skill, autre source conforme) ; aucun mécanisme de publication Apify n’est retenu. [APIFY-1 à 5 ; LI-LEGAL dans API_INTEGRATIONS.md]

**Mission 0.5 :** les pages conditions/abonnements/stockage Apify n’ont pas pu être rouvertes ; les valeurs ci-dessus restent des preuves Mission 0 à recontrôler. Un extrait indexé du DPA Apify (8 juillet 2026) décrit client responsable du traitement/Apify sous-traitant avec clauses de suppression et sous-traitance ultérieure : cela ne constitue ni une autorisation de collecter LinkedIn ni une preuve de conformité tunisienne. Le coût d’un import dépend de l’Actor réel et de ses stockages ; aucune estimation chiffrée par lot n’est inventée.

## 6. Messagerie et orchestration

### Telegram Bot API — retenu

API adaptée à un usage individuel sans abonnement. L’utilisateur doit démarrer la conversation ; le bot peut ensuite envoyer des rappels dans le chat connu tant qu’il n’est pas bloqué.

- Long polling et webhook mutuellement exclusifs ; `getUpdates` évite un serveur entrant public.
- Événements non récupérés conservés **au maximum 24 heures**.
- Recommandations FAQ : éviter plus d’un message/seconde dans un chat, 20/minute dans un groupe, environ 30/seconde en diffusion gratuite. Respecter les 429 et `Retry-After` ; pas de diffusion payante.
- Bot privé ≠ Secret Chat : pas de chiffrement de bout en bout pour ce dialogue. Le privacy mode des groupes ne masque pas les messages privés au bot.
- Télégramme, texte, images et identifiants transitent chez Telegram ; confidentialité et disponibilité réseau selon le pays à accepter.

Sources [MSG-1 à 3].

### WhatsApp Business Cloud API — écarté pour ce besoin

La page tarifaire officielle consultée annonce une modification au **1er octobre 2026** : **1 000 messages de service distribués gratuits/mois par numéro professionnel**, sans report, puis facturation à partir du 1 001e. Sans moyen de paiement, le quota peut être utilisé puis les livraisons concernées s’arrêtent. Les messages entrants ne sont pas facturés.

La fenêtre de service dure 24 h après interaction de l’utilisateur. Hors fenêtre, un modèle approuvé est nécessaire ; les messages de rappel après cinq jours ne sont donc pas une réponse gratuite ordinaire. Ne pas reprendre l’ancienne affirmation « réponses illimitées et utility gratuits dans 24 h » : les règles actuelles diffèrent. Les fenêtres liées aux publicités ne constituent pas une solution à budget nul.

Compte Meta/développeur/professionnel, numéro et conditions de modèles compliquent aussi le démarrage. Petit usage réactif éventuellement gratuit, **rappels proactifs gratuits non garantis**. Aucun automatisme WhatsApp Web non officiel proposé. [MSG-4, 5]

### n8n Community Edition — étudié, non obligatoire

Gratuit en auto-hébergement pour l’usage personnel prévu, mais licence **Sustainable Use License**, source-available/fair-code et non OSI open source. Le service n8n Cloud et ses essais ne constituent pas un hébergement gratuit permanent.

Limites CE documentées notamment sur collaboration, SSO, environnements, secrets externes, Git/versionnement et multi-main. L’enregistrement gratuit débloque quelques fonctions ; il ne faut pas le confondre avec un abonnement nécessaire au moteur de base.

Le Telegram Trigger natif repose sur un webhook **HTTPS public**. Le long polling Telegram proposé dans notre architecture Python n’est pas automatiquement disponible via ce déclencheur. n8n apporte une interface utile pour composer des workflows, mais les validations versionnées, la reprise d’envois incertains et les corrections conversationnelles exigent toujours une logique métier rigoureuse. [N8N-1 à 3]

## 7. Hébergement

**Décision du 13 novembre 2026 :** développement et premiers tests sur le **PC de l’utilisateur** ; Oracle Always Free à étudier plus tard ; PC d’un ami en secours. Aucune installation ni aucun déploiement sur un serveur distant maintenant ; le développement n’est pas bloqué par le choix définitif de l’hébergement. Les deux options ci-dessous restent des preuves documentaires, pas des cibles activées.

### Oracle Cloud Always Free

**À ne pas confondre avec l’essai 300 USD / 30 jours.** L’Always Free est annoncé sans expiration, sous conditions du service, pas garanti sans interruption.

Documentation technique consultée au 13 novembre 2026 :

| Ressource | Allocation publiée |
|---|---|
| AMD VM.Standard.E2.1.Micro | Jusqu’à 2 VM, chacune 1/8 OCPU et 1 GB RAM |
| Arm VM.Standard.A1.Flex | 1 500 OCPU-heures et 9 000 GB-heures/mois ; équivalent annoncé 2 OCPU et 12 GB RAM cumulés |
| Volumes bloc/démarrage | 200 GB cumulés |
| Sauvegardes de volumes | 5 au total |

**Attention : ne pas reprendre les anciennes valeurs 4 OCPU / 24 GB de tutoriels sans revérification.** La console du compte et la documentation à la date du déploiement doivent être cohérentes. Région d’origine, formes/OS éligibles, stockage et coûts réseau restent à vérifier ; aucun plafond réseau non vérifié n’est chiffré ici.

- Carte/téléphone généralement requis ; préautorisation bancaire temporaire possible. FAQ : cartes virtuelles/prépayées notamment non acceptées. Aucun passage au payant autorisé par cette mission.
- Capacité non garantie : erreurs « out of host capacity » documentées ; l’utilisateur peut ne pas obtenir de VM.
- Récupération des VM inactives possible si, sur sept jours, CPU au 95e percentile <20 %, réseau <20 %, et mémoire <20 % pour A1. Un bot léger peut être concerné ; **ne pas générer de charge artificielle pour contourner cette règle**.
- Pas de SLA pour l’usage exclusivement Always Free ; compte abandonné et VM inactive sont deux notions distinctes.
- Confidentialité : cloud tiers et traitements internationaux possibles ; minimisation, contrôle des accès et sauvegarde indépendante nécessaires.

**Verdict :** à étudier plus tard, pas activé maintenant ; le PC de l’utilisateur sert au développement et aux premiers tests. Alternative conditionnelle, pas préalable bloquant si une machine de confiance existe. [HOST-1 à 4]

### Balayage des clouds gratuits sans carte (17 novembre 2026)

Recherche ciblée puis élimination critère par critère (grille E1–E7 du projet).
Verdict global : **aucun cloud gratuit sans carte ne satisfait les quatre
besoins du bot en 2026** (processus 24/7, disque SQLite persistant,
sous-processus, secrets protégés).

| Candidat | Sans carte | Verdict | Preuve |
|---|---|---|---|
| **Northflank** Sandbox | Non | **Éliminé (E2) par essai réel de l'utilisateur le 17 nov 2026** : une carte/moyen de paiement est exigé pour créer la moindre ressource, quel que soit le plan. Docs officielles : *« all users must add a payment method to start creating resources on Northflank, regardless of plan selection »* — la page pricing (« No card needed ») décrivait le plan, pas l'inscription | Essai utilisateur + [docs billing Northflank](https://northflank.com/docs/v1/application/billing/pricing-on-northflank) |
| **Modal** Starter (30 $/mois de crédits) | Non | Éliminé (E2 + E3) : moyen de paiement obligatoire « to use Modal at all » ; consommation au-delà des crédits **débitée automatiquement, sans plafond dur** | [modal.com/docs/guide/billing](https://modal.com/docs/guide/billing) ; recoupé par freetier.wiki (02 nov 2026) |
| **Leapcell** Hobby | Oui | Incompatible (E4/E5) : serverless **sans système de fichiers persistant** au plan gratuit (SQLite perdu au scale-down) ; le long polling Telegram ne correspond pas à son modèle requête/réponse ; les « Persistent Servers » 24/7 sont payants (Plus). Une adaptation exigerait de migrer la couche données vers PostgreSQL — contraire à l'architecture validée (SQLite central) | Évaluation FastOpp (sept 2025) ; [leapcell.io/pricing](https://leapcell.io/pricing) |
| Render, SnapDeploy, Back4App | Oui | Éliminés (E4/E5) : sommeil après 15 min / 60 min, disque éphémère ; le Postgres gratuit de Render expire à 30 jours | Comparatif daté 26 sept 2026 (snapdeploy.dev), recoupé avec render.com/docs/free |
| Railway Free (1 $/mois) | Oui | Éliminé (E1 en pratique) : pas de sommeil, mais un service 24/7 (~0,5 Go RAM permanent) dépasse largement le crédit mensuel de 1 $ | Comparatif daté 26 sept 2026 |
| Koyeb | Non | Éliminé (E2) : carte exigée depuis février 2026 (préautorisation 29 $) | koyeb.com/docs/faqs/pricing |
| Oracle Always Free | Non | Éliminé pour cet utilisateur (pas de carte) — voir section ci-dessus | [HOST-1 à 4] |
| Hugging Face Spaces | Oui (avant juillet 2026) | Éliminé : Docker/Gradio Spaces **payants depuis juillet 2026** ; disque éphémère | Comparatif daté 26 sept 2026 |

**Conséquence :** la famille d'hébergement qui coche toutes les cases reste le
**matériel dorm de l'utilisateur** (PC, vieux smartphone via Termux, Raspberry
Pi, NAS) et le **PC d'un ami en secours** — conformes à la décision du
13 novembre 2026. Les offres ci-dessus sont re-testables si les conditions
changent (carte obtenue, nouvelle offre) ; chaque re-test repart de cette
grille et exige une autorisation distincte.


### PC portable d’un ami

Pas d’abonnement serveur si matériel/connexion existent et sont mis à disposition avec accord. Mais électricité, usure, Internet et temps d’administration ne sont pas nuls ; déterminer qui les assume.

Veille, fermeture du capot, déplacement, redémarrages et coupures interrompent le service. Isolation système/stockage nécessaire, sans prétendre protéger les secrets contre l’administrateur hôte. Prévoir droit d’arrêt, restitution et suppression des données. Aucune exposition publique nécessaire pour Telegram en long polling ; callback LinkedIn à vérifier séparément.

**Verdict :** secours si le PC de l’utilisateur ne convient plus ; le choix de départ est le PC de l’utilisateur. Ne devient un départ que si confiance, coûts assumés et interruptions sont acceptés. Sinon décision d’hébergement non résolue, pas de promesse 0 € tout compris.

## 8. Dimensionnement indicatif, pas une mesure

Hypothèse de travail à valider : 12 posts/mois, 3 requêtes web initiales/post et 2 tours supplémentaires de 3 requêtes. Cela donne **108 recherches basic = 108 crédits Tavily** ; ajouter par exemple 12 séances de suggestions à 3 requêtes donnerait 144 crédits. Cette arithmétique n’inclut ni Extract, ni Research, ni d’autres usages du compte.

Proposer un plafond local de 600 crédits Tavily/mois pour garder de la marge, **sans remplacer le suivi réel du compte**. Un appel `advanced` compte double. Pour LLM, ne pas convertir un nombre de posts en tokens sans mesurer prompts, exemples, sorties et corrections ; le contexte borné (profil + échantillon ciblé, pas toute l’archive) limite la consommation par génération. Un test futur devra prouver que le modèle tient dans ses limites minute/jour.

L’archive SQLite, le profil descriptif, la déduplication et le retrieval local n’ont pas de coût d’API : seulement disque, CPU et sauvegarde de l’hôte. Un import via Apify consommerait du crédit Apify selon l’Actor réel ; l’import manuel d’originaux autorisés n’en consomme pas.

Ce budget ne garantit pas le service : même sous le quota mensuel, limites par minute, indisponibilité, restrictions géographiques et suspension pour non-respect des conditions peuvent bloquer. Réduire la cadence, attendre le reset ou utiliser une alternative déjà validée ; jamais multiplier les comptes pour contourner les quotas.

## 9. Sources officielles et niveau de vérification

Les sources ci-dessous ont été consultées le 13 novembre 2026 ; elles ne prouvent aucun accès de compte.

### LLM

- GEM-1 [Gemini — tarifs](https://aistudio.google.com/docs/pricing) — I.
- GEM-2 [Gemini — quotas](https://aistudio.google.com/docs/rate-limits) — I.
- GEM-3 [Gemini — facturation](https://aistudio.google.com/docs/billing) — I.
- GEM-4 [Gemini — régions](https://aistudio.google.com/docs/available-regions) — I.
- GEM-5 [Gemini — conditions](https://aistudio.google.com/docs/terms) — D, texte recoupé directement.
- GEM-6 [Gemini — grounding](https://aistudio.google.com/docs/google-search) — I.
- GROQ-1 [Groq — limites](https://console.groq.com/docs/rate-limits) — D pour mécanismes/en-têtes ; tableau de quotas effectifs à relever.
- GROQ-2 [Groq — facturation](https://console.groq.com/docs/billing-faqs) — I.
- GROQ-3 [Groq — données et ZDR](https://console.groq.com/docs/your-data) — D, texte recoupé directement.
- LLM-ALT-1 [Cloudflare Workers AI — prix](https://developers.cloudflare.com/workers-ai/platform/pricing/) — I.
- LLM-ALT-2 [OpenRouter — modèles gratuits](https://openrouter.ai/collections/free-models) — I.
- LLM-ALT-3 [OpenRouter — données des fournisseurs](https://openrouter.ai/docs/guides/privacy/provider-logging) — I.

### Recherche et extraction

- SEARCH-1 [Tavily — crédits](https://docs.tavily.com/documentation/api-credits) — D, texte recoupé directement.
- SEARCH-2 [Tavily — organisations et plafonds](https://docs.tavily.com/documentation/platform/managing-organizations) — D.
- SEARCH-3 [Brave — tarifs](https://brave.com/search/api/) — I.
- SEARCH-4 [Brave — facturation et prépayé](https://api-dashboard.search.brave.com/documentation/resources/help-feedback) — D.
- EXTRACT-1 [Trafilatura — documentation/licence](https://trafilatura.readthedocs.io/en/latest/_sources/index.rst.txt) — D.
- EXTRACT-2 [Trafilatura — téléchargement](https://trafilatura.readthedocs.io/en/latest/_sources/downloads.rst.txt) — D.
- EXTRACT-3 [Trafilatura — limites](https://trafilatura.readthedocs.io/en/latest/_sources/troubleshooting.rst.txt) — D.

### Images et Apify

- IMG-1 [Commons — réutilisation](https://commons.wikimedia.org/wiki/Commons:Reusing_content_outside_Wikimedia?action=raw) — D.
- IMG-2 [Commons — métadonnées](https://www.mediawiki.org/wiki/Extension:CommonsMetadata?action=raw) — D.
- IMG-3 [Wikimedia — limites API](https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits?action=raw) — D.
- IMG-4 [Pexels — licence](https://www.pexels.com/license/) — I.
- IMG-5 [Pexels — API](https://www.pexels.com/api/documentation/) — I.
- IMG-6 [Pexels — conditions](https://www.pexels.com/terms-of-service/) — I.
- IMG-7 [Pexels — précisions API](https://help.pexels.com/hc/en-us/articles/900005880463-What-are-the-Terms-and-Conditions) — I.
- IMG-8 [Unsplash — documentation](https://unsplash.com/documentation) — D.
- IMG-9 [Unsplash — hotlinking](https://help.unsplash.com/en/articles/2511271-guideline-hotlinking-images) — D.
- IMG-10 [Unsplash — droits complémentaires](https://help.unsplash.com/en/articles/2612329-releases-and-trademarks) — D.
- APIFY-1 [Apify — tarifs](https://apify.com/pricing) — D.
- APIFY-2 [Apify — abonnements](https://docs.apify.com/account/subscriptions.md) — D.
- APIFY-3 [Apify — coûts des Actors](https://docs.apify.com/actors/running/actors-in-store.md) — D.
- APIFY-4 [Apify — limites](https://docs.apify.com/account/limits.md) — D.
- APIFY-5 [Apify — stockage](https://docs.apify.com/storage.md) — D.
- SKILL-1 Audit local du skill `apify-ultimate-scraper` (`SKILL.md`, `references/actor-index.md`, `references/gotchas.md`, workflows) — fichiers de l’agent lus le 13 novembre 2026 ; voir [APIFY_SKILL_AUDIT.md](APIFY_SKILL_AUDIT.md). Aucune exécution, aucun login, aucun token, aucune modification du skill.

### Messages, orchestration et hôtes

- MSG-1 [Telegram — Bot API](https://core.telegram.org/bots/api) — D.
- MSG-2 [Telegram — FAQ bots](https://core.telegram.org/bots/faq) — D.
- MSG-3 [Telegram — confidentialité](https://telegram.org/privacy) — D.
- MSG-4 [Meta — tarifs WhatsApp](https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing) — D, texte recoupé directement.
- MSG-5 [Meta — modèles WhatsApp](https://developers.facebook.com/documentation/business-messaging/whatsapp/templates/overview) — D.
- N8N-1 [n8n — licence](https://docs.n8n.io/n8n-community-license) — D.
- N8N-2 [n8n — Community Edition](https://docs.n8n.io/deploy/host-n8n/community-edition-features) — D.
- N8N-3 [n8n — Telegram Trigger](https://docs.n8n.io/integrations/builtin/trigger-nodes/n8n-nodes-base.telegramtrigger/common-issues) — D.
- HOST-1 [Oracle — Free Tier et essai](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier.htm) — D.
- HOST-2 [Oracle — quotas Always Free](https://docs.oracle.com/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm) — D, quotas recoupés directement.
- HOST-3 [Oracle — FAQ](https://www.oracle.com/fr/cloud/free/faq/) — D.
- HOST-4 [Oracle — confidentialité](https://www.oracle.com/legal/privacy/services-privacy-policy.html) — D.
- HOST-5 [Northflank — pricing/billing docs](https://northflank.com/docs/v1/application/billing/pricing-on-northflank) — D ; moyen de paiement exigé pour créer des ressources. Recoupé par essai réel de l'utilisateur (17 nov 2026) — R.
- HOST-6 [Modal — billing guide](https://modal.com/docs/guide/billing) — D ; moyen de paiement obligatoire, dépassement des crédits débité automatiquement. Recoupé par freetier.wiki (02 nov 2026) — D.
- HOST-7 [Leapcell — pricing](https://leapcell.io/pricing) — D ; serveurs persistants payants, plan gratuit serverless sans disque persistant (évaluation FastOpp, sept 2025) — D.

Les sources LinkedIn sont centralisées dans [API_INTEGRATIONS.md](API_INTEGRATIONS.md) pour garder une référence unique aux permissions, versions et restrictions de données. Les références LI-12/13 ajoutent une contrainte importante : données d’activité des membres lues via Marketing APIs limitées à 48 h et restrictions de transfert ; un accès technique ne suffit donc pas à autoriser leur conservation ou leur envoi à un LLM. Les textes fournis indépendamment par l’utilisateur sont distingués explicitement.
