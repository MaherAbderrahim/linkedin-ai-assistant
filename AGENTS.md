# LinkedIn AI Assistant

Assistant personnel piloté par Telegram. État : **Phase 1 (volet B) livrée le 14 novembre 2026 — 143 tests sans réseau : loader `.env` stdlib + validation des variables par nom au démarrage, rappel 10 h `Africa/Tunis` modifiable, paramètres progressifs partagés Telegram/dashboard (`/settings`), contrat `Publisher` formalisé (résolution dynamique treg), contrat `LLMProvider` + adaptateurs simulés Groq/OpenRouter + harness `llm_benchmarks` (aucun appel réel), tableau de bord local `127.0.0.1:8000` (aucune publication). Phases 2–4 et rappels locaux déjà livrées. Scaffolding Phase 5 simulé livré (SearchProvider + budget, extracteur SSRF). Accès de publication LinkedIn provisionné via treg (ADR-16) : connexion active, identité et `w_member_social` vérifiés ; publication réelle NON TESTÉE. Gate G1 atteint côté code ; volet A restant : qualification réelle `/rest/posts` + image (tests autorisés distincts), consentements, conditions treg.**

## Autorisation de travail

- **CRITICAL : l'utilisateur a autorisé l'implémentation locale (13 novembre 2026) et validé le périmètre de la Phase 1 volet B (14 novembre 2026, ordre ajusté), qui est livré. Toute action externe — publication treg réelle, appel LLM réel, test de qualification `/rest/posts` — exige toujours une autorisation distincte sur l'action et le contenu exacts.**
- Toute action externe — création/configuration de compte, publication, upload, appel API réel, test réel — exige une autorisation distincte sur l'action et le contenu exacts. Ne créer aucun compte, abonnement, déploiement ou secret sans accord.
- La spécification porte sur les documents indexés ci-dessous, dont AGENTS.md. Une validation d'architecture n'autorise ni publication de test ni autre action externe. Ne pas modifier le skill Apify original (audité, voir le rapport dédié).

## Architecture : socle validé, modalités proposées

**Validés :** Python + SQLite, modularité et fournisseurs interchangeables, Telegram principal, n8n facultatif, Tunisie et `Africa/Tunis`, API officielle LinkedIn, budget 0 € sans paiement obligatoire ni basculement payant automatique, validations texte/image distinctes puis finale, archive centrale durable des textes dont la rétention est permise et profil compact persistant, sans archive binaire d'images. Trois posts récents = échantillon, pas plafond de stockage.

**Décisions du 13 novembre 2026 :** hébergement sur le PC de l'utilisateur pour le développement et les premiers tests (Oracle Always Free à étudier plus tard, PC ami en secours ; aucune installation distante maintenant, développement non bloqué) ; LLM Groq + OpenRouter à comparer (français, instructions, style, latence, limites), aucun modèle figé avant tests, clés fournies par l'utilisateur via `.env` ; tableau de bord web local planifié (localhost, même configuration SQLite que Telegram, jamais exposé publiquement sans protection) ; rappel quotidien à 10 h 00 `Africa/Tunis`, modifiable ; paramètres éditoriaux progressifs configurables.

**Décision du 14 novembre 2026 (treg, ADR-16) :** l'accès de publication LinkedIn passe par treg (proxy de credentials hébergé) avec l'OAuth propre du membre détenu côté treg — pas d'application Developer propre ni de callback local. Connexion `linkedin` active (capability `write`, consentement navigateur utilisateur) ; `v2/userinfo` → 200 (identité + `w_member_social`, expiration 2027-01-13). Publication prévue `POST /rest/posts` (0 $), preuve = HTTP 201 + URN `x-restli-id`, jamais le scraping treg ; rotation ⇒ résolution dynamique de la connexion via `treg connections ls` (aucun nom/secret en dur) ; endpoints treg mesurés à éviter ; bug machine `NO_PROXY=[::1],::1` ⇒ préfixer chaque commande treg de `NO_PROXY=` (vide). Publication réelle NON TESTÉE ; chaque test exigera une autorisation distincte.

**Proposés / non vérifiés :** scopes/permissions LinkedIn, conditions/consentements par usage/destination, paramètres de rétention/import/retrieval, seuil d’inactivité 120 h. Monolithe processus unique et long polling implémentés, non éprouvés sur un compte réel. Aucune application LinkedIn Developer antérieure trouvée sur la machine : vérifier le portail avant toute création ; une page entreprise n’est pas intrinsèquement requise pour la publication personnelle.

## Commandes

- `python -m venv .venv && .venv/Scripts/python -m pip install -e ".[dev]"` — installation locale (Windows ; Linux/macOS : `.venv/bin/python`)
- `.venv/Scripts/python -m pytest -q` — tests sans réseau
- `.venv/Scripts/linkedin-assistant --config config.toml` — démarrage ; sans `TELEGRAM_BOT_TOKEN`, mode simulation sans aucune action réseau. Le jeton ne va jamais dans un fichier versionné.
- `.venv/Scripts/linkedin-assistant --config config.toml --local` — test interactif local sans réseau : texte libre = révision, numéros = boutons, publication simulée.
- `.venv/Scripts/linkedin-assistant --config config.toml --dashboard [--port N]` — tableau de bord local lié à 127.0.0.1 (défaut 8000) : configuration générale et état système, même SQLite, aucune publication possible.

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
- [Audit du skill Apify](docs/APIFY_SKILL_AUDIT.md) : fonctionnement, Actors LinkedIn, coûts, limites, conformité et modes d’intégration.
- [Qualification treg](docs/QUALIFICATION_TREG.md) : runbook prêt mais non exécuté pour le premier test réel `/rest/posts` et le parcours image ; chaque étape exige une autorisation distincte.

## Contraintes universelles

- Budget validé : **0 €, aucun paiement obligatoire ni fallback payant** ; quota épuisé = arrêt, jamais essai/crédit de bienvenue présenté comme gratuit permanent.
- LLM : Groq + OpenRouter à comparer avant toute sélection définitive ; changement de modèle/fournisseur sans toucher au métier ; aucun fournisseur payant sans autorisation, aucun basculement automatique vers du payant.
- Tableau de bord web local : localhost uniquement, même configuration SQLite que Telegram, pas de second chemin de publication (mêmes validations déterministes) ; jamais accessible publiquement sans authentification et protection des secrets.
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
- Secrets via `.env` local (ignoré par git ; `.env.example` factice versionné) : jamais de clé dans le code, les logs, les prompts ou les messages Telegram ; ne jamais demander de coller une clé dans la conversation. Vérifier les variables manquantes au démarrage par leur nom, sans révéler leur contenu. Ne jamais journaliser clés, jetons, cookies ou liens signés.
- Skill Apify audité le 13 novembre 2026 (voir [rapport](docs/APIFY_SKILL_AUDIT.md)) : skill d’agent pilotant le CLI Apify, Actors LinkedIn community/PPE, scraping non conforme par défaut. Original inchangé, aucune exécution d’Actor sans accord distinct ; intégration par l’import générique (export utilisateur préféré), jamais une dépendance du cœur ni un moyen de publication.
- Vérifier les droits d’image et approuver le fichier exact indépendamment du texte ; preuve de succès texte ≠ capacité image, `w_member_social` seul ne permet pas le GET versionné du statut d’image.
- Aucune archive binaire d’images ; RAM seule de bout en bout proposée, sans BLOB/disque temporaire/sauvegarde, métadonnées/hash/droits autorisés seulement. Tampon perdu/redémarrage : nouvel aperçu et approbations image/finale, jamais retrait silencieux ; ne promettre ni suppression Telegram/LinkedIn ni absence de swap OS.
- Rappels : `Africa/Tunis` fixé ; rappel quotidien à 10 h 00 choisi par l’utilisateur, modifiable (défaut code actuel 9 h à corriger en Phase 1) ; jours/activation/120 h proposés. `published_at` accepté, jamais `imported_at` ; date imprécise/future/en conflit = clarification, `confirmed_at` du bot seulement comme approximation signalée sans heure serveur. Au plus 1/jour, fusion/reprise sans rafale ; bot utilisable sans rappels.
- Toute dépendance doit répondre à un besoin actuel et prévoir un point de remplacement ; installation limitée à l’environnement du projet. Les modalités non validées (seuils, durées, RAM images, fournisseurs) restent des propositions à confirmer.
