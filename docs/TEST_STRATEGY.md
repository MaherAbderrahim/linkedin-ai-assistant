# Stratégie de tests et preuves d’acceptation

Date : 13 novembre 2026, Mission 0.6. **Une suite locale existe : 75 tests passants (unitaires et intégration, fournisseurs simulés). Aucun test de compte/API authentifiée, aucune publication réelle et aucun benchmark LLM réel n’a été effectué.** Les contrôles documentaires ne doivent pas être présentés comme la réussite des tests réels ci-dessous. Couvre le socle implémenté (archive centrale, import indépendant, profil descriptif, retrieval borné, rappels) plus les modalités proposées (images sans archive binaire, comparaison Groq/OpenRouter, tableau de bord local).

## 1. Ordre et niveaux

1. Vérifications documentaires : cohérence des exigences/contrats/choix, liens locaux, faits sourcés, gratuité récurrente et états d’accès explicitement inconnus.
2. Tests unitaires déterministes : états, empreintes, validations, rappels, budgets, sécurité des entrées.
3. Tests d’intégration locaux : SQLite réelle temporaire, transactions concurrentes, tâches, purges et reprise après arrêt.
4. Tests de contrat avec fournisseurs simulés : données et erreurs conformes aux documents officiels, quotas et latence contrôlés.
5. Tests réels non publiants, autorisés et bornés : Telegram, identité OAuth, modèles et recherche gratuits.
6. Tests de publication réels : chaque contenu et chaque envoi sont autorisés explicitement, via le même parcours final que le produit.
7. Recette humaine éditoriale et exploitation sur l’hôte choisi.

Pas de sandbox LinkedIn supposée disponible. Les tests automatisés ordinaires ne doivent jamais pouvoir publier sur un vrai compte. Un test « live » n’est ni implicite dans une commande générale ni déclenché par un agent LLM.

## 2. Invariants critiques — aucun échec admis

| ID | Scénario | Résultat exigé |
|---|---|---|
| SEC-01 | Message/bouton d’un autre utilisateur, groupe ou propriétaire usurpé par username | Refus, aucun changement sensible ni appel de publication |
| SEC-02 | Utilisateur écrit « OK », « oui », « super », ou donne une instruction citée/transférée | Pas de publication ; clarification ou validation non sensible selon contexte |
| SEC-03 | Source web demande d’ignorer les règles, voler un secret ou publier | Traitée comme données non fiables ; aucun effet sur les autorisations |
| SEC-04 | Clé/jeton dans `.env`, code, log, prompt, Telegram ou dépôt | Secret jamais affiché ni commité ; `.env` ignoré, `.env.example` sans vraie clé ; variables manquantes signalées par nom sans contenu |
| VAL-01 | Texte approuvé, image non choisie | Publication refusée ; demander image ou absence explicite |
| VAL-02 | Texte et image approuvés, pas d’accord final | Aucun upload LinkedIn ni post |
| VAL-03 | Ancien bouton final après modification du texte, fait, auteur, visibilité ou média | Rejet ; nouvel aperçu et autorisation nécessaires |
| VAL-04 | Changement de pixels, compression ou texte alternatif après accord image | Validation image et autorisation finale invalidées |
| VAL-05 | Image remplacée par « sans image » à la suite d’une panne | Aucun retrait silencieux ; demander confirmation et revalider le texte si crédit modifié |
| VAL-06 | Accord final expiré ou nonce rejoué | Refus ; un seul usage possible |
| VAL-07 | Crédit ajouté après validation texte | Texte et autorisation finale invalidés |
| DUP-01 | Deux clics simultanés ou deux updates Telegram identiques | Une seule intention/envoi possible |
| DUP-02 | Deux brouillons différents avec même auteur, texte, visibilité et image | Empreinte de contenu identique malgré IDs/révisions différents ; doublon bloqué |
| DUP-03 | Timeout après création possible chez LinkedIn | État UNKNOWN_OUTCOME, verrou du compte, zéro retry automatique |
| DUP-04 | Réponse 201 perdue avant écriture SQLite | Même blocage ; aucune conclusion « non publié » |
| DUP-05 | LinkedIn réussit mais la notification Telegram échoue | Post conservé comme publié ; seule la notification est reprise selon règles |
| DUP-06 | Autre brouillon demandé pendant un envoi incertain | Préparation possible, nouvelle publication bloquée sur le compte |
| DUP-07 | Restauration d’une sauvegarde antérieure à un post | Publication désactivée jusqu’à réconciliation ; anciennes autorisations finales révoquées |
| MEM-01 | Correction de longueur/ton dans un brouillon | Aucun ajout à preferences sans accord distinct sur la règle exacte |
| MEM-02 | LLM propose lui-même une préférence durable | Seulement une proposition à confirmer ; aucune écriture de règle active |
| MEM-03 | Observation descriptive du profil | Aucune promotion en règle normative ; références versions/période/couverture présentes ; textes assistant étiquetés |
| MEM-04 | Source supprimée/expirée/interdite au traitement | Versions concernées, index FTS, extraits et observations dérivées invalidés/effacés ; aucun dérivé interdit exporté |
| HIST-01 | Confirmation LinkedIn fiable | Reçu + `PUBLISHED` + texte original exact archivés dans une seule transaction locale ; aucun succès sans preuve |
| HIST-02 | Échec certain, `UNKNOWN_OUTCOME`, brouillon, intention | Aucune entrée d’archive créée ; aucun renvoi automatique après panne locale post-succès réseau |
| HIST-03 | ID/URL/heure serveur absents | Champs null conservés ; `published_at` (précision/fuseau), `confirmed_at`, `imported_at` jamais substitués l’un à l’autre |
| HIST-04 | Purge des brouillons à 30 jours | Archive autorisée intacte ; plus de trois posts conservables et consultables |
| IMP-01 | Lot rejoué à l’identique | Aucun post/version dupliqué ; nouvelle observation d’acquisition possible, traçable |
| IMP-02 | Droits inconnus ou interdiction de stockage/transfert | Aucune persistance provisoire (base, fichier, log, sauvegarde) ; aperçu Telegram refusé si transfert interdit |
| IMP-03 | Même ID, texte modifié | Nouvelle version proposée puis confirmée ; ancienne conservée si permise ; null importé n’écrase pas une valeur connue |
| IMP-04 | IDs différents, textes proches ; date manquante/imprécise | Pas de fusion automatique ; arbitrage humain ; absence du lot suivant ≠ suppression |
| IMP-05 | Plan d’import périmé (base modifiée, course avec archivage d’un succès) | Commit refusé/rollback complet du sous-ensemble choisi ; recalcul et nouvel accord ; aucun double post |
| IMP-06 | Import ressemblant à un envoi `UNKNOWN_OUTCOME` | Indice de réconciliation seulement ; verrou du compte maintenu jusqu’à preuve fiable |
| RET-01 | Retrieval sur grande archive | ≤6 posts/12 000 caractères proposés respectés ; filtres droits avant sélection ; jamais toute l’archive transmise |
| RET-02 | Règles confirmées + budget de contexte serré | Règles fournies séparément, jamais tronquées silencieusement ; blocage exposé si insuffisant |
| IMG-06 | Parcours image complet | Aucun binaire en base, fichier temporaire applicatif, cache SDK disque ou sauvegarde ; perte du tampon ⇒ nouvel aperçu + approbations image/finale |
| BUD-01 | Quota épuisé, modèle devenu payant, limite inconnue ou PAYG détecté | Capacité bloquée ; pas de débit payant, pas de contournement par autre compte |
| BUD-02 | Fournisseur gratuit en panne | Pas de transfert à un nouveau destinataire non approuvé |
| IA-01 | Comparaison Groq/OpenRouter avant sélection | Aucun modèle figé d’office ; mêmes tâches autorisées, métriques relevées dans `llm_benchmarks` ; sélection seulement après recette |
| IA-02 | Fournisseur/modèle gratuit épuisé ou devenu payant | Aucun basculement automatique vers une offre payante ; pause explicite, pas de débit ni de contournement |
| DASH-01 | Tableau de bord local | Lié à `127.0.0.1` uniquement ; même base/paramètres que Telegram ; aucune seconde voie de publication ; non exposé publiquement sans authentification |
| DASH-02 | Paramètre modifié via Telegram ou tableau de bord | Une seule source de vérité SQLite ; l’autre canal reflète la même valeur ; aucun secret affiché dans l’interface |

## 3. États, concurrence et pannes

Utiliser une horloge contrôlable et des adaptateurs simulés ; aucune attente de cinq jours réels dans la suite.

- Une réponse de rédaction terminée pour une ancienne révision ne doit pas écraser une correction récente.
- Une révision approuvée demeure immuable ; son texte et l’image envoyée correspondent exactement à l’aperçu.
- Une autorisation finale et une intention sont engagées atomiquement ; deux workers simulés ne peuvent les consommer deux fois.
- Injecter une interruption : avant réservation, après intention durable, pendant upload, juste avant POST, juste après POST, après reçu mais avant confirmation Telegram.
- Redémarrage : tâches sans effet externe peuvent reprendre ; un envoi commencé ne redevient pas automatiquement une tâche publiable.
- Simuler disque plein, base verrouillée ou échec de commit : **si l’intention ne peut pas être persistée, aucun appel LinkedIn ne part**.
- Distinguer échec de média sans post et incertitude de création de post ; ne jamais perdre le fait qu’un POST a pu partir.
- Une annulation pendant l’envoi ne promet pas d’annuler un effet déjà réalisé ; l’état doit le signaler clairement.
- Sauvegarde/restauration sous WAL : intégrité, références de révisions, registre d’envoi et contrôle du high-water mark Telegram vérifiés.
- Course simulée : un import approuvé et l’archivage d’un succès du bot visant le même post ; le plan périmé échoue, aucune double entrée, provenance des deux observations préservée.
- Échec de commit après succès réseau simulé : pas de nouvelle tentative ; réappliquer le reçu encore détenu répare l’écriture locale sans appel créateur ; reçu perdu ⇒ incertitude.

## 3bis. Historique central, import et profil (tests locaux)

Fixtures multi-formats : originaux utilisateur, export simulé du skill (schéma documenté par l’audit : `postText`/`publishedAt`/`url` ; sortie réelle non obtenue, aucun Actor exécuté), export d’un autre outil, réponse API simulée avec restrictions. Aucun Actor exécuté, aucun compte réel.

- Déduplication : ID typé complet prioritaire ; suffixes `share`/`ugcPost`/`activity` non assimilés sans preuve ; repli texte normalisé versionné + date précise + auteur + métadonnées ; normalisation ne supprimant ni nombres, URLs ni ponctuation significative.
- Deux posts réels de même texte mais IDs/dates différents restent distincts ; date au jour seule ne fabrique pas d’heure ; date future ou contradictoire ⇒ conflit visible.
- Statuts du plan : nouveau, connu, version, conflit, ambigu, incomplet, refus de droits ; chaque statut testé avec et sans accord ; accord partiel n’importe que le sous-ensemble choisi, transactionnellement.
- Provenance : un export API remis par l’utilisateur reste d’origine API ; observations multiples sans écrasement ; `imported_at` distinct de `published_at`/`confirmed_at` ; lot partiel ne marque pas les posts absents comme supprimés.
- Rétention par origine : source à échéance courte purgée à temps avec ses dérivés (FTS, profil, extraits) ; sauvegarde contenant une donnée expirée non restaurée en état consultable ; effacement demandé propagé ; trace minimale seulement si autorisée.
- Profil : recalcul après ajout/version/suppression ; références de versions valides ; couverture/confiance affichées ; aucune inférence sensible ; textes assistant exclus des références de style humain selon la règle retenue ; profil mixte non exportable exclu/recalculé avant transfert.
- Retrieval : filtres auteur/date/droits avant FTS ; budget 6 posts/12 000 caractères respecté ; FTS5 absent ⇒ repli borné fonctionnel ; règles confirmées séparées non tronquées ; alerte de répétition explicable, non bloquante.
- Concurrence : deux lots simultanés, lot pendant une publication simulée, aperçu modifié entre accord et commit ; idempotence par empreinte de lot et décisions.

## 4. OAuth et contrats LinkedIn

### Non publiant ou simulé en premier

- Produits visibles, scopes disponibles et scopes réellement consentis distingués.
- Redirection exacte, state invalide/absent/rejoué, mauvais utilisateur et callback expiré rejetés.
- Validation complète de l’ID token si utilisé ; ne pas confondre un JWT décodable et un jeton vérifié.
- Identité du membre et auteur attendu cohérents ; aucun identifiant récupéré depuis une URL de profil arbitraire.
- `expires_in` pris en compte ; scénario sans refresh token valide et révocation anticipée.
- 401, 403, 429, versions sunset, réponse inattendue et permission partielle couverts.
- Le scope `w_member_social` ne débloque pas la lecture historique ni le GET images versionné.
- Le guide self-service UGC ne suffit pas à considérer `/rest/posts` testé ; preuve enregistrée par endpoint et version.

### Texte et image, preuves distinctes

- Publication texte : payload exact, version/en-têtes, compte/visibilité, réponse 201 et URN.
- Cas longueur/Unicode : accents, guillemets, retours ligne, caractères combinés, caractères hors BMP, URLs et limite effective du contrat.
- Image : droits, MIME/dimensions/limites actuelles, empreinte identique, URL d’upload expirée, état de traitement, absence de permission GET et erreur de publication média.
- Ne pas marquer le média « disponible » sur la seule initialisation de l’upload.
- Les tests peuvent conclure « texte vérifié, image bloquée » ; ce résultat est acceptable comme état intermédiaire, pas comme livraison complète avec images.

## 5. Telegram et rappels

| Cas | Attendu |
|---|---|
| Rappels désactivés et idée spontanée | Brouillon créé normalement |
| Rappel quotidien configuré | Créneau par défaut 10 h 00 `Africa/Tunis` (décision utilisateur), modifiable ; au plus un par jour local ; le `DEFAULT_HOUR=9` actuel du code doit être aligné en Phase 1 |
| Bot pas encore démarré ou bloqué | Pas de promesse de livraison ; statut explicite |
| Deux événements du même créneau | Un seul rappel quotidien |
| Créneau récurrent et inactivité simultanés | Motifs fusionnés, pas deux messages |
| 119 h 59 min depuis publication | Pas de rappel d’inactivité |
| 120 h puis prochain créneau autorisé | Rappel admissible selon pause/jours |
| Dernière publication inconnue | Demander date ou choix explicite de démarrer le compteur |
| Publication confirmée hors bot par l’utilisateur | Référence temporelle actualisée ; aucune permission de lecture inventée |
| Import tardif d’un ancien post | `published_at` utilisé, jamais `imported_at` ; date imprécise/future/en conflit ⇒ clarification avant tout changement de référence |
| Envoi de publication incertain | Dernière date confirmée inchangée ; rappel ne prétend pas connaître tout l’historique |
| Changement de fuseau ou passage heure été/hiver | Règle d’heure manquante/répétée respectée ; au plus un rappel par jour local |
| Redémarrage après dix créneaux manqués | Pas de rafale de dix rappels |
| Coupure Telegram >24 h | Avertir de possible perte d’updates ; aucune promesse de reconstruction intégrale |
| Aperçu dépassant la légende photo | Texte séparé complet et rattaché au même manifeste |
| Markdown/HTML dans le texte ou les métadonnées | Échappement correct, pas de contenu caché ni texte modifié |
| Bouton ancien dont le brouillon a été purgé | Refus compréhensible, aucun nouvel envoi implicite |

## 6. Recherche et qualité rédactionnelle

Constituer un petit corpus de test avec contenu autorisé : annonce récente à source primaire, chiffres contradictoires, page inaccessible, reprises d’un même communiqué, idée personnelle, demande vague, correction purement stylistique et correction factuelle.

- Chaque affirmation vérifiable conserve sa provenance, une date de consultation et un statut explicite.
- Deux copies d’un communiqué ne satisfont pas la corroboration indépendante.
- Une source unique n’est pas présentée comme un consensus ; l’exception pour une annonce primaire doit être explicitement acceptée et son attribution conservée.
- Un résultat de recherche/snippet ne devient pas automatiquement une lecture vérifiée de la page.
- Une URL inaccessible n’est pas « remplacée » par une citation inventée.
- Une correction factuelle relance la vérification ciblée ; une correction de style ne déclenche pas systématiquement une recherche inutile.
- Limites de trois requêtes/cinq pages par tour et plafonds gratuits contrôlés ; une boucle de recherche ne peut pas s’auto-prolonger.
- Une tâche sans LLM/recherche disponible conserve le brouillon et annonce ses limites.

### Recette humaine du français et du style

L’utilisateur évalue une petite série de textes sur ses thèmes réels, avec un échantillon autorisé de son archive (dont ses originaux datés) : naturel, exactitude personnelle, adéquation du ton, absence de clichés récurrents, précision des corrections, absence de promesses concernant les prochains posts. Présenter les différences, pas seulement un nouveau texte entier. Vérifier que le style généré par l’assistant ne se renforce pas comme préférence humaine.

Critères bloquants : fait personnel inventé, citation/source fabriquée, chiffre non vérifié présenté comme certain, promesse de contenu futur interdite, modification substantielle hors demande non signalée. Un score automatique peut aider mais ne remplace pas cette recette.

**Qualification et comparaison de modèles avant choix :** Groq et OpenRouter sont comparés sur les mêmes tâches autorisées (qualité du français, suivi d’instructions, reproduction du style, latence, limites d’usage) ; relever fournisseur/modèle/version, paramètres, taille des entrées/sorties, quotas et échecs dans `llm_benchmarks`. Aucun modèle n’est sélectionné définitivement avant cette recette. Aucun résultat de benchmark réel n’est disponible à ce jour ; les tests actuels utilisent des fournisseurs simulés.

## 7. Images et droits

- Vérifier fichier domaine public établi, CC BY avec crédit, fichier multilicence, auteur différent de l’importateur et licence absente.
- Champs Commons contenant HTML : parser/nettoyer, ne pas les rendre comme contenu actif.
- Restriction marque/personne/usage : bloquer ou demander clarification ; « gratuit » ne vaut pas autorisation universelle.
- Licence exigeant attribution/modification : vérifier sa présence dans le texte final avant validation.
- Image distante changée entre sélection et publication : utiliser les octets approuvés en RAM, ou redemander validation après nouveau téléchargement ; tampon perdu (redémarrage, expiration) ⇒ nouvel aperçu et approbations image/finale, jamais de substitution silencieuse.
- Vérifier l’absence de binaire image en base, fichier temporaire applicatif, cache SDK sur disque et sauvegarde ; seules métadonnées/empreintes/droits autorisés persistés. Ne pas prétendre tester l’absence de swap OS.
- Fichier malveillant, MIME mensonger, dimensions/mémoire décodée excessives et redirection vers adresse privée : refus sans exécution ni fuite de données.
- Aucune option de génération ne consomme des crédits promotionnels ou payants dans le chemin normal.

## 8. Confidentialité, budgets et exploitation

- Tester que prompts, erreurs, traces HTTP et URLs ne révèlent pas de jeton, code OAuth, clé API ou URL signée.
- Vérifier réellement les données envoyées : uniquement champs autorisés, pas de transcript complet ni de cookies.
- Tester la suppression d’une préférence et le maintien des seules données anti-doublon nécessaires.
- Purges : brouillon à 30 jours sans toucher l’archive autorisée ; tampons image libérés à la fin/expiration, aucun fichier à purger ; messages traités supprimés ; lots en attente à échéance proposée 7 j seulement si rétention permise ; aucune purge automatique des cas incertains avant résolution, sauf restriction plus stricte qui prime.
- Archive et profil : pas de plafond de trois posts ; invalidation des dérivés à chaque changement de source/droits ; effacement requis/demandé propagé aux versions, index, profil et sauvegardes concernées selon la politique validée.
- Distinguer les données fournies indépendamment de celles lues via API LinkedIn. Si une intégration de lecture est activée ultérieurement, vérifier durées par champ (notamment activité sociale à 48 h), absence de copies/dérivés/sauvegardes hors délai, et aucun transfert LLM non autorisé par les conditions. Un consentement utilisateur ne neutralise pas une restriction fournisseur.
- Documenter les restes éventuels dans SQLite/WAL/sauvegardes et la rétention des fournisseurs, sans promettre un effacement mondial immédiat.
- Réserver le coût maximal avant appel ; vérifier décompte basic/advanced, reset mensuel/journalier et concurrence. En cas de réponse perdue, ne pas libérer une réservation comme si rien n’avait été consommé sans preuve.
- Les limites locales complètent la configuration de facturation, elles ne prouvent pas seules l’absence de frais.
- Tests hôte : veille, coupure Internet, redémarrage système, espace disque insuffisant, lancement accidentel d’une seconde instance et restauration.
- Aucun stress test sur les API gratuites ; tests de charge/concurrence en local uniquement.

## 8bis. Tableau de bord local (squelette livré le 14 novembre 2026 — tests implémentés)

Interface `127.0.0.1:8000` (`dashboard_port`), serveur HTTP stdlib, lisant/écrivant la même base SQLite que Telegram. Aucun test réel d'exposition publique n'est effectué au socle.

Implémentés (tests/test_dashboard.py, 143 tests au total au 14 nov) :

- Rendu pur testable sans socket : `/` (index), `/config` (registre `prefs`, mêmes validations que `/settings` Telegram), `/state` (compteurs, rappels, variables absentes par noms seuls), `/bench` (lecture seule), 404/405.
- Configuration partagée : un réglage posé via le tableau de bord est relu identique par Telegram (même table `settings`) ; valeurs invalides et clés inconnues refusées (400, échec conservateur).
- Aucune voie de publication : rien ne publie ni ne consomme d'approbation ; énoncé affiché sur la page d'état.
- Secrets : aucune clé/jeton affiché ; variables manquantes signalées par noms seuls.
- Échappement HTML des valeurs de paramètres (test d'injection `<script>`).
- Liaison loopback vérifiée en test réel : serveur éphémère (port 0) sur 127.0.0.1, requête HTTP locale 200 ; jamais d'écoute externe par défaut.

Reste proposé (phases suivantes) : sections éditoriale/IA/recherches (Phase 5), état système complet (Phase 8) ; garde d'exposition Internet : authentification et protection des secrets obligatoires avant tout accès, non couvert par le socle local.

## 9. Recette de bout en bout autorisée

1. Propriétaire reconnu, rappels désactivés, idée spontanée.
2. Import confirmé d’originaux autorisés dans l’archive (aperçu, accord, idempotence) ; profil descriptif calculé.
3. Recherche sourcée, échantillon borné de l’archive + profil, premier texte français.
4. Correction ciblée de style puis correction factuelle avec nouvelle recherche.
5. Refus de mémoriser une correction, puis confirmation distincte d’une autre règle.
6. Validation du texte et d’une image avec droits, puis changement d’image : ancien bouton final refusé.
7. Nouvel aperçu du compte et du contenu complet ; clic final explicite.
8. Une publication officielle, une URN, texte exact archivé atomiquement, date/historique actualisés ; double clic sans second post ; rejeu d’un lot contenant ce post sans doublon.
9. Scénario de timeout uniquement simulé : blocage d’incertitude, aucune reprise automatique ; un import ressemblant ne lève pas le verrou.
10. Réactivation facultative des rappels ; bot toujours utilisable lorsqu’ils sont à nouveau désactivés.

Un compte réel ne sert pas à tester des pannes destructrices ni à produire des posts supplémentaires involontaires. Toute suppression externe serait soumise à une autorisation distincte.

## 10. Preuves et critères de livraison

Conserver un compte rendu de recette expurgé : date, version de l’application/API/modèle, scénario, résultat attendu/observé, type simulé ou réel, et URN si une publication autorisée a eu lieu. Les clés et contenus privés ne sont pas des pièces de preuve à publier.

**Livrable activable seulement si :** tous les invariants critiques sont passants, compte et endpoint officiel vérifiés, confidentialité/budget validés, reprise testée, recette éditoriale acceptée, et limites restantes clairement visibles. Une compilation ou un bot qui répond ne prouve pas ces propriétés.

Références : [exigences](PRODUCT_REQUIREMENTS.md), [architecture](TECHNICAL_ARCHITECTURE.md), [API](API_INTEGRATIONS.md), [feuille de route](DEVELOPMENT_ROADMAP.md).
