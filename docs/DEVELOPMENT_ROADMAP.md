# Ordre de développement et portes de validation

Date : 13 novembre 2026, Mission 0.5. **Socle validé (Python, SQLite central, Telegram, Tunisie/`Africa/Tunis`, API officielle, 0 €, validations séparées, archive textuelle sans fichiers images).** Les phases ci-dessous sont indépendamment livrables ; aucune estimation de délai n’est un engagement. Aucun accès fournisseur n’est présumé.

## Principes

- Distinguer autorisation de coder, de configurer un compte et d’effectuer une action externe. Chaque test réel (surtout publication/upload) exige une autorisation séparée sur le contenu exact.
- Sécurité d’état et tests simulés avant tout appel de publication réel ; une preuve réelle s’obtient en sortie de phase, jamais comme prérequis circulaire.
- L’archive, l’import générique et le profil local ne dépendent ni d’Apify, ni du LLM, ni de l’accès publication : ils peuvent être livrés et testés avec des originaux autorisés et des fixtures.
- Si un gate échoue, conserver les fonctions non concernées et demander une décision explicite ; ne pas déclarer l’objectif complet atteint.
- Aucune bascule payante, aucun contournement LinkedIn, aucune persistance sans droits vérifiés.

## Phase 0.5 — Spécification consolidée (documentaire)

Livrables : les neuf documents alignés (archive centrale, import indépendant, profil descriptif + règles confirmées, retrieval borné, rétention par origine, images sans archive binaire), décisions validées vs proposées, sources datées.

**Non fait :** code applicatif, dépendances, comptes, tokens, collecte, publication, audit du skill exact (non fourni).

**Sortie :** l’utilisateur a autorisé le démarrage de l’implémentation le 13 novembre 2026 (dépôt GitHub créé, documentation poussée). Les modalités restantes restent à confirmer ; chaque action externe exige une autorisation distincte.

## Phase 1 — Décisions et vérifications d’accès non publiantes

**Dépendances :** autorisation utilisateur ; aucune action externe sans accord distinct.

- Hôte, coûts indirects, interruptions ; consentement par usage/destination (Telegram inclus) ; paramètres de rétention, retrieval, rappels, RAM images.
- Application LinkedIn : produits, scopes visibles, association de Page si requise, callback OAuth réellement utilisable ; identité et scopes vérifiés sans publier ni téléverser.
- Fournisseurs : offre/pays/modèle/quota/ZDR et absence de facturation automatique ; Tavily sans PAYG ; Telegram configuré avec accord.
- Skill Apify exact : recevoir fichiers/instructions/dépendances/Actors/I/O anonymisées ; audit documentaire des accès, coûts, droits de collecte/conservation/transfert ; aucune exécution, original inchangé.
- Qualifier documentairement `/rest/posts`, la version supportée et le parcours image (restriction GET) ; aucun test de création ici.

**Gate G1 :** aucune incompatibilité connue avec 0 €, hôte et données acceptés, chemin officiel plausible, droits d’import définis par origine. Tout test non effectué reste explicitement à effectuer. Si blocage publication : décider un mode préparation sans publication, pas un objectif complet atteint.

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

**Dépendances :** G3 + audit du skill exact terminé + droits vérifiés + accord utilisateur. Traduire sa sortie vers le contrat d’import générique ; aucune modification du skill original ; coûts Apify bornés et mesurés avant usage ; si l’audit échoue, la phase 3 reste livrée.

## Phase 4 — Profil descriptif et retrieval borné (local)

**Dépendances :** G3. LLM non requis pour le calcul local et les tests.

- `style_profile` persistant borné (≤4 000 caractères proposés), références versions/périodes/couverture/confiance ; textes assistant étiquetés ; aucune règle normative implicite.
- `History.query` : filtres indexés + FTS5 si disponible (sinon repli borné), ≤6 posts/12 000 caractères proposés ; règles confirmées séparées non tronquées.
- Invalidation/recalcul après ajout, version, suppression, changement de droits ; dérivés héritant des restrictions ; vérification des droits avant chaque destination.
- Alertes locales de répétition thématique/textuelle, explicables, non bloquantes.

**Gate G4 (tests locaux) :** invariants MEM/RET passants ; profil recalculé après effacement de source ; aucun dérivé interdit exporté ; budget de retrieval respecté ; FTS5 absent ⇒ repli fonctionnel.

**Livrable :** sélection d’exemples pertinents et profil à jour, sans génération LLM.

## Phase 5 — Recherche web et rédaction

**Dépendances :** G4 + fournisseur LLM/recherche qualifié (conditions, pays, quotas, ZDR, consentement).

- SearchProvider Tavily basic, réserve de quota, extraction HTTP sécurisée (SSRF, tailles, délais) ; dossier multi-source daté, contradictions et manques visibles.
- LLMProvider du modèle retenu ; prompts bornés avec profil + échantillon autorisé ; français naturel, aucun fait personnel inventé, aucune promesse future.
- Corrections ciblées avec différences visibles ; changement factuel ⇒ revérification ; proposition/confirmation distincte des règles permanentes ; révocation.

**Gate G5 :** recette humaine sur plusieurs sujets/corrections ; sources réellement consultées ; pas d’apprentissage implicite ; pas de facturation ni boucle de recherche illimitée ; droits de transfert vérifiés avant chaque envoi.

**Livrable :** assistant éditorial complet sans publication activée.

## Phase 6 — Publication officielle texte seul

**Dépendances d’entrée :** G2/G5, produits/scopes/identité vérifiés, protocole documentaire cohérent, consentement au test réel. La preuve de création s’obtient en sortie G6.

- Adaptateur officiel uniquement : version explicite, en-têtes, règles d’erreur ; préflight et aperçu final ; publication liée au manifeste exact et à l’autorisation consommée.
- Reçu/URN, `PUBLISHED` + archive exacte en transaction locale ; historique et dernière publication connue actualisés ; notification Telegram séparée et reprenable.
- Reconnexion OAuth, expiration, refus de scope, rate limiting, `UNKNOWN_OUTCOME` et réconciliation ; aucun retry automatique d’envoi incertain.
- Premier test de création réelle ici, contenu validé, protections du socle actives ; refus/échec ⇒ capacité non activée.

**Gate G6 :** un post réel autorisé confirme le parcours sur le bon profil ; pannes simulées complètes ; archive atomique vérifiée ; aucune suppression du post de test sans demande distincte.

## Phase 7 — Images existantes et droits

**Dépendances d’entrée :** G6, sources et prérequis documentaires du parcours image vérifiés. Preuve réelle upload/publication en sortie G7.

- Recherche Commons, provenance/licences/restrictions/crédits ; téléchargement et figement **en RAM** (modalité à valider), empreinte, dimensions/MIME bornés.
- Validation image/absence séparée ; crédit ajouté avant validation texte ; perte du tampon ⇒ nouvel aperçu et approbations image/finale.
- Upload officiel sans GET de statut non autorisé ; gestion des états/erreurs du protocole vérifié ; aucun binaire persisté.
- Test réel image avec consentement spécifique ; pipeline bloqué ⇒ texte seul après nouvelles validations explicites.

**Gate G7 :** preuve d’utilisation du fichier approuvé et de droits documentés ; aucun média non validé ; aucune archive binaire ; aucune API privée. Pexels/Unsplash/génération : extensions ultérieures seulement.

## Phase 8 — Rappels et exploitation

Les rappels peuvent être développés après G2 avec date fournie manuellement, puis branchés sur l’archive (G3) et la publication (G6).

- Créneaux `Africa/Tunis`, jours, pause, inactivité 120 h proposée ; `published_at` accepté jamais `imported_at` ; dates imprécises/futures/conflit clarifiées ; `confirmed_at` seulement en approximation signalée.
- Déduplication quotidienne, fusion des motifs, reprise sans rafale, heure manquante/répétée ; déclaration de publication hors bot.
- Installation sur l’hôte approuvé, service, permissions, sauvegarde chiffrée des seules données autorisées, restauration en publication bloquée + réconciliation ; purges et invalidation des dérivés ; statuts quota/capacité ; rotation des logs.

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
