# Ordre de développement et portes de validation

Date : 13 novembre 2026, Mission 0.6. **Socle validé (Python, SQLite central, Telegram, Tunisie/`Africa/Tunis`, API officielle, 0 €, validations séparées, archive textuelle sans fichiers images) ; décisions utilisateur du 13 novembre intégrées (hébergement local, Groq/OpenRouter à comparer, tableau de bord local, rappel 10 h).** Les phases ci-dessous sont indépendamment livrables ; aucune estimation de délai n’est un engagement. Aucun accès fournisseur n’est présumé.

**État d'avancement :** phases 2 à 4 livrées localement, plus le cœur local de la phase 8 (rappels `Africa/Tunis`, `/lastpost`, `/reminder`, tick sans rafale). **Phase 1 (volet B) livrée le 14 novembre 2026 :** loader `.env` stdlib + validation par nom au démarrage ; rappel 10 h modifiable ; paramètres progressifs partagés (`/settings` Telegram + tableau de bord, même SQLite) ; contrat `Publisher` formalisé avec résolution dynamique treg (`resolve_treg_connection`) ; contrat `LLMProvider` + adaptateurs simulés Groq/OpenRouter + harness + table `llm_benchmarks` (aucun appel réel, aucune sélection) ; squelette du tableau de bord local `127.0.0.1:8000` (configuration + état système, aucune publication) — **117 tests sans réseau passants ; gate G1 atteint côté code** (aucune action externe). Accès de publication provisionné via treg (ADR-16) — identité et `w_member_social` vérifiés, publication réelle NON TESTÉE.

## Principes

- Distinguer autorisation de coder, de configurer un compte et d’effectuer une action externe. Chaque test réel (surtout publication/upload) exige une autorisation séparée sur le contenu exact.
- Sécurité d’état et tests simulés avant tout appel de publication réel ; une preuve réelle s’obtient en sortie de phase, jamais comme prérequis circulaire.
- L’archive, l’import générique et le profil local ne dépendent ni d’Apify, ni du LLM, ni de l’accès publication : ils peuvent être livrés et testés avec des originaux autorisés et des fixtures.
- Si un gate échoue, conserver les fonctions non concernées et demander une décision explicite ; ne pas déclarer l’objectif complet atteint.
- Aucune bascule payante, aucun contournement LinkedIn, aucune persistance sans droits vérifiés.

## Phase 0.5 — Spécification consolidée (documentaire)

Livrables : les neuf documents alignés (archive centrale, import indépendant, profil descriptif + règles confirmées, retrieval borné, rétention par origine, images sans archive binaire), décisions validées vs proposées, sources datées.

**Non fait à ce stade (Phase 0.5, documentaire) :** code applicatif, dépendances, comptes, tokens, collecte, publication. Le socle applicatif a été livré depuis aux phases 2 à 4 ; l’audit du skill, réalisé en Mission 0.6, est consigné dans [APIFY_SKILL_AUDIT.md](APIFY_SKILL_AUDIT.md).

**Sortie :** l’utilisateur a autorisé le démarrage de l’implémentation le 13 novembre 2026 (dépôt GitHub créé, documentation poussée). Les modalités restantes restent à confirmer ; chaque action externe exige une autorisation distincte.

## Phase 1 — Préparation configurable et vérifications non publiantes (révisée)

**Dépendances :** périmètre volet B **validé par l'utilisateur le 14 novembre 2026** (ordre ajusté : 1. secrets, 2. rappel 10 h, 5. contrat Publisher, puis 3. paramètres partagés, 4. LLM, 6. dashboard) ; aucune action externe sans accord distinct. Le développement local n'est bloqué ni par l'hébergement (PC utilisateur décidé) ni par le choix définitif du modèle.

### Volet A — Vérifications et décisions restantes (humain, sans publication)

**Couvert par treg (14 novembre 2026, ADR-16) :** l'application Developer et le callback OAuth ne sont plus requis — la connexion treg `linkedin` (capability `write`) est active, l'identité (`v2/userinfo` → 200, sub membre) et `w_member_social` sont vérifiés, sans publication.

Restent :

- Fournisseurs : l'utilisateur crée le `.env` local (Groq, OpenRouter, Telegram, recherche) ; offre/pays/quota/ZDR et absence de facturation automatique à recontrôler ; Tavily sans PAYG. Aucun modèle figé avant les tests comparatifs.
- Consentements par usage/destination (Telegram inclus) ; paramètres de rétention, retrieval, RAM images ; seuil d'inactivité 120 h proposé.
- Qualification **réelle** (test autorisé distinct, pas documentaire — le catalogue treg l'atteste déjà) : POST `/rest/posts`, version `LinkedIn-Version` supportée, parcours image (initializeUpload → PUT pré-signé → référence média ; restriction GET) ; aucun test de création sans autorisation sur le contenu exact.
- Conditions et confidentialité du service treg (flux d'appels hébergé, tiers) à accepter explicitement ; gestion de la rotation (reconnexion utilisateur après révocation) à prévoir dans l'adaptateur.

### Volet B — Préparation locale (code, simulé, sans réseau)

Périmètre précis proposé, à valider avant codage :

1. **Secrets et démarrage** : chargement `.env` (parseur stdlib minimal), validation des variables requises par leur nom au démarrage avec messages explicites sans révéler les valeurs ; `.env.example` déjà créé ; mode simulation conservé sans jeton. Tests : variable manquante signalée sans contenu, aucune clé dans logs/erreurs.
2. **Rappel 10 h** : défaut `DEFAULT_HOUR` 9 → 10 (modifiable), jours/activation inchangés ; tests de créneau existants adaptés.
3. **Paramètres progressifs partagés** : extension de `settings` (thématiques, ton, public cible, longueur, langue, fréquence, horaires rappels, préférences recherche/images, modèle LLM, fournisseur recherche) ; lecture/écriture via commandes Telegram ; mêmes valeurs servies au tableau de bord. Aucune valeur figée arbitrairement ; règles normatives toujours confirmées séparément.
4. **Abstraction LLM + comparaison** : contrat `LLMProvider` unique, adaptateurs Groq et OpenRouter (simulés en tests), sélection modèle/fournisseur par paramètre ; harness de comparaison sur tâches identiques (mesure latence/usage, évaluation humaine du français/instructions/style) ; table `llm_benchmarks` proposée. Aucun appel réel ni sélection définitive dans cette phase ; aucun fallback payant.
5. **Interface de publication** : formaliser le contrat `Publisher` (déjà `SimulatedPublisher`) en prévoyant le futur adaptateur treg : résolution **dynamique** de la connexion `linkedin` health=ok via `treg connections ls` (la rotation treg crée des `linkedin-N` ; jamais de nom ni de secret en dur), preuve de publication = HTTP 201 + URN `x-restli-id`, aucun appel treg mesuré, `NO_PROXY=` vide préfixé à chaque invocation (bug machine). Aucun adaptateur réel tant que la qualification réelle n'est pas faite et autorisée.
6. **Squelette du tableau de bord local** : serveur HTTP stdlib lié à `127.0.0.1` (port 8000 proposé), sections « configuration générale » et « état système » en lecture/écriture partagée avec SQLite ; pas de second chemin de publication ; pas d’exposition publique. Développement progressif des autres sections aux phases suivantes.

**Gate G1 (local) :** tests sans réseau passants (secrets, rappel 10 h, paramètres partagés, adaptateurs LLM simulés, dashboard loopback) ; aucune action externe ; variables manquantes signalées sans contenu ; aucun modèle sélectionné définitivement ; aucune clé dans le code/logs. **Atteint côté code le 14 novembre 2026 (117 tests, démarrage réel et dashboard vérifiés en boucle locale)** ; les vérifications du volet A restent explicitement à effectuer ; si blocage publication : mode préparation sans publication, pas un objectif complet atteint.

## Phase 2 — Socle conversationnel et garanties d’état (local, simulé)

**Dépendances :** G1 pour les choix de configuration ; le code du socle peut être développé avec adaptateurs simulés sans aucun compte réel.

- Configuration minimale, secrets locaux, liste propriétaire/chat autorisés.
- SQLite : `settings`, `drafts`, `draft_versions`, `approvals`, `publication_intents`, `events`, `preferences`, `quota_usage` ; WAL, transactions courtes, migrations.
- Réception Telegram long polling (ou simulée), déduplication `update_id`, intentions, clarification, statuts.
- Validations texte/image/absence/finale, manifeste exact, empreintes d’approbation et de contenu, consommation atomique, intention durable, verrou de compte.
- Adaptateur de publication simulé : succès, refus, réponse perdue, crash ; purge brouillons 30 j proposée ; logs expurgés.

**Gate G2 (tests locaux) :** invariants SEC/VAL/DUP de TEST_STRATEGY passants ; double clic, message répété, compte non autorisé, ancienne révision, crash, restauration ; « OK » libre et contenu web malveillant ne publient jamais ; aucune transaction réseau.

**Livrable :** saisir/corriger un brouillon, le prévisualiser, le retrouver après redémarrage, sans recherche ni publication réelle.

## Phase 3 — Archive centrale et import générique (indépendant d’Apify)

**Dépendances :** G2 ; droits d’import par origine définis (G1). Ni LLM, ni accès LinkedIn, ni skill requis.

- Tables `history_posts`, `history_versions`, `history_identifiers`, `history_sources`, `import_batches` ; index et contraintes d’unicité.
- `History.record_confirmed` : reçu + succès + texte exact en transaction locale atomique (testé avec publication simulée) ; `published_at`/`confirmed_at`/`imported_at` distincts, précision/fuseau, nullables honnêtes.
- Contrat `ImportProvider` + parsing borné (proposition 100 éléments/2 Mio), comparaison ID typé puis repli conservateur, statuts nouveau/connu/version/conflit/ambigu/refus.
- Aperçu immuable, accord lot/éléments, commit idempotent du sous-ensemble choisi, revalidation des droits et révisions ; rollback complet si plan périmé.
- Versions non destructives, null sans effacement, provenance réelle multiple, absence ≠ suppression ; effacement requis/demandé propagé.
- Fixtures : originaux utilisateur autorisés, exports simulés multi-formats ; aucun Actor exécuté.

**Gate G3 (tests locaux) :** invariants HIST/IMP passants ; rejeu de lot sans doublon ; course import/archivage simulée résolue sans double post ; import ne lève jamais `UNKNOWN_OUTCOME` ; purge brouillons sans perte d’archive autorisée ; droits inconnus sans persistance.

**Livrable :** archive consultable localement et import manuel confirmé, utilisable sans aucun service externe.

### Phase 3B — Adaptateur du skill Apify (optionnelle, après audit)

**Dépendances :** G3 + audit du skill terminé (fait le 13 nov, voir [APIFY_SKILL_AUDIT.md](APIFY_SKILL_AUDIT.md)) + droits vérifiés + accord utilisateur. Traduire sa sortie réelle vers le contrat d’import générique ; aucune modification du skill original ; coûts Apify bornés et mesurés avant usage ; mode préféré = export utilisateur ingéré par l’importeur existant (Phase 3). Si la collecte n’est pas conforme, la phase 3 reste livrée.

## Phase 4 — Profil descriptif et retrieval borné (local)

**Dépendances :** G3. LLM non requis pour le calcul local et les tests.

- `style_profile` persistant borné (≤4 000 caractères proposés), références versions/périodes/couverture/confiance ; textes assistant étiquetés ; aucune règle normative implicite.
- `History.query` : filtres indexés + FTS5 si disponible (sinon repli borné), ≤6 posts/12 000 caractères proposés ; règles confirmées séparées non tronquées.
- Invalidation/recalcul après ajout, version, suppression, changement de droits ; dérivés héritant des restrictions ; vérification des droits avant chaque destination.
- Alertes locales de répétition thématique/textuelle, explicables, non bloquantes.

**Gate G4 (tests locaux) :** invariants MEM/RET passants ; profil recalculé après effacement de source ; aucun dérivé interdit exporté ; budget de retrieval respecté ; FTS5 absent ⇒ repli fonctionnel.

**Livrable :** sélection d’exemples pertinents et profil à jour, sans génération LLM.

## Phase 5 — Recherche web et rédaction

**Dépendances :** G4 + fournisseurs LLM/recherche qualifiés (conditions, pays, quotas, ZDR, consentement), clés utilisateur fournies et comparaison Groq/OpenRouter réalisée.

- SearchProvider Tavily basic, réserve de quota, extraction HTTP sécurisée (SSRF, tailles, délais) ; dossier multi-source daté, contradictions et manques visibles.
- LLMProvider Groq/OpenRouter ; sélection du modèle après tests comparatifs (français, instructions, style, latence, limites), jamais avant ; prompts bornés avec profil + échantillon autorisé ; français naturel, aucun fait personnel inventé, aucune promesse future ; aucun fallback payant.
- Corrections ciblées avec différences visibles ; changement factuel ⇒ revérification ; proposition/confirmation distincte des règles permanentes ; révocation.
- Tableau de bord : sections éditoriale, IA (fournisseurs/modèles/benchmarks) et recherches branchées sur la même configuration SQLite.

**Gate G5 :** recette humaine sur plusieurs sujets/corrections ; sources réellement consultées ; pas d’apprentissage implicite ; pas de facturation ni boucle de recherche illimitée ; droits de transfert vérifiés avant chaque envoi.

**Livrable :** assistant éditorial complet sans publication activée.

## Phase 6 — Publication officielle texte seul

**Dépendances d'entrée :** G2/G5, accès treg actif (ADR-16, fait le 14 nov) et qualification réelle du POST `/rest/posts` par un test autorisé distinct, protocole documentaire cohérent, consentement au test réel. La preuve de création s'obtient en sortie G6.

- Adaptateur officiel uniquement, via treg (ADR-16) : résolution dynamique de la connexion `linkedin` health=ok, version explicite, en-têtes, règles d'erreur ; préflight et aperçu final ; publication liée au manifeste exact et à l'autorisation consommée ; preuve = 201 + URN `x-restli-id`, jamais le scraping treg.
- Reçu/URN, `PUBLISHED` + archive exacte en transaction locale ; historique et dernière publication connue actualisés ; notification Telegram séparée et reprenable.
- Reconnexion OAuth, expiration, refus de scope, rate limiting, `UNKNOWN_OUTCOME` et réconciliation ; aucun retry automatique d’envoi incertain.
- Premier test de création réelle ici, contenu validé, protections du socle actives ; refus/échec ⇒ capacité non activée.

**Gate G6 :** un post réel autorisé confirme le parcours sur le bon profil ; pannes simulées complètes ; archive atomique vérifiée ; aucune suppression du post de test sans demande distincte.

## Phase 7 — Images existantes et droits

**Dépendances d’entrée :** G6, sources et prérequis documentaires du parcours image vérifiés. Preuve réelle upload/publication en sortie G7.

- Recherche Commons, provenance/licences/restrictions/crédits ; téléchargement et figement **en RAM** (modalité à valider), empreinte, dimensions/MIME bornés.
- Validation image/absence séparée ; crédit ajouté avant validation texte ; perte du tampon ⇒ nouvel aperçu et approbations image/finale.
- Upload officiel via treg (ADR-16) : initializeUpload → URL pré-signée → PUT du fichier approuvé (curl.exe, pas Invoke-WebRequest) → référence `media` ou `multiImage` (repli media si 422) ; sans GET de statut non autorisé ; gestion des états/erreurs du protocole vérifié ; aucun binaire persisté.
- Test réel image avec consentement spécifique ; pipeline bloqué ⇒ texte seul après nouvelles validations explicites.

**Gate G7 :** preuve d’utilisation du fichier approuvé et de droits documentés ; aucun média non validé ; aucune archive binaire ; aucune API privée. Pexels/Unsplash/génération : extensions ultérieures seulement.

## Phase 8 — Rappels et exploitation

Les rappels peuvent être développés après G2 avec date fournie manuellement, puis branchés sur l’archive (G3) et la publication (G6).

- Créneaux `Africa/Tunis` (rappel quotidien 10 h par défaut, modifiable), jours, pause, inactivité 120 h proposée ; `published_at` accepté jamais `imported_at` ; dates imprécises/futures/conflit clarifiées ; `confirmed_at` seulement en approximation signalée.
- Déduplication quotidienne, fusion des motifs, reprise sans rafale, heure manquante/répétée ; déclaration de publication hors bot.
- Exploitation sur le PC utilisateur (dev/tests) ; Oracle Always Free à étudier plus tard, PC ami en secours ; aucune installation distante sans accord. Service, permissions, sauvegarde chiffrée des seules données autorisées, restauration en publication bloquée + réconciliation ; purges et invalidation des dérivés ; statuts quota/capacité ; rotation des logs.
- Tableau de bord : section état système complète (services, erreurs, quotas, dernières exécutions) ; authentification et protection des secrets obligatoires si exposition Internet ultérieure.

**Gate G8 :** scénario complet sur l’hôte réel ; bot utilisable sans rappel ; restauration testée ; responsabilité d’exploitation acceptée ; aucun SLA promis.

## Extensions seulement si justifiées

Autre fournisseur LLM/recherche/image qualifié ; n8n si bénéfice visuel confirmé ; génération d’images si offre récurrente 0 € compatible ; lecture officielle historique si scope et conditions de conservation/transfert démontrés. Pas de calendrier autonome, multi-utilisateur ni analytics sans nouvelle demande.

## Dépendances critiques résumées

- Publication = identité/scopes + protocole officiel vérifié + contenu complet + validations + anti-doublon.
- Archive = succès fiable (source A) ou droits + aperçu + accord (source B) ; jamais l’inverse.
- Style = archive autorisée + profil descriptif + règles confirmées ; retrieval borné, pas de réexport complet.
- Image = droits + octets figés en RAM + approbation séparée + pipeline LinkedIn vérifié.
- Rappel = date de publication fiable + heure/fuseau + hôte actif ; jamais date d’import.
- Gratuité = configuration de compte + quotas + refus des dépassements + frais indirects acceptés.

## Définition de fin du premier produit

L’utilisateur propose une idée sans rappel, obtient un brouillon sourcé adapté à son historique autorisé, corrige précisément, choisit ou refuse une image, publie par API officielle après validations explicites, et retrouve le texte dans l’archive centrale. Pannes et quotas ne causent ni coût automatique, ni doublon rejoué, ni publication non validée, ni perte silencieuse de données autorisées. Preuves selon [TEST_STRATEGY.md](TEST_STRATEGY.md), pas seulement un processus qui démarre.
