# Exigences produit — LinkedIn AI Assistant

Date : 13 novembre 2026. **Mission 0.5 documentaire.** Implémentation autorisée par l’utilisateur le 13 novembre 2026 ; aucune intégration testée ; aucune action sur un compte/service sans autorisation distincte.

**Validé par l’utilisateur :** Python + SQLite, modularité et fournisseurs interchangeables, Telegram comme interface principale, n8n facultatif, utilisation en Tunisie avec fuseau `Africa/Tunis`, publication par API officielle LinkedIn, budget 0 € sans paiement obligatoire ni fallback payant, validations texte et image distinctes puis autorisation finale, archive centrale durable de tous les textes dont la rétention est permise et profil compact persistant, sans archive de fichiers images.

**Encore proposés ou à vérifier :** modalités techniques détaillées, hôte, fournisseurs/modèles, accès et scopes réels, conditions/consentements par usage et destination, paramètres de rétention, d’import, de retrieval et de rappels. Ces modalités restent à confirmer ; leur validation ne vaut pas autorisation d’action externe.

## 1. Objectif et périmètre

Aider une seule personne à préparer puis publier sur son profil personnel LinkedIn, depuis une conversation privée Telegram. Favoriser la qualité, la vérifiabilité et le contrôle éditorial plutôt que le volume. Le fonctionnement normal ne doit exiger ni paiement, ni abonnement, ni crédit acheté, ni modèle local.

Les quotas gratuits ne constituent pas une garantie de disponibilité ou de gratuité perpétuelle. Si une capacité gratuite disparaît ou atteint son quota, le traitement concerné s’arrête proprement ; aucun achat automatique n’est permis. Le matériel, Internet et l’électricité de l’hôte ne sont pas physiquement gratuits : leur prise en charge doit être acceptée avant de qualifier la solution de « 0 € supplémentaire ».

### Inclus

- Idées spontanées, suggestions de sujets récents, recherche web sourcée, rédaction et corrections ciblées en français.
- Archive centrale durable de **tous les textes dont la rétention est permise** : source A, publications du bot confirmées ; source B, imports autorisés indépendants du fournisseur. Trois publications récentes constituent un échantillon de consultation, pas une limite de stockage.
- Profil de style compact persistant, descriptif et recalculable, distinct des règles normatives confirmées ; sélection bornée de textes pertinents, jamais toute l’archive envoyée à chaque génération.
- Images existantes, droits vérifiés, validation séparée, aucune archive de fichiers images ; texte seul possible uniquement après choix explicite.
- Rappels facultatifs en `Africa/Tunis` ; publication immédiate après autorisation finale via API officielle.
- Reprise après redémarrage, brouillons/révisions, historique opérationnel minimal, archive autorisée distincte, prévention des doublons et visibilité des erreurs. Un tampon image perdu nécessite un nouvel aperçu et de nouvelles approbations image/finale.

### Exclus du premier produit

Multi-utilisateur, pages d’entreprise, réponses/commentaires/likes automatisés, prospection, scraping LinkedIn intégré, planification de publications sans présence de l’utilisateur, analytics d’engagement, vidéo, carrousel, interface web permanente, base vectorielle, archive binaire d’images, agent autonome disposant des jetons de publication. Un import externe éventuel n’autorise ni collecte non conforme ni exécution/modification du skill Apify. La génération d’images reste une extension facultative désactivée tant qu’une option compatible n’est pas démontrée.

## 2. Parcours de référence

1. L’utilisateur démarre le bot, confirme son identité Telegram autorisée, choisit ses sujets, sa confidentialité et éventuellement ses rappels.
2. Il propose une idée ou demande des suggestions. Une ambiguïté sur l’intention ou le brouillon concerné provoque une clarification, pas une action externe.
3. Le bot recherche des sources, expose les points vérifiés et les incertitudes, puis rédige avec le profil descriptif persistant, les règles explicitement confirmées et un échantillon borné de textes autorisés de l’archive (récents, thématiques ou par période). Il indique dates, provenance et couverture ; trois récents ne signifient pas les trois derniers LinkedIn si l’historique est incomplet.
4. L’utilisateur demande des changements ciblés. Une modification factuelle entraîne une recherche complémentaire avant nouvelle rédaction.
5. Il valide le texte exact affiché.
6. Il choisit et valide une image avec sa provenance, ses conditions de réutilisation, son crédit et son texte alternatif, ou valide explicitement « sans image ».
7. Le bot affiche le compte auteur, la visibilité, le texte complet et l’image exacte. Le bouton dédié « Publier maintenant » demande une autorisation finale, distincte des deux validations précédentes.
8. L’application publie la version autorisée une seule fois ou expose un état d’échec/incertitude. Elle ne prétend pas avoir publié sans preuve.

L’ordre des validations texte/image peut être inversé. Leur portée reste distincte. Ajouter un crédit d’image au texte nécessite une nouvelle validation du texte.

## 3. Exigences et acceptation

Critères de recette futurs, non exécutés. Les seuils et modalités signalés « proposés » restent à valider ; aucune ligne de ce tableau n’autorise un accès de compte ou une action externe.

| ID | Exigence | Dépendances | Critère d’acceptation |
|---|---|---|---|
| CONV-01 | Conversation privée Telegram, un propriétaire autorisé | Bot API, configuration d’identité | Messages et boutons d’un autre identifiant refusés ; les noms d’utilisateur ne servent pas d’autorisation |
| CONV-02 | Idées à tout moment, indépendamment des rappels | Réception Telegram, brouillons | Rappels désactivés : une idée spontanée démarre un brouillon |
| CONV-03 | Désambiguïsation et corrections en langage naturel | Routeur, contexte de brouillon | « Raccourcis le deuxième paragraphe » ne réécrit pas silencieusement tout le post ; « OK » ne publie pas |
| CONV-04 | Résilience et statut | Persistance, quota | Redémarrer conserve brouillon textuel et statut ; `/statut` expose attente, blocage ou prochaine action ; tampon image perdu = revalidation |
| REM-01 | Fuseau fixé, paramètres de rappel proposés | Horloge `Africa/Tunis`, planificateur | Heure/jours/activation affichés et confirmés avant activation ; ne pas redemander le fuseau validé |
| REM-02 | Seuil proposé de cinq jours | Date acceptée, planificateur | Si 120 h validées : prochain créneau autorisé, au plus 1 rappel/jour local, motifs fusionnés et reprise sans rafale ; `imported_at` ne remet jamais le compteur à zéro |
| REM-03 | Pause sans désactiver le bot | Paramètres indépendants | Désactiver les rappels n’arrête ni les idées ni les corrections ni la publication manuelle |
| REM-04 | Dates fiables et incertitudes visibles | `published_at`, précision/fuseau | Date imprécise/future/en conflit = clarification ; sans heure serveur, `confirmed_at` du bot seulement comme approximation explicitement signalée |
| TOP-01 | Suggestions de sujets récents et pertinents | Recherche web, thèmes utilisateur | Chaque suggestion comporte son intérêt, des sources datées et son niveau d’actualité ; pas de popularité inventée |
| RES-01 | Recherche avant rédaction | SearchProvider, Extractor | Au moins deux sources fiables indépendantes pour une synthèse factuelle, et une source primaire lorsqu’elle existe |
| RES-02 | Faits traçables et limites explicites | Dossier de recherche | Chaque affirmation importante renvoie à une source consultée ; une annonce à source primaire unique est présentée comme telle et exige une exception confirmée |
| RES-03 | Recherche complémentaire | Nouvelle demande/fait | Ajouter un chiffre ou changer un fait invalide la validation texte et relance la vérification ciblée |
| RES-04 | Contenus web non fiables | Extraction sécurisée | Les instructions contenues dans une page ou un fichier ne peuvent pas modifier les règles ni appeler l’API de publication |
| TXT-01 | Français naturel et contenu personnel exact | LLM, profil de style | Pas d’expérience, de qualification, de réussite ou de donnée personnelle inventée ; incertitudes signalées |
| TXT-02 | Style fondé sur archive et profil autorisés | Retrieval borné, profil persistant | Dates/provenances/couverture affichées ; trois récents = échantillon, jamais limite de stockage ni garantie d’exhaustivité LinkedIn |
| TXT-03 | Corrections ciblées, sans promesses futures | Révisions immuables | Différence visible entre versions ; aucune promesse du type « prochainement je vous présenterai… » |
| HIST-01 | Archive centrale durable autorisée | SQLite, droits par origine | Plus de trois textes autorisés restent consultables ; purge proposée des brouillons à 30 j sans suppression de leur copie publiée autorisée |
| HIST-02 | Source A après succès fiable uniquement | Reçu LinkedIn, transaction locale | Texte original exact envoyé + reçu/preuve + succès + archive validés atomiquement en local ; brouillon/intention/`UNKNOWN_OUTCOME` exclus ; panne locale après succès réseau n’autorise aucun renvoi |
| HIST-03 | Identité et temporalité honnêtes | Métadonnées attestées | ID/URL absents restent null ; `published_at` et précision/fuseau distincts de `confirmed_at` et `imported_at`, sans heure/identifiant inventé |
| IMP-01 | Source B indépendante du fournisseur | Contrat d’import, revue des droits | Skill exact examiné avant intégration : fichiers/instructions/dépendances/Actor/I-O anonymisées ; original inchangé, aucun générique exécuté |
| IMP-02 | Import contrôlé et idempotent | Parse borné, aperçu immuable, accord | Droits avant persistance → parse → comparaison → aperçu → accord lot/éléments → transaction ; rejouer le même lot approuvé ne duplique pas les textes/versions |
| IMP-03 | Comparaison prudente | ID LinkedIn typé, métadonnées | Afficher nouveau/connu/version/conflit/ambigu/refus ; suffixes share/ugcPost/activity non assimilés, ambiguïtés soumises à l’humain |
| IMP-04 | Versions et observations traçables | Confirmation, provenance réelle | Même ID + texte changé = nouvelle version confirmée ; null n’écrase pas connu, IDs différents/texte proche non fusionnés, absence d’un lot ≠ suppression ; aucun export API réétiqueté |
| MEM-01 | Règles normatives explicitement confirmées | Confirmation séparée, stockage distinct | « Corrige ce passage » ne crée aucune règle ; présenter le texte exact de la règle durable avant confirmation |
| MEM-02 | Oubli et minimisation | Politique de conservation | Suppression ciblée possible ; pas d’historique intégral de conversation/corpus web ; archive autorisée distincte des données opérationnelles |
| MEM-03 | Profil descriptif compact persistant | Textes/versions autorisés | Observations recalculables avec références versions/périodes/couverture/confiance, sans inférence sensible ; textes assistant identifiés, aucune promotion automatique en règle normative |
| MEM-04 | Restrictions et effacement propagés | Provenance, dépendances des dérivés | Effacement requis/demandé appliqué aux versions concernées, dérivés, index et profil ; pas d’ancien texte illicite conservé au nom du versionnement |
| RET-01 | Rétention et traitements autorisés | Matrice origine/usage/destination | Stockage, analyse, dérivation et transfert vérifiés séparément, Telegram compris ; droits inconnus = aucune persistance provisoire ; conditions plus strictes prioritaires |
| RET-02 | Retrieval borné, paramètres proposés | Filtres SQLite, FTS5 si disponible | Au plus 6 posts / 12 000 caractères cumulés + profil 4 000 caractères si validés ; sélection récente/thématique/par période, jamais toute l’archive ; règles confirmées séparées non tronquées silencieusement |
| IMG-01 | Images existantes prioritaires | ImageProvider, vérification des droits | La fiche de chaque candidate indique auteur, URL de la page source, licence exacte, restrictions, crédit et fichier prévisualisé |
| IMG-02 | Validation indépendante | Empreinte du fichier, approbation | Remplacer, recadrer, recomprimer ou régénérer l’image invalide son approbation et l’autorisation finale |
| IMG-03 | Génération facultative | Fournisseur vérifié, consentement | Le produit fonctionne sans génération et sans crédit ; aucune substitution automatique d’image |
| IMG-04 | Aucune archive binaire | Circuit RAM seule proposé | Aucun fichier image en archive ; proposition sans BLOB/disque temporaire/sauvegarde, seules métadonnées/hash/droits autorisés persistés ; pas de promesse sur swap OS ou suppression chez les services |
| IMG-05 | Perte du tampon sûre | Empreinte, aperçu, approbations | Après perte/redémarrage : refaire aperçu et approbations image/finale, même si l’image est récupérable ; pas de passage silencieux au texte seul |
| PUB-01 | API officielle et permissions vérifiées | OAuth, adaptateur LinkedIn | Compte/scope/endpoint attestés, sinon publication bloquée ; preuve texte distincte de preuve image, `w_member_social` seul ne permet pas le GET versionné du statut d’image |
| PUB-02 | Autorisation finale explicite | Validations texte/image, manifeste | Aucune publication sur rappel, approbation de style, « OK », appel du LLM ou ancien bouton |
| PUB-03 | Anti-doublon | Transaction SQLite, registre d’envoi | Double clic, doublon Telegram et redémarrage ne déclenchent pas deux envois du même brouillon |
| PUB-04 | État incertain visible | Réconciliation explicite | Timeout après envoi possible : verrou du compte et zéro retry automatique ; import/déclaration ne lèvent pas automatiquement `UNKNOWN_OUTCOME` |
| OPS-01 | Dépense nulle par construction | Garde de quota, offres gratuites à vérifier | Quota épuisé ou offre ambiguë : arrêt de la capacité, aucun paiement obligatoire ni fallback payant |
| OPS-02 | Remplacement des fournisseurs | Contrats internes | Un changement de LLM/recherche/import ne modifie pas la logique d’approbation ou la base métier |

## 4. Règles de rappel proposées

- Le fuseau **`Africa/Tunis` est validé**, pas à redemander. Activation, heure et jours restent à choisir ; proposition de laisser les rappels désactivés tant que ces paramètres et le consentement ne sont pas confirmés. Le bot fonctionne indépendamment des rappels.
- Deux motifs proposés : créneau éditorial récurrent et inactivité de cinq jours. Au plus **un rappel par jour local**, motifs fusionnés si nécessaire.
- « Cinq jours » signifie dans la proposition **120 heures écoulées**, puis prochain créneau autorisé ; seuil encore à valider, ni règle déjà acceptée ni limite d’API.
- Référence : dernier **`published_at` accepté**, avec provenance, précision et fuseau, pour une publication confirmée du bot ou un post externe importé/déclaré et validé. **Jamais `imported_at`** : importer aujourd’hui un ancien post ne remet pas l’inactivité à zéro. Brouillon, intention, échec ou `UNKNOWN_OUTCOME` ne comptent pas comme succès.
- Sans heure serveur pour une publication du bot dont le succès est fiable, `confirmed_at` peut servir d’approximation **explicitement signalée**, jamais être présenté comme heure officielle de publication ni écrasé dans `published_at`.
- Date imprécise, future ou contradictoire : clarification humaine avant calcul ; aucune heure fabriquée à partir d’une date au jour et aucune sélection silencieuse entre dates en conflit.
- Sans accès historique exhaustif, les posts externes ne sont pas détectés automatiquement. Import autorisé ou déclaration « j’ai publié le… » peuvent compléter les observations ; le rappel dit « aucune publication connue depuis… ». Cela ne réconcilie pas automatiquement un envoi incertain du bot.
- Date initiale inconnue : demander une date fiable ou proposer un ancrage explicitement accepté à l’activation, distinct d’une date de publication ; ne pas supposer cinq jours d’inactivité.
- Reprise après indisponibilité : recalculer l’éligibilité, fusionner les motifs et ne jamais envoyer une rafale de rappels manqués.
- Les données Telegram non récupérées ne sont conservées par Telegram que pendant une durée limitée : aucune promesse de rattraper toute conversation après une longue coupure.

## 5. Recherche et qualité éditoriale

« Recherche approfondie » signifie ici un dossier limité mais traçable : proposition de trois requêtes maximum, cinq pages maximum par tour, sélection de sources primaires puis corroboration indépendante. Ces plafonds internes évitent une boucle coûteuse ; l’utilisateur peut autoriser un nouveau tour dans la limite du quota gratuit.

Une reprise d’un communiqué par plusieurs sites ne compte pas comme plusieurs confirmations indépendantes. Une page inaccessible ou un extrait de moteur n’est pas déclaré « vérifié ». Pour une opinion personnelle, distinguer le vécu confirmé par l’utilisateur des éléments factuels externes ; une recherche ne doit pas inventer un contexte pour remplir un quota de sources.

Avant validation : vérifier noms, dates, nombres, pertinence temporelle, liens, répétitions génériques, promesses futures et ressemblance excessive avec les anciens posts. La qualité du français nécessite une recette humaine : aucun score LLM ne prouve à lui seul qu’un texte est naturel.

Proposer une longueur de travail inférieure ou égale à 3 000 caractères ; la limite effective et le comptage de l’endpoint LinkedIn retenu restent à tester. Montrer le texte complet, sans troncature cachée ni ajout de hashtags après validation.

## 6. Archive centrale, import, mémoire et style

### 6.1. Socle validé et séparation des données

L’archive SQLite conserve durablement **tous les textes dont la rétention est permise**, sans fenêtre glissante de trois publications. Elle distingue textes publiés, versions, observations d’acquisition et provenance réelle ; les brouillons, intentions d’envoi et états opérationnels restent séparés des publications confirmées. « Durable » ne signifie jamais conservation illimitée contre une restriction ou une demande d’effacement.

Le profil compact persistant est distinct de l’archive et des règles normatives explicitement confirmées. Les trois récents sont un échantillon possible ; l’application affiche la couverture réellement connue et ne prétend pas connaître les derniers posts LinkedIn si elle ne les observe pas tous. Aucun historique intégral de messagerie, aucune mémoire vectorielle, aucun secret transmis à un fournisseur IA ; aucune alimentation de la mémoire globale des agents.

### 6.2. Source A — publications du bot confirmées

- Archiver au titre d’une publication réussie **seulement après confirmation fiable de LinkedIn**, en conservant le **texte original exact envoyé**, pas une reformulation ou un texte reconstruit depuis un export. « Original envoyé » décrit la source des octets textuels, pas une attribution automatique à l’utilisateur : conserver l’indication d’une rédaction assistée.
- Enregistrer ensemble le reçu/preuve de succès autorisé, l’état de succès et l’entrée d’archive dans une **transaction locale SQLite atomique**. L’appel LinkedIn est extérieur à cette transaction : aucune transaction réseau, aucun rollback de publication distant ou « exactly once » garanti. Une panne entre succès distant et commit local nécessite réconciliation, jamais un nouvel envoi automatique.
- L’ID LinkedIn **typé** et l’URL peuvent rester `null` si le reçu fiable ne les fournit pas ; ne jamais les inventer, les déduire d’un suffixe ou fabriquer une URL. Conserver la preuve permettant de qualifier le succès indépendamment de leur présence.
- `published_at` = date de publication attestée, avec source, **précision et fuseau** ; conserver les inconnues au lieu d’inventer une heure. `confirmed_at` = instant où le succès est observé. `imported_at` = instant d’acquisition/import, distinct des deux autres ; aucune substitution automatique entre ces champs.
- Brouillon, clic, intention, accusé d’upload image ou `UNKNOWN_OUTCOME` ne valent pas publication réussie. Un timeout après envoi possible verrouille les publications du compte avec **zéro retry automatique** ; un import ultérieur peut apporter un élément à examiner mais ne résout pas automatiquement l’incertitude.
- La purge proposée des brouillons à **30 jours** ne supprime pas la copie publiée de l’archive lorsque sa conservation reste autorisée. Elle ne dispense pas des effacements obligatoires ou demandés.

### 6.3. Source B — import indépendant du fournisseur

Le contrat d’import est indépendant d’Apify : des copies ou exports autorisés peuvent l’alimenter, sans prétendre à une synchronisation ni à une collecte autorisée par défaut. Le **skill Apify exact n’est pas fourni et n’a pas été audité**. Ne pas invoquer un skill générique à sa place. Avant toute intégration, examiner ses fichiers, instructions, dépendances, Actor(s) exact(s), entrées/sorties anonymisées, ainsi que ses accès, coûts et conditions. Les adaptations restent **des propositions** ; le skill original demeure inchangé, sans exécution pendant cette mission.

Pipeline proposé, avec garde-fous obligatoires :

1. **Vérifier les droits avant toute persistance** : origine et modes d’obtention, droits de stockage, d’analyse/comparaison, de dérivation et de transfert à chaque destination d’aperçu/traitement. Droits inconnus ou incompatibles = refus/blocage, pas de copie provisoire en base, fichier temporaire, journal ou sauvegarde. Ne pas demander d’envoyer un export à Telegram si ce transfert n’est pas autorisé.
2. **Parser de façon bornée**, comme une entrée non fiable : taille, nombre d’éléments, longueur des champs et formats à fixer avant intégration. Aucun contenu importé n’est une instruction exécutable ; ne pas ouvrir automatiquement de liens ou exécuter du code incorporé.
3. **Comparer** aux textes/versions connus par les règles ci-dessous et attribuer un statut explicite à chaque élément.
4. Produire un **aperçu immuable** du lot, de ses éléments, versions/différences, dates, provenance, droits et décisions proposées, uniquement via une destination autorisée. Une modification du lot ou de la base affectant la comparaison invalide l’aperçu concerné.
5. Recueillir l’**accord explicite sur le lot ou sur les éléments sélectionnés**, lié à cet aperçu exact ; conflits/ambiguïtés nécessitent arbitrage, les refus ne sont pas contournables par un simple « oui ».
6. Appliquer les éléments approuvés en **transaction locale idempotente**, en revérifiant les droits et la validité de l’aperçu. Rejouer le même lot approuvé ne duplique ni texte ni version ; une acquisition indépendante peut apporter une nouvelle observation traçable, pas une duplication silencieuse du post.

Statuts à présenter : **nouveau** (aucune correspondance fiable), **connu** (même version identifiée), **version** (même publication, texte changé à confirmer), **conflit** (valeurs incompatibles), **ambigu** (identité/date insuffisante), **refus** (droits, format ou contrôles incompatibles). Un accord d’import n’est jamais une autorisation de publication.

Règles de rapprochement et de versionnement :

- Priorité à l’**identifiant LinkedIn typé complet**, avec sa provenance. Ne pas assimiler les suffixes numériques de `share`, `ugcPost` et `activity` ; une équivalence éventuelle exige une preuve distincte, jamais l’égalité du suffixe.
- À défaut d’ID fiable, proposer un repli **conservateur** sur texte normalisé pour comparaison + date suffisamment précise + auteur + métadonnées concordantes. Garder le texte source exact distinct de sa forme de comparaison ; ne pas effacer accents, ponctuation ou différences significatives pour forcer une égalité. Date/auteur manquants ou rapprochement incertain = arbitrage humain, pas de fusion par similarité seule.
- Même ID et texte changé : proposer une **nouvelle version confirmée**, jamais écraser silencieusement la précédente. Une date d’acquisition plus récente ne prouve pas à elle seule l’ordre de modification des textes.
- Une valeur `null` n’écrase jamais une valeur connue ; une valeur contradictoire produit un conflit. **IDs différents et textes proches peuvent désigner des publications réellement distinctes.** L’absence d’un post dans un lot ne constitue pas une suppression.
- Conserver **origine réelle, observations, versions et imports** : source de collecte, acteur/fournisseur si connu, type d’ID, acquisition, dates et précision, confirmations et statut de rédaction assistée. Un export API transmis par l’utilisateur reste d’origine API, pas un « original utilisateur » bénéficiant artificiellement d’autres droits.
- La non-destruction silencieuse protège les données **encore autorisées** ; elle n’autorise jamais la conservation illicite d’anciennes versions après expiration de droits ou demande d’effacement.

### 6.4. Profil descriptif et règles normatives

- Calculer des observations descriptives de style (structure, longueur, ton, procédés rédactionnels) **recalculables**, référencées aux versions sources, périodes, couverture et niveau de confiance. Échantillon réduit ou incomplet = limites visibles, pas de certitude fabriquée.
- Ne déduire aucune caractéristique sensible de l’auteur. Identifier les textes écrits/assistés par le bot ; les isoler des références de style humain pour éviter une boucle renforçant le style IA. Si l’attribution est inconnue, la signaler ; modalités de sélection/pondération à valider.
- Le profil peut persister sous réserve des droits applicables ; sa persistance **ne transforme pas les observations en consignes normatives**. Toute règle permanente exige une confirmation séparée de son **texte exact**, même si elle semble évidente dans les publications. Une correction ponctuelle ne crée aucune règle.
- Prévoir suppression ciblée, invalidation et recalcul après retrait/modification des sources autorisées ; observations, index et profil héritent des restrictions et suppressions de leurs sources. Une règle explicitement confirmée reste séparée sans servir à contourner une restriction de dérivation.

### 6.5. Retrieval borné proposé

SQLite reste la base validée ; **filtres + FTS5 si disponible** sont proposés, sans nouvelle dépendance ni base vectorielle obligatoire. Sélectionner des échantillons récents, thématiques ou par période selon le besoin et les droits, avec références/dates et couverture visibles. Trois récents sont un point de départ possible, pas une limite d’archive.

Proposition à valider : **6 posts maximum et 12 000 caractères cumulés** de textes récupérés par génération, **profil limité à 4 000 caractères**. Préférer une sélection plus courte ; tout extrait éventuel est explicitement signalé, sans modifier l’original archivé. Les **règles confirmées sont fournies séparément et ne sont jamais tronquées silencieusement** ; si le contexte disponible ne suffit pas, exposer le blocage et demander un arbitrage. Ne pas envoyer toute l’archive à chaque génération ; chaque transfert vers le LLM ou Telegram doit être autorisé, même si le stockage local l’est.

### 6.6. Rétention, conformité et effacement

Vérifier séparément **stockage, analyse, dérivation et transfert vers chaque destination**, y compris Telegram, pour chaque origine. Le consentement utilisateur ne neutralise ni les conditions fournisseur ni une interdiction applicable. Droits inconnus = aucune persistance provisoire ; autorisation de stockage local ≠ autorisation d’analyse, de dérivation ou d’envoi au LLM.

La règle des **48 heures des LinkedIn Marketing APIs concerne l’activité sociale issue de ces APIs** ; ce n’est pas une règle générale applicable indistinctement aux originaux ou à Apify. Inversement, faire transiter un export par l’utilisateur ou Apify n’efface pas son origine ni les restrictions qui lui sont applicables. Un scope accordé ne suffit pas à autoriser tous les usages ; l’accès de lecture historique pour le style demeure bloqué tant que ses conditions ne sont pas clarifiées.

Les conditions plus strictes priment sur la conservation durable souhaitée. Tout effacement requis ou demandé doit se propager aux textes/versions concernés, dérivés, index, profil et copies/sauvegardes locales concernées selon une politique à valider ; aucun ancien texte illicite conservé sous prétexte d’éviter une suppression silencieuse. Tracer la décision d’effacement uniquement dans la mesure permise, sans recopier le contenu supprimé. Les durées et modalités restent à préciser dans [l’architecture](TECHNICAL_ARCHITECTURE.md), sans réintroduire de plafond de trois posts ni d’archive binaire d’images.

**Les conditions d’utilisation en Tunisie et les transferts restent non vérifiés.** Les politiques Telegram, LinkedIn et des autres prestataires sont distinctes ; ne présumer ni accès de compte ni droit général de suppression chez ces services.

### 6.7. Images sans archive binaire

L’absence d’archive de fichiers images est validée. La recommandation technique **encore proposée** est la **RAM seule de bout en bout** : téléchargement, prévisualisation, traitement et envoi par tampons mémoire, sans BLOB SQLite, disque temporaire ni sauvegarde binaire. Seules les métadonnées, empreintes/hash et informations/preuves de droits **autorisées** sont persistables ; un hash ne remplace ni le fichier à approuver ni une preuve de capacité de publication image.

Qualifier les bibliothèques et chemins réels avant de retenir cette option ; un composant exigeant un fichier local bloque le parcours image tant qu’une solution conforme n’est pas validée. Après perte du tampon ou redémarrage, refaire l’aperçu du fichier exact et les approbations **image puis finale**, même si un lien ou identifiant permet de le récupérer. Une modification du texte/crédit impose aussi la revalidation texte ; jamais de remplacement d’image ou de passage au texte seul silencieux.

RAM seule ne promet **ni absence de swap OS/copies système, ni suppression des images chez Telegram ou LinkedIn**. Leurs transferts et politiques doivent être examinés séparément. Le succès d’une publication texte ne prouve pas le parcours image : `w_member_social` seul ne permet pas le GET versionné du statut d’image.

## 7. Modes dégradés acceptables

| Incident | Comportement |
|---|---|
| LLM indisponible ou quota atteint | Conserver le brouillon, permettre son édition manuelle ; pas de génération annoncée comme réussie |
| Recherche indisponible | Accepter des liens fournis et tenter leur lecture ; bloquer les faits non vérifiables plutôt que fabriquer des sources |
| Historique incomplet ou import non conforme | Demander des originaux autorisés via l’importeur indépendant ; couverture et limites du style affichées, aucune fausse synchronisation |
| Image indisponible/droits douteux/API images non validée | Proposer explicitement le texte seul ; jamais retirer silencieusement une image approuvée |
| OAuth expiré/refusé | Maintenir les fonctions éditoriales et demander une reconnexion ; aucun contournement |
| Hôte arrêté | Aucun rappel ni traitement ; reprise explicite à son retour, disponibilité non garantie |
| Résultat d’envoi incertain | Verrouiller toute nouvelle publication sur le compte jusqu’à résolution humaine ou preuve officielle |

## 8. Décisions encore ouvertes

Déjà validés : Python + SQLite, Telegram principal/n8n facultatif, Tunisie/`Africa/Tunis`, API officielle, 0 € sans fallback payant, validations séparées puis finale, modularité, archive textuelle sans fichiers images. Restent à décider :

1. Hôte, administrateur, interruptions et coûts indirects acceptés.
2. Fournisseurs/modèles/offres réellement accessibles, conditions de données et consentements par usage/destination (Telegram inclus) ; produits/scopes/callback LinkedIn et preuves d’accès.
3. Fichiers/instructions/dépendances/Actors et I/O anonymisées du skill Apify exact ; origine et droits des imports, limites de parsing, modalités d’accord lot/éléments. Aucun secret dans le chat.
4. Paramètres proposés : rétention par origine, purge brouillons 30 j, lots en attente 7 j, RAM seule pour images, retrieval 6 posts/12 000 caractères, profil 4 000 caractères, expiration finale 10 min, seuil 120 h, heure/jours des rappels.
5. Thèmes, public, ton, exclusions et recette éditoriale ; confirmation séparée de chaque règle normative permanente.

Les vérifications de comptes et les blocages précis sont suivis dans [API_INTEGRATIONS.md](API_INTEGRATIONS.md) ; l’ordre d’autorisation et de développement est fixé dans [DEVELOPMENT_ROADMAP.md](DEVELOPMENT_ROADMAP.md).
