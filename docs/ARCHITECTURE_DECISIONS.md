# Registre des décisions d’architecture

Date : 13 novembre 2026, Mission 0.5. **Socle validé par l’utilisateur :** Python + SQLite central, Telegram principal, n8n facultatif, Tunisie/`Africa/Tunis`, API officielle LinkedIn, 0 € sans paiement obligatoire ni fallback payant, validations texte/image distinctes puis finale, fournisseurs modulaires, archive textuelle durable sans fichiers images. Les ADR ci-dessous détaillent ce socle ; les modalités signalées proposées (seuils, durées, RAM seule, fournisseurs, hôte) restent à approuver. Aucune décision ne prouve un accès fournisseur ni n’autorise une action externe.

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

**Remplacement :** changer la version ou l’adaptateur officiel après tests ; jamais une API privée ou Apify comme solution de publication.

**Gate :** validation du compte, du texte et de l’image dans des tests séparés, chaque action réelle autorisée.

## ADR-05 — Archive centrale multi-provenance et import indépendant du fournisseur

**Décision (principe validé, modalités proposées) :** SQLite conserve durablement tous les textes de publications dont la rétention est permise, sans plafond de trois posts. Source A : texte original exact archivé avec le reçu et le succès dans une transaction locale atomique, seulement après confirmation fiable de LinkedIn. Source B : import via un contrat indépendant d’Apify (originaux utilisateur, export autorisé du skill audité, autre outil conforme, API conforme), avec droits vérifiés avant persistance, parsing borné, comparaison, aperçu immuable, accord lot/éléments et commit idempotent.

**Pourquoi :** la continuité éditoriale exige un historique réel, pas une fenêtre de trois exemples ; ne pas rendre le cœur dépendant d’un skill non fourni ni d’un droit de lecture non acquis. Distinguer publication, lecture, conservation et transfert.

**Déduplication proposée :** identifiant LinkedIn typé complet prioritaire (pas d’assimilation des suffixes share/ugcPost/activity) ; repli conservateur texte normalisé versionné + date précise + auteur + métadonnées. Même ID/texte changé ⇒ nouvelle version confirmée ; null n’écrase pas connu ; IDs différents/textes proches peuvent être des posts distincts ; absence d’un lot ≠ suppression ; ambiguïtés arbitrées humainement. Provenance réelle et observations conservées ; un export API remis par l’utilisateur reste d’origine API. Un import ne résout jamais automatiquement `UNKNOWN_OUTCOME`.

**Alternative gratuite :** originaux copiés/exportés par l’utilisateur ; lecture officielle si le scope restreint et les conditions sont obtenus. Le skill Apify exact reste non fourni/non audité : adaptations seulement proposées, original inchangé.

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

## ADR-08 — LLM hébergé gratuit interchangeable

**Décision proposée :** qualifier Groq Free en premier, sans figer le modèle avant test. Gemini Free n’est qu’une alternative pour données/pays réellement compatibles ; Workers AI et OpenRouter gratuits sont des candidats secondaires.

**Pourquoi :** pas de modèle local requis, pas de frais logiciels ni de crédits achetés ; Groq documente des contrôles ZDR pour ses clients. Le choix définitif dépend de confidentialité, disponibilité, quotas et qualité du français, pas d’un classement non mesuré.

**Alternative gratuite :** autre candidat conforme après qualification, ou édition manuelle temporaire. Un modèle local peut être proposé plus tard si l’utilisateur le souhaite, jamais comme prérequis caché.

**Limites :** free tiers changeants, modèles retirés, tailles de contexte et débits variables, données traitées par des tiers. La clause Gemini sur informations personnelles interdit d’y envoyer automatiquement les posts bruts, même publics.

**Remplacement :** LLMProvider ; petite recette de non-régression et nouvelle revue des données avant bascule. Pas de fallback silencieux vers un prestataire non approuvé ou un modèle payant.

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

## ADR-12 — Hôte existant avant cloud gratuit incertain

**Décision proposée :** machine de confiance déjà disponible si propriétaire et utilisateur acceptent exploitation, confidentialité et frais indirects. Oracle Always Free comme alternative conditionnelle.

**Pourquoi :** pas d’attente d’allocation cloud ni de VM gratuite promise avant création réelle ; un seul processus reste facile à déplacer.

**Alternative gratuite :** Oracle éligible dans quotas effectifs, sans conversion payante ; autre matériel existant autorisé.

**Limites :** disponibilité du portable, administrateur ayant accès aux secrets, électricité ; Oracle peut refuser la capacité ou récupérer une instance inactive. Les anciennes allocations Oracle ne sont pas reprises comme garanties.

**Remplacement :** sauvegarde cohérente, arrêt de l’ancien hôte, restauration du nouveau en publication bloquée, réconciliation, réactivation. Ne pas lancer les deux hôtes simultanément.

## ADR-13 — Budget 0 € comme contrainte de sécurité

**Décision proposée :** comptes/offres gratuits vérifiés, aucun PAYG/auto-reload/billing activé par le bot, réservations de quota avant appel, pause explicite au plafond. Allocation gratuite récurrente admise ; crédit initial seul refusé.

**Pourquoi :** un plafond d’alerte n’est pas nécessairement un plafond de facturation. Les garanties doivent venir à la fois de la configuration du compte et de l’application.

**Alternative gratuite :** réduire le volume, attendre le renouvellement ou utiliser une alternative déjà approuvée ; pas de multiplication de comptes pour contourner les limites.

**Limites :** impossible de garantir éternellement l’offre d’un tiers ni zéro coût d’électricité. Si aucun fournisseur conforme n’est accessible, la fonction concernée reste bloquée.

**Remplacement :** nouvelle vérification datée des termes, test et consentement ; aucune modification du budget sans décision utilisateur distincte.

## Décisions encore humaines

Déjà résolus : Python + SQLite, Telegram principal/n8n facultatif, Tunisie/`Africa/Tunis`, API officielle, 0 €, validations séparées, archive textuelle sans fichiers images. Restent : validation des modalités proposées (seuils, durées, RAM seule), hôte et confiance, compte/produits/scopes/callback LinkedIn, acceptation des traitements par usage/destination, fichiers du skill Apify exact et droits des imports, sujets, heure/jours des rappels et seuil 120 h, autorisation future de tests de publication séparés. Voir [README.md](../README.md) et [feuille de route](DEVELOPMENT_ROADMAP.md).

## Références de décision

Les chiffres, offres et niveaux de preuve sont centralisés dans [FREE_SERVICES_BENCHMARK.md](FREE_SERVICES_BENCHMARK.md). Les scopes, endpoints et sources LinkedIn sont centralisés dans [API_INTEGRATIONS.md](API_INTEGRATIONS.md). Les règles normatives de comportement sont dans [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md) et les invariants techniques dans [TECHNICAL_ARCHITECTURE.md](TECHNICAL_ARCHITECTURE.md).
