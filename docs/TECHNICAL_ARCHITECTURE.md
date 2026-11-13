# Architecture technique proposée

Date : 13 novembre 2026. **Mission 0.5, conception uniquement.** Python, SQLite central, Telegram principal, n8n facultatif, Tunisie/`Africa/Tunis`, publication officielle, budget 0 €, validations séparées et archive textuelle sans fichiers images sont validés par l’utilisateur. Les contrats, schémas et paramètres ci-dessous restent proposés. Aucun composant n’est implémenté.

## 1. Décision de structure

**Un monolithe modulaire Python, un processus actif, une base SQLite locale, un canal Telegram.** Les appels LLM, recherche, historique, images et publication passent par des adaptateurs remplaçables. Un planificateur interne léger crée des événements de rappel ; il n’autorise jamais de publication.

```text
Utilisateur <-> Telegram <-> Orchestrateur déterministe
                               |       |         |
                           Recherche Rédaction Images en RAM
                                       |
                      Profil compact + requêtes SQLite ciblées
                                       |
                          Brouillons et validations séparées
                                       |
                           Autorisation finale exacte
                                       |
                         Publication -> API officielle LinkedIn
                                       |
                     Confirmation fiable -> archive texte SQLite

Originaux utilisateur / skill audité / autre source autorisée
  -> adaptateur d'import -> contrôle des droits -> comparaison
  -> aperçu + confirmation -> même archive SQLite versionnée

SQLite : archive + profil + règles + brouillons + registre d'envoi
Planificateur -> rappels ; garde de quota -> appels fournisseurs
```

L’historique durable est indépendant d’Apify et du droit de lecture LinkedIn. La capacité de publier ne prouve pas celle de lire, de conserver ou de transférer un post. L’absence de fichiers images est satisfaite par une proposition RAM seule, détaillée plus bas.

Le LLM propose des intentions et du texte ; l’orchestrateur contrôle leur admissibilité. Aucun outil LinkedIn n’est mis à disposition du modèle. Un contenu extrait n’est jamais traité comme une instruction de contrôle.

### Ce qui n’est pas nécessaire

Ni microservices, ni Redis, ni Celery, ni Kubernetes, ni bus externe, ni Postgres initial, ni base vectorielle, ni interface web permanente, ni second framework agentique. Les interfaces ci-dessous sont des contrats internes, pas des services HTTP séparés. n8n peut être réévalué si l’utilisateur privilégie réellement l’édition visuelle ; il ne doit pas doubler le moteur d’état métier.

## 2. Modules et responsabilités

| Module logique | Responsabilité | N’a pas le droit de faire |
|---|---|---|
| Conversation | Recevoir messages/boutons, vérifier propriétaire et chat privé, afficher état et aperçus | Déduire une autorisation de publication d’un texte libre |
| Orchestrateur | Associer une demande au bon brouillon, gérer versions, états et confirmations | Contourner les validations pour satisfaire une réponse du modèle |
| Planification | Calculer créneaux et inactivité, dédupliquer les rappels | Appeler le service de publication |
| Recherche | Requêtes, extraction, provenance, corroboration, dates et incertitudes | Suivre des instructions intégrées dans les pages ; contourner un accès |
| Rédaction/style | Réviser depuis sources, profil compact et exemples ciblés autorisés | Inventer des faits personnels ou transformer une observation en règle |
| Préférences | Présenter puis stocker uniquement des règles confirmées | Apprendre une règle durable d’une correction implicite |
| Images | Droits, téléchargement/transformations et octets figés en RAM | Archiver un fichier ou assimiler disponibilité et licence |
| Historique | Archiver textes autorisés, versions, identifiants et provenances ; recherche locale ciblée | Affirmer complétude ou succès du bot à partir d’un import |
| Import | Normaliser un format indépendant, comparer, préparer un aperçu et engager les choix | Exécuter un Actor non audité, persister sans droits, fusionner un conflit silencieusement |
| Profil rédactionnel | Maintenir une synthèse descriptive compacte avec filiation des sources | Exporter un dérivé interdit ou confondre style généré et préférence humaine |
| Publication | Préflight, verrou, envoi officiel, preuve de résultat et réconciliation | Recevoir directement une commande du LLM ou répéter un envoi incertain |
| Stockage/exploitation | Transactions, reprises, purges, sauvegardes, logs expurgés | Conserver les secrets dans la base métier ou les logs |
| Fournisseurs/quotas | Traduction des contrats internes, plafonds, délais, compteurs | Activer une offre payante ou changer les termes de confidentialité sans accord |

Les modules sont des frontières de responsabilité dans un seul dépôt et processus, pas une obligation de créer une classe ou un fichier pour chaque ligne.

## 3. Déroulement et états

### Brouillon

États conceptuels : `IDEA`, `RESEARCHING`, `DRAFT`, `REVIEW`, `READY`, `PUBLISHING`, `PUBLISHED`, `BLOCKED`, `CANCELLED`. `BLOCKED` comprend une raison explicite : quota, accès, sources, droits, incertitude. Les approbations sont des enregistrements séparés, pas un unique booléen « approuvé ».

- Un nouveau contenu crée une révision immuable et change le pointeur courant du brouillon.
- Chaque tâche longue porte l’identifiant du brouillon et sa révision de départ. Un résultat arrivé après une modification n’écrase pas la révision courante.
- Un brouillon `READY` possède les approbations requises mais n’est pas encore autorisé à être publié.
- Le bouton final crée une autorisation à usage unique sur le manifeste exact. Le passage à `PUBLISHING` la consomme atomiquement.
- Une annulation avant l’envoi invalide l’autorisation. Après départ de la requête, ne pas promettre d’annuler la publication ; une éventuelle suppression LinkedIn serait une action distincte, hors MVP.
- Une édition concurrente pendant `PUBLISHING` est bloquée ; la demande est conservée pour clarification, sans modifier le contenu déjà envoyé.

### Objet exact approuvé

Le manifeste contient : compte auteur, identifiant brouillon, révision, texte complet, visibilité, choix image/absence, empreinte SHA-256 des octets d’image, crédit intégré, texte alternatif et version du contrat de publication. L’empreinte d’approbation porte sur une sérialisation déterministe incluant brouillon et révision ; aucune normalisation invisible du texte après validation. Une empreinte de contenu distincte, utilisée contre les doublons entre brouillons, inclut auteur, texte exact, visibilité et média, mais exclut identifiants internes, révision, dates et nonce.

| Changement | Validation texte | Validation image | Autorisation finale |
|---|---|---|---|
| Texte ou crédit intégré au texte | Invalide | Préservée si fichier/droits/texte alternatif identiques | Invalide |
| Fait/recherche qui change l’appui du texte | Invalide | Préservée si inchangée | Invalide |
| Image, recadrage, recompression, texte alternatif, droits | Préservée si texte inchangé | Invalide | Invalide |
| Passage image vers « sans image » ou inversement | Préservée sauf changement de crédit | Nouveau choix explicitement approuvé | Invalide |
| Auteur ou visibilité | Préservée pour le contenu seulement | Préservée pour le contenu seulement | Invalide ; nouvel aperçu obligatoire |
| Fournisseur LLM sans modification de contenu | Préservée | Préservée | Préservée uniquement si manifeste identique et autorisation encore valide |

Une approbation d’image ne peut pas être accordée à une URL distante mutable : télécharger/valider le fichier avant son aperçu. Toute transformation doit précéder l’aperçu final. L’image envoyée à LinkedIn est exactement le fichier approuvé, même si Telegram en affiche une prévisualisation compressée.

Proposition : expiration de l’autorisation finale après 10 minutes ; cette durée est une règle interne, à valider. Si une préparation média dépasse la durée, une nouvelle autorisation finale est nécessaire. Les boutons utilisent des références opaques courtes vers la base, liées au propriétaire, au chat, à la révision, au type d’action et à l’échéance. Le contenu complet ne transite pas dans `callback_data`.

## 4. Interfaces internes

Les noms sont des contrats de conception, pas des fonctions déjà disponibles. Dates UTC au format ISO 8601 avec fuseau ; horaires utilisateur en fuseau IANA ; identifiants internes opaques ; URLs externes validées avant lecture ; budgets en unités explicites.

| Contrat | Entrées minimales | Sortie attendue | Effets/persistance |
|---|---|---|---|
| `Conversation.receive` | Identifiant événement, propriétaire, chat, date, texte ou référence de bouton | Intention validée ou clarification | Événement dédupliqué avant traitement |
| `Schedule.next_due` | Paramètres, dernière publication confirmée, heure actuelle | Prochain rappel et motif fusionné | Échéance et clé unique par jour local |
| `ImportProvider.read` | Source autorisée, auteur attendu, limites de lot et curseur | Enveloppe structurée indépendante du fournisseur, provenance réelle, couverture | Lecture bornée ; aucune écriture historique ni exécution automatique d’Actor |
| `Import.preview/commit` | Lot admissible, versions SQLite attendues, choix explicites de l’utilisateur | Nouveaux/connus/versions/conflits/ambiguïtés/refus, puis bilan | Plan immuable et commit idempotent ; aperçu périmé refusé |
| `History.record_confirmed` | Intention durable, reçu fiable, texte exact local et métadonnées autorisées | Publication historique et lien vers l’intention | Même transaction que succès/reçu ; pas de succès créé par import |
| `History.query` | Auteur, thème/texte, période, usage/destination, limites | Versions autorisées et références, couverture/incertitudes | Lecture locale indexée ; jamais archive entière par défaut |
| `StyleProfile.refresh` | Versions autorisées, observations précédentes, limites | Synthèse descriptive avec période, confiance et filiation | Cache persistant borné ; aucune règle approuvée créée implicitement |
| `SearchProvider.search` | Question, langue, période, nombre maximal, budget | Résultats : URL, titre, extrait, date si attestée | Réservation de quota et provenance fournisseur |
| `Extractor.fetch` | URL autorisée, taille/délai maximum | Texte nettoyé, URL finale, titre, dates, statut, empreinte | Cache court ; aucune conservation du HTML complet par défaut |
| `Research.build` | Idée, questions, sources précédentes, budget | Dossier : sources, affirmations, références, contradictions, manques | Snapshot dans la révision de brouillon |
| `LLMProvider.complete` | Instruction bornée, dossier, exemples minimisés, limite de sortie | Proposition structurée, usage, fournisseur/modèle exacts | Aucun outil de publication ; réponse non fiable à valider |
| `Writer.revise` | Révision de base, demande, dossier vérifié, règles acceptées | Nouveau texte, résumé des différences, faits à revérifier | Nouvelle révision, jamais une préférence implicite |
| `Preference.propose/confirm` | Règle textuelle exacte, portée, accord référencé | Préférence active ou refus | Écriture durable seulement après confirmation distincte |
| `ImageProvider.search` | Sujet, droits recherchés, nombre maximal | Candidates : page source, fichier, auteur, licence, crédit, restrictions | Pas d’approbation automatique |
| `Image.prepare` | Candidate, transformations autorisées, limites mémoire | Octets finaux en RAM, empreinte, dimensions, MIME, droits et texte alternatif | Métadonnées seulement en base ; perte du tampon invalide image/finale |
| `Approval.record` | Acteur autorisé, action, objet/empreinte, échéance | Approbation ou rejet de référence périmée | Transaction et trace minimale |
| `LinkedIn.capabilities` | Métadonnées OAuth et version ciblée | Capacités `identity`, `write_text`, `write_image`, `read_own_posts`, `read_image_status` séparées | Preuve datée ; états documenté/non testé/testé/refusé |
| `LinkedIn.prepare_media` | Compte et image autorisés, consentement de transfert | URN média et niveau de preuve de disponibilité | Aucun post ; transfert après autorisation finale seulement |
| `LinkedIn.publish` | Manifeste, intention durable liée exclusivement à l’autorisation déjà consommée pour elle, validité temporelle et absence d’envoi antérieur contrôlées | Reçu officiel, échec certain ou résultat incertain | Seul point d’émission d’un post ; ne consomme pas une seconde autorisation et ne rejoue pas une intention envoyée |
| `Quota.reserve/settle` | Fournisseur, coût maximum estimé, unités, fenêtre | Autorisé ou pause jusqu’à date connue | Réservation atomique avant réseau ; comptabilisation réelle après retour |

### Structures communes

- Source : identifiant, URL canonique/finale, titre, éditeur, date de publication si connue, date de consultation, extrait utile, statut d’accès, empreinte. Une date absente reste absente.
- Affirmation : texte, références de sources, nature fait/opinion, statut vérifié/contesté/insuffisant, justification courte.
- Post historique : texte intégral original, auteur, identifiants typés/URL attestés éventuellement absents, version, `published_at` avec précision/fuseau/source, `confirmed_at` si succès du bot, observations d’acquisition `imported_at`, origines réelles, droits par champ/usage/destination et couverture. Une date seule n’est pas transformée en heure exacte ; l’heure d’import n’est pas l’heure de publication.
- Erreur fournisseur : catégorie `AUTH_REQUIRED`, `PERMISSION_DENIED`, `QUOTA_EXHAUSTED`, `TEMPORARY_FAILURE`, `INVALID_INPUT`, `UNSUPPORTED`, `UNKNOWN_OUTCOME`, date de reprise éventuelle, message expurgé.
- Un champ « idempotency key » interne n’est jamais présenté comme une garantie offerte par LinkedIn. Les informations spécifiques à un fournisseur restent dans son adaptateur ou une métadonnée opaque, pas dans les règles métier.

## 5. Persistance réellement nécessaire

SQLite convient à une personne, un hôte, peu d’écritures, et des transactions courtes. Le choix n’est pas adapté à plusieurs instances actives ni à un partage réseau du fichier. Proposer clés étrangères, mode WAL, synchronisation durable, transactions explicites et délais bornés ; les paramètres exacts seront testés sur l’hôte retenu.

### Tables logiques proposées

| Table | Données nécessaires | Justification et contraintes |
|---|---|---|
| `settings` | Propriétaire/chat autorisés, fuseau, rappels, thème, consentements prestataires, références de capacités OAuth sans secrets | Paramètres qui doivent survivre au redémarrage ; un seul profil actif |
| `drafts` | Identifiant, état, révision courante, dates, dernier blocage | Reprise de conversation et contrôle de concurrence |
| `draft_versions` | Révisions immuables, texte, dossier de recherche compact, manifeste image et empreintes | Prouver ce qui a été approuvé ; unique `(draft_id, revision)` |
| `approvals` | Type texte/image/absence/final/règle, acteur, référence exacte, date/expiration, consommation | Contrôle explicite et références à usage unique ; pas de transcript complet |
| `publication_intents` | Intention, brouillon unique, auteur, empreinte de contenu, état, dates, reçu/URN autorisés, lien historique nullable | Registre des tentatives distinct de l’archive ; une intention par brouillon, un envoi actif par compte |
| `events` | Inbox Telegram, rappels, tâches bornées, état/lease, échéance, révision de base | File SQLite légère ; clé externe unique par source |
| `preferences` | Règle exacte, portée, date, référence d’accord | Règles normatives confirmées, distinctes des observations |
| `history_posts` | Post logique, auteur, version courante, date de publication avec précision, visibilité connue, révision du dossier | Archive centrale sans plafond de trois ; aucune suppression en cascade depuis un brouillon |
| `history_versions` | Texte intégral immuable, empreintes exacte et normalisée avec version d’algorithme, origine rédactionnelle, date d’observation | Conserver modifications autorisées ; unicité `(post_id, exact_text_hash)` vérifiée aussi sur le texte |
| `history_identifiers` | Post, namespace, identifiant complet typé, source de la preuve | Unicité de l’identifiant dans son namespace ; aliases uniquement après preuve d’équivalence |
| `history_sources` | Version/post, source réelle, méthode, fournisseur/Actor/version si connu, référence externe, dates d’acquisition, champs observés, politique et échéances | Plusieurs provenances sans écrasement ; observation idempotente, pas de réponse brute illimitée |
| `import_batches` | Origine, empreinte de lot, schéma, plan borné, versions attendues, décisions, état, date d’import | Aperçu/commit reproductibles ; contenu en attente seulement si persistance déjà autorisée |
| `style_profile` | Synthèse descriptive bornée, thèmes/périodes, confiance/couverture, références versions et usages autorisés, version de calcul | Cache dérivé persistant invalidable ; pas de règle normative implicite |
| `quota_usage` | Fournisseur, période, unité, usage réservé/consommé, plafond | Redémarrer ne réinitialise pas le budget |

Les snapshots JSON validés restent petits : sources du brouillon, droits d’image, plan de lot et profil. Aucun JSON fournisseur opaque non borné, ni historique de conversation intégral. Les droits sont portés par les observations et les champs correspondants ; les différentes autorisations de stockage/analyse locale/dérivation/Telegram/LLM ne se réduisent pas à un booléen global.

Index proposés : auteur/date, identifiant typé unique, empreinte normalisée/auteur/date, source/expiration et relations de filiation. FTS5 est un index dérivé local facultatif, seulement sur les versions autorisées à être indexées ; vérifier sa disponibilité dans la distribution SQLite. Sans FTS5, conserver les filtres indexés et chercher sur un sous-ensemble borné, sans imposer un serveur de recherche.

Un index FTS, une empreinte ou un résumé peut aussi être un dérivé soumis à restriction. Supprimer/invalider les entrées liées à une source expirée ; une permission plus large n’est utilisable que si une provenance indépendante la justifie réellement, sans effacer la provenance restrictive.

### Hors base

- Secrets dans un fichier d’environnement privé ou le coffre du système, permissions minimales. La base contient uniquement une référence, les scopes et la date d’expiration, jamais le jeton.
- Réponses HTML brutes en mémoire ; extraits pertinents seulement dans le dossier de recherche.
- Images : recommandation **RAM seule** de bout en bout, sans BLOB, fichier temporaire, cache SDK sur disque ni binaire dans les sauvegardes. Métadonnées autorisées, empreinte et preuve de droits seulement en SQLite. Taille compressée, dimensions et mémoire décodée bornées avant traitement.
- Perte du tampon (arrêt, expiration ou pression mémoire) : invalider image et autorisation finale ; nouveau téléchargement/choix, aperçu et accord. Ne pas reprendre un upload depuis une simple URL mutable. Si le POST a déjà pu partir, conserver le verrou d’incertitude indépendamment de la perte d’image.
- Une empreinte ne permet pas de reconstituer les pixels ; on ne promet ni une archive visuelle ni l’absence de swap/hibernation du système. Les copies Telegram/LinkedIn restent régies par leurs politiques. Cette solution RAM est une modalité proposée du choix validé « pas de fichiers images ».
- Modèles, instructions statiques et paramètres techniques versionnés ultérieurement avec l’application, pas dupliqués en base sans besoin.

### Import indépendant et déduplication historique

1. **Admissibilité avant acquisition/persistance** : identifier auteur, origine réelle et méthode, conditions applicables, durée par champ, analyses et destinations permises. Un fichier remis par l’utilisateur peut rester une donnée API/Apify. Droits inconnus : pas de stockage provisoire ; inspection en mémoire seulement si elle-même permise.
2. **Lecture bornée** : enveloppe décrite dans API_INTEGRATIONS.md ; proposition 100 éléments/2 Mio par lot, contrôles de schéma, UTF-8, taille et complétude des textes. Pas d’exécution de fichier ni de lien téléchargé automatiquement. Limites à qualifier sur la sortie réelle du skill.
3. **Comparaison** : identifiant typé prioritaire. À défaut, normalisation versionnée NFC, fins de ligne et espaces usuels, sans suppression des nombres, URLs ou ponctuation ni rapprochement agressif. Auteur et précision de date sont indispensables à un rapprochement fiable ; un hash seul ne prouve pas l’identité d’une publication.
4. **Plan immuable** : classer `NEW`, `KNOWN`, `TEXT_CHANGED`, `METADATA_CONFLICT`, `AMBIGUOUS`, `INCOMPLETE`, `POLICY_BLOCKED`. Présenter les différences, droits et choix possibles ; les données de l’aperçu Telegram doivent elles aussi être autorisées. Un lot non exportable n’est pas affiché intégralement dans Telegram.
5. **Confirmation** : accord lié à l’empreinte du plan, à sa révision et aux choix exacts. Les conflits demandent une décision par élément ; aucune fusion « probable » silencieuse. Revalider auteur, droits, échéances et révisions SQLite au commit.
6. **Transaction courte** : engager atomiquement les éléments admissibles choisis du lot, journaliser le résultat et marquer le lot engagé. Si base changée/plan périmé, annuler l’ensemble de ce commit, recalculer et redemander accord. Une répétition retourne le même bilan, sans ajouter un post/version identique. Une nouvelle acquisition peut enregistrer une observation datée, pas une nouvelle publication.
7. **Versions** : même ID avec autre texte ⇒ nouvelle version conservant l’ancienne si permis ; activer seulement le choix confirmé. Null n’efface jamais connu. Identifiants différents/textes semblables ⇒ conserver distincts sauf preuve validée d’alias. Absence du prochain lot ⇒ aucune suppression. Une demande d’effacement ou une échéance légale prime sur la conservation des anciennes versions.

Le lot approuvé peut exclure les refus/éléments incomplets : le bilan indique importés, connus, ignorés, conflits non résolus et couverture. L’échec transactionnel n’importe aucun élément du sous-ensemble choisi. Une course avec l’archivage d’un succès du bot doit faire échouer le plan d’import périmé, pas doubler le post.

Un import externe ne change pas `publication_intents` et ne résout jamais automatiquement `UNKNOWN_OUTCOME`. Si son identifiant semble correspondre, présenter un indice à la réconciliation ; seule une preuve fiable peut confirmer le résultat du bot. Les métadonnées d’une publication externe n’inventent pas une autorisation finale antérieure.

### Profil rédactionnel et récupération ciblée

Deux couches : archive de versions complètes autorisées, puis synthèse descriptive compacte persistante. `preferences` contient séparément les règles exactes approuvées. Les observations (longueur, ton, structures, thèmes, évolution) portent période, couverture, confiance et références des versions ; elles ne sont ni des faits personnels ni des consignes obligatoires. Les textes assistant sont étiquetés pour éviter une boucle d’auto-imitation.

Proposition : profil descriptif ≤4 000 caractères ; récupération ≤6 posts et ≤12 000 caractères d’extraits cumulés par demande. Les règles confirmées sont séparées, jamais supprimées/tronquées silencieusement pour respecter ce budget. Plafonds ajustables après recette et dans le contexte du modèle. Trois posts récents sont un échantillon, pas une limite de stockage.

Filtrer localement droits, auteur et périodes avant recherche FTS ; sélectionner exemples récents, pertinents pour le sujet et éventuellement de périodes différentes. Le dossier transmis contient références et extraits sélectionnés, pas le corpus intégral. Une comparaison locale de thèmes/textes signale une répétition possible sans interdire automatiquement une nouvelle publication différente.

Mettre à jour/invalider le profil lors d’un ajout, changement de version, suppression ou changement de droits. Une reconstruction complète exceptionnelle peut parcourir localement l’archive admissible par lots bornés ; aucune relecture intégrale routinière ni transmission intégrale au LLM. Une observation dérivée de sources mixtes non exportables doit être exclue/recalculée sur les seules sources admissibles avant transfert. Vérification des droits à la lecture et juste avant l’envoi, pas seulement lors de l’import.

## 6. Anti-doublon et reprise

1. Dédupliquer l’événement Telegram par `update_id` et le bouton par son nonce consommable.
2. Vérifier propriétaire, état, révision et validations dans une transaction. La création de l’intention de publication est unique par brouillon ; empêcher en plus deux intentions actives sur le compte.
3. Comparer l’empreinte de contenu, indépendante des identifiants de brouillon, aux publications déjà confirmées et aux intentions actives. Un contenu exactement identique connu est bloqué ; le MVP ne propose pas de bouton « ignorer le doublon ». Pour les publications externes déjà importées, comparer aussi les textes/identifiants autorisés ; un média ou une visibilité inconnus ne permettent pas de reconstruire une empreinte complète et produisent un avertissement à examiner. Cette protection ne prétend pas détecter toute paraphrase ni les publications externes non importées.
4. Consommer l’autorisation finale et enregistrer durablement l’intention avant le moindre transfert LinkedIn. Préparer le média si présent, sous cette autorisation et dans sa durée de validité.
5. Avant le `POST` créateur, marquer l’envoi comme commencé durablement. Ne pas garder une transaction SQLite ouverte pendant le réseau.
6. Sur confirmation officielle fiable, engager dans **la même transaction locale** le reçu autorisé, `PUBLISHED`, l’archive du texte original exact et le lien à l’intention ; rapprocher un éventuel post déjà importé par ID sans écraser son origine. Un conflit de métadonnées reste visible et ne justifie jamais un nouveau POST. L’archive ne dépend pas du succès Telegram. Date serveur seulement si attestée ; sinon garder `published_at` absent et `confirmed_at` explicite comme approximation opérationnelle pour le rappel. Si le commit échoue, ne pas annoncer une persistance réussie ni renvoyer : maintenir le blocage et réconcilier. Réappliquer localement le reçu encore détenu peut réparer l’écriture, sans appel créateur ; après sa perte, traiter l’envoi comme incertain.
7. Sur rejet définitif et documenté, enregistrer l’échec ; une nouvelle tentative après correction requiert une nouvelle autorisation finale et ne crée pas un second brouillon pour contourner l’intention existante.
8. Sur timeout après départ possible, réponse ambiguë, erreur serveur susceptible d’avoir suivi une création, ou crash après envoi avant écriture du reçu : état `UNKNOWN_OUTCOME` et verrou du compte.
9. Résoudre à partir de preuves officielles si le scope de lecture est effectivement disponible, sinon demander à l’utilisateur de consulter son profil. Une absence observée immédiatement ne suffit pas : aucune relance tant que le doute subsiste. Si une non-publication est confirmée après vérification, nouvelle autorisation obligatoire.

**Limite explicite :** sans transaction distribuée ni idempotence garantie par LinkedIn, « exactement une fois » n’est pas démontrable lors de toutes les pannes. La priorité est de ne pas répéter un envoi incertain, au prix d’un blocage à résoudre humainement. Aucune propriété de déduplication serveur non documentée n’est supposée.

Les opérations sans effet de publication peuvent réessayer avec backoff et `Retry-After`, dans un plafond. Le `POST` créateur n’utilise jamais une politique générique de retry HTTP. Au redémarrage, tout envoi interrompu devient incertain, pas « à rejouer ».

## 7. Confidentialité, conservation et sécurité

### Durées internes proposées, à valider

| Donnée | Conservation |
|---|---|
| Paramètres et préférences acceptées | Jusqu’à modification, révocation ou arrêt du service |
| Archive textuelle, versions et provenances | Durablement tant que l’usage et les droits le permettent, avec suppression demandée/échéance par source ; aucun plafond de trois posts |
| Profil descriptif et index | Tant que leurs sources/usages sont autorisés ; invalidation à chaque changement pertinent, effacement des dérivés expirés |
| Lots d’import en attente | Proposition maximum 7 jours, uniquement si rétention déjà permise ; échéance plus courte prioritaire, sinon pas de persistance |
| Lots terminés | Métadonnées minimales de bilan/provenance autorisées ; pas de doublon durable des textes bruts du lot |
| Brouillons actifs et leurs sources/révisions | 30 jours après dernière activité ; prévenir avant expiration ; pas de prolongation silencieuse infinie |
| Brouillons publiés ou abandonnés | Détails de préparation 30 jours ; texte publié conservé séparément dans l’archive autorisée |
| Images binaires | RAM pendant le traitement/brouillon actif, libérée à la fin ou expiration ; aucun fichier applicatif ni sauvegarde |
| Inbox : texte brut des messages | Supprimé après traitement réussi, délai maximum 7 jours si traitement bloqué ; puis erreur explicite |
| Clés de déduplication Telegram, logs expurgés | 7 jours ; high-water mark Telegram conservé séparément dans les paramètres |
| Métadonnées d’approbation finale et registre de publication | Tant que le service est actif, uniquement identifiants, empreintes, dates et état nécessaires à l’anti-doublon |
| Envoi incertain | Pas de purge automatique avant résolution ; minimiser le contenu conservé mais préserver les éléments nécessaires |
| Compteurs de quota | Fenêtre active et précédente uniquement ; adapter au reset réel du fournisseur |
| Sauvegardes privées | Rotation maximale proposée de 30 jours ; expliquer le délai de disparition des données supprimées |

Ce tableau ne constitue pas une autorisation universelle de stockage. **Toute restriction applicable plus stricte prime**, y compris sur un cas d’envoi incertain ou une trace anti-doublon. Séparer originaux utilisateur indépendants, textes créés localement, collecte Apify et données des autres APIs/outils. Chaque champ/observation porte origine, politique vérifiée, date de revue, usages/destinations et échéance ; inconnue signifie refus de l’opération concernée.

Les Data Storage Requirements limitent notamment à 48 h l’activité sociale des membres reçue par les **Marketing APIs LinkedIn**, pas tous les originaux LinkedIn ni toute collecte Apify. Ils distinguent les données fournies indépendamment. Copies, extraits, profils, index FTS, empreintes soumises aux règles et sauvegardes ne prolongent pas une durée. L’exception de rétention de certains identifiants ne permet pas de garder le texte associé. Le consentement utilisateur ne neutralise pas les interdictions fournisseur. Voir LI-12/13 dans API_INTEGRATIONS.md.

Ne pas collecter si la suppression effective dans le délai et les restrictions d’usage ne peuvent pas être garanties, notamment dans SQLite/WAL et sauvegardes. Au socle, lecture Marketing API désactivée et sources à durée incompatible exclues de l’archive durable. Une restauration doit appliquer les échéances et décisions d’effacement avant toute consultation, indexation ou transfert ; si l’effacement des sauvegardes requis n’est pas réalisable, ne pas accepter la source.

Un effacement requis ou demandé retire texte, anciennes versions, index, profil et copies concernées ; conserver seulement une trace minimale si elle est elle-même autorisée. « Pas de suppression silencieuse » interdit les pertes implicites par synchronisation, pas les obligations d’effacement. Les obligations tunisiennes et transferts internationaux restent à vérifier pour le traitement réel ; un DPA/SCC européen n’est pas une preuve suffisante de conformité en Tunisie.

L’effacement local n’efface ni le chat Telegram, ni un post LinkedIn, ni d’éventuelles copies chez un fournisseur IA. Ne pas annoncer un effacement sécurisé immédiat des octets SQLite/WAL : les procédures de maintenance et de rotation des sauvegardes devront le prendre en compte.

### Frontières de confiance

- Identifiants numériques Telegram autorisés par liste locale ; seul chat privé. `/start` ne suffit pas à rendre un utilisateur propriétaire.
- Messages, fichiers et sorties LLM sont non fiables. Validation de schéma, tailles et types aux frontières ; les actions sensibles utilisent un chemin déterministe.
- Extraction web : HTTP(S) uniquement, préférence HTTPS ; refuser réseau privé, localhost, link-local et métadonnées cloud ; vérifier DNS et chaque redirection, empêcher DNS rebinding, borner téléchargements/décompression/délais. Aucun rendu JavaScript arbitraire au MVP.
- Ne pas envoyer les jetons d’une API à une URL de téléchargement reçue sans vérifier le protocole de cette API et son domaine de destination ; ne pas journaliser les URLs signées LinkedIn.
- OAuth : `state` aléatoire à usage unique, redirection enregistrée exacte, propriétaire lié à la session ; validation de signature/issuer/audience/expiration/nonce si ID token utilisé.
- Les clés du LLM/recherche ne disposent pas de privilèges LinkedIn. Les fonctions rédaction/recherche ne reçoivent aucun secret de publication.
- Chiffrement du disque/sauvegardes selon l’hôte ; un administrateur du PC ami peut néanmoins accéder aux processus/secrets. L’isolation de compte n’équivaut pas à une confidentialité face à l’administrateur.
- Aperçus Telegram : échapper la syntaxe de formatage, présenter le texte réel, vérifier la limite de messages/boutons ; ne jamais tronquer discrètement un post.

## 8. Hébergement et exploitation

### Option de départ recommandée

PC déjà disponible et administré avec accord de son propriétaire. Un compte système dédié, un gestionnaire de service adapté au système, un stockage local privé et une sauvegarde chiffrée sur un emplacement existant suffisent. Un seul consommateur Telegram et un seul worker de publication sont actifs.

Long polling Telegram : connexions sortantes, pas de domaine ni webhook public nécessaire. Cela **ne résout pas** le callback OAuth LinkedIn : avant développement, vérifier une redirection autorisée et accessible au navigateur de l’utilisateur. Une configuration locale ponctuelle doit être acceptée par LinkedIn ; sinon prévoir un callback HTTPS temporaire sûr sur l’hôte retenu, sans dépendre d’un tunnel payant ou non vérifié. Aucun mode OAuth de périphérique n’est supposé disponible.

Oracle Always Free est une alternative conditionnelle : éligibilité, compte, région, capacité réelle, quotas de disque/réseau et risque de récupération d’instance inactive doivent être validés. Aucune architecture ne doit dépendre d’une VM gratuite non encore obtenue.

### Exploitation minimale

- Statut explicite des capacités, connexion, quotas et rappels dans Telegram ; aucun secret affiché.
- Journal structuré expurgé : identifiant d’événement, brouillon, fournisseur, durée, catégorie d’erreur ; pas de prompts complets par défaut.
- Sauvegarde SQLite cohérente, pas une simple copie du fichier principal pendant des écritures WAL ; restauration testée.
- **Après restauration d’une sauvegarde : mode publication bloquée**, vérification des publications intervenues depuis la sauvegarde et autorisations finales révoquées avant réactivation. Cela évite qu’un registre ancien provoque des doublons.
- Mise à jour planifiée des dépendances et des versions LinkedIn ; pas de mise à jour automatique non testée du protocole de publication.
- Procédure d’arrêt : suspendre nouvelles tâches, terminer ou marquer les envois incertains, sauvegarder. Jamais deux hôtes actifs lors d’une migration.
- Aucun SLA 24 h/24 n’est promis sur portable ou offre gratuite.

## 9. Évolution justifiée seulement par un besoin mesuré

Ajouter n8n uniquement si des workflows visuels apportent une valeur concrète ; remplacer SQLite si plusieurs auteurs/instances doivent écrire concurremment ; ajouter une queue externe uniquement si les tâches dépassent réellement la capacité du processus. Ces changements ne doivent pas modifier le contrat des validations ni ouvrir un second chemin de publication.

Références : [décisions](ARCHITECTURE_DECISIONS.md), [API et preuves](API_INTEGRATIONS.md), [limites des services](FREE_SERVICES_BENCHMARK.md), [tests](TEST_STRATEGY.md).
