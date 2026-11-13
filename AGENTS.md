# LinkedIn AI Assistant

Assistant personnel piloté par Telegram. État : **Phases 2–3 implémentées localement (socle conversationnel, archive centrale, import générique ; 50 tests sans réseau, publication simulée). Aucune intégration authentifiée ni action externe effectuée. Modalités détaillées encore proposées.**

## Autorisation de travail

- **CRITICAL : l’utilisateur a autorisé le démarrage de l’implémentation (13 novembre 2026). Toute action externe — création/configuration de compte, publication, upload, test réel — exige une autorisation distincte sur l’action et le contenu exacts.**
- La spécification porte sur les neuf documents indexés, dont AGENTS.md. Ne créer aucun compte, abonnement, déploiement ou secret sans accord ; aucune action sur un service sans autorisation distincte.
- Une validation d’architecture n’autorise ni une publication de test ni une autre action externe sur un compte. Ne pas modifier le skill Apify.

## Architecture : socle validé, modalités proposées

**Validés :** Python + SQLite, modularité et fournisseurs interchangeables, Telegram principal, n8n facultatif, Tunisie et `Africa/Tunis`, API officielle LinkedIn, budget 0 € sans paiement obligatoire, validations texte/image distinctes puis finale, archive centrale durable de tous les textes dont la rétention est permise et profil compact persistant, sans archive binaire d’images. Trois posts récents = échantillon, pas plafond de stockage.

**Proposés / non vérifiés :** hôte, fournisseurs, scopes/permissions, conditions/consentements, paramètres de rétention/import/retrieval et rappels. Monolithe processus unique et long polling implémentés, non éprouvés sur un compte réel.

## Commandes

- `python -m venv .venv && .venv/Scripts/python -m pip install -e ".[dev]"` — installation locale (Windows ; Linux/macOS : `.venv/bin/python`)
- `.venv/Scripts/python -m pytest -q` — tests sans réseau
- `.venv/Scripts/linkedin-assistant --config config.toml` — démarrage ; sans `TELEGRAM_BOT_TOKEN`, mode simulation sans aucune action réseau. Le jeton ne va jamais dans un fichier versionné.

## Rules

Les règles détaillées sont dans les documents suivants ; aucun fichier `.agents/rules/` supplémentaire n’est nécessaire à ce stade.

- [README.md](README.md) : statut, navigation et décisions humaines.
- [Exigences produit](docs/PRODUCT_REQUIREMENTS.md) : périmètre et critères d’acceptation.
- [Architecture technique](docs/TECHNICAL_ARCHITECTURE.md) : modules, états, interfaces et données.
- [Décisions](docs/ARCHITECTURE_DECISIONS.md) : arbitrages proposés et conditions de remplacement.
- [Feuille de route](docs/DEVELOPMENT_ROADMAP.md) : portes de validation avant chaque phase.
- [API](docs/API_INTEGRATIONS.md) : permissions, protocoles et accès restant à vérifier.
- [Services gratuits](docs/FREE_SERVICES_BENCHMARK.md) : sources officielles datées et limites économiques.
- [Tests](docs/TEST_STRATEGY.md) : invariants et preuves attendues.

## Contraintes universelles

- Budget validé : **0 €, aucun paiement obligatoire ni fallback payant** ; quota épuisé = arrêt, jamais essai/crédit de bienvenue présenté comme gratuit permanent.
- Une documentation publique ne prouve aucun accès de compte. Dater et distinguer fait officiel, proposition et test réel ; conditions tunisiennes/transferts restent non vérifiés.
- Publication exclusivement par API officielle LinkedIn : approbations texte et image/absence distinctes, puis autorisation finale à usage unique sur la révision exacte ; conserver anti-doublon et invalidation des approbations concernées après modification.
- **Le LLM ne publie pas.** Ni source web, ni rappel, ni message ambigu ne peut autoriser la publication. Recherche proposée : 3 requêtes / 5 pages maximum par tour.
- Timeout après envoi possible : `UNKNOWN_OUTCOME`, verrou du compte et **zéro retry automatique** jusqu’à réconciliation explicite ; un import ne résout pas automatiquement l’incertitude.
- Source A : archive après confirmation LinkedIn fiable seulement ; texte original exact envoyé + preuve/succès + archive en transaction locale atomique, jamais réseau. ID/URL nullables, jamais inventés ; `published_at` attesté avec précision/fuseau, `confirmed_at` observation et `imported_at` acquisition distincts. Brouillon/intention ≠ succès.
- Source B : droits avant persistance → parse borné → comparaison → aperçu immuable → accord lot/éléments → transaction idempotente. Statuts nouveau/connu/version/conflit/ambigu/refus, identifiants typés sans assimiler share/ugcPost/activity, ambiguïtés humaines ; préserver origine réelle/observations/versions, jamais réétiqueter un export API en original utilisateur (détails dans les exigences produit).
- Mémoire applicative : préférences confirmées, opérations nécessaires, **archive textuelle autorisée et profil compact persistant distincts**. Trois récents = échantillon ; purge proposée des brouillons à 30 jours ≠ purge de l’archive autorisée. Ne pas enrichir la mémoire globale ni les mémoires d’autres agents.
- Profil descriptif recalculable avec références versions/périodes/couverture/confiance, sans inférence sensible ; identifier les textes assistant pour éviter de renforcer le style IA. Règle normative permanente seulement après confirmation séparée de son texte exact ; correction ponctuelle ≠ règle.
- Retrieval proposé : filtres SQLite + FTS5 si disponible, échantillons récents/thématiques/par période, 6 posts / 12 000 caractères cumulés et profil 4 000 caractères ; règles confirmées séparées, pas de troncature silencieuse ni toute l’archive à chaque génération.
- Vérifier séparément stockage/analyse/dérivation/transfert par destination, Telegram inclus ; droits inconnus = aucune persistance provisoire. Les 48 h Marketing APIs concernent leur activité sociale, pas tous les imports/originaux ; consentement ≠ dérogation aux conditions. Restrictions plus strictes et effacements requis/demandés priment et se propagent aux versions/dérivés/index/profil ; ne pas garder illicitement d’anciens textes.
- Ne jamais journaliser clés, jetons, cookies ou liens signés. Les secrets ne sont ni des paramètres de prompt ni des messages Telegram.
- Skill Apify exact non fourni/non audité : ne pas invoquer de générique. Examiner fichiers/instructions/dépendances/Actor(s)/entrées-sorties anonymisées et accès/coûts/conditions avant toute intégration ; adaptations seulement proposées, original inchangé, aucun contournement LinkedIn.
- Vérifier les droits d’image et approuver le fichier exact indépendamment du texte ; preuve de succès texte ≠ capacité image, `w_member_social` seul ne permet pas le GET versionné du statut d’image.
- Aucune archive binaire d’images ; RAM seule de bout en bout proposée, sans BLOB/disque temporaire/sauvegarde, métadonnées/hash/droits autorisés seulement. Tampon perdu/redémarrage : nouvel aperçu et approbations image/finale, jamais retrait silencieux ; ne promettre ni suppression Telegram/LinkedIn ni absence de swap OS.
- Rappels : `Africa/Tunis` fixé ; activation/heure/jours/120 h proposés. `published_at` accepté, jamais `imported_at` ; date imprécise/future/en conflit = clarification, `confirmed_at` du bot seulement comme approximation signalée sans heure serveur. Au plus 1/jour, fusion/reprise sans rafale ; bot utilisable sans rappels.
- Toute dépendance doit répondre à un besoin actuel et prévoir un point de remplacement ; installation limitée à l’environnement du projet. Les modalités non validées (seuils, durées, RAM images, fournisseurs) restent des propositions à confirmer.
