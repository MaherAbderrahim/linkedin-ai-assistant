# LinkedIn AI Assistant

Assistant personnel pour rechercher, rédiger, corriger et publier du contenu LinkedIn depuis Telegram, **uniquement après validations explicites**. Dépôt public réutilisable : chaque utilisateur l'installe chez lui avec **ses propres comptes** — voir [docs/SETUP_GUIDE.md](docs/SETUP_GUIDE.md).

**Statut au 16 novembre 2026 : chaîne complète opérationnelle.** `/research <sujet>` (ou `/link <url>`) déclenche une recherche réelle bornée (Tavily) suivie d'une proposition de post rédigée par Groq/OpenRouter **informée par votre archive locale** (profil de style recalculable + exemples récents + règles confirmées) ; un message libre sur un brouillon existant est **interprété par le LLM** (consigne ou texte final) ; les images sont proposées par le bot **en photo dans Telegram** (bouton « Utiliser ») ou ajoutées depuis le téléphone / une URL, et vivent **en RAM uniquement** (jusqu'à 4 par post) ; `/preview` affiche le texte **et** toutes les images ; les validations sont TEXT → IMAGE/absence → autorisation finale à usage unique ; la publication part par l'API LinkedIn officielle via treg (`POST /rest/posts`), images comprises. **254 tests passent sans réseau.** Publication réelle activée par configuration (`publisher = "treg"`) : le clic final du bouton unique publie vraiment, sur la révision exacte approuvée.

## Démarrage rapide

```powershell
git clone https://github.com/MaherAbderrahim/linkedin-ai-assistant.git
cd linkedin-ai-assistant
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
Copy-Item config.example.toml config.toml   # à adapter (Linux/macOS : cp)
Copy-Item .env.example .env
.venv\Scripts\python -m pytest -q           # ~254 tests, aucun appel réseau
```

Créez ensuite vos comptes et clés (Telegram BotFather, Groq, Tavily, treg/LinkedIn) : la marche à suivre complète est dans **[docs/SETUP_GUIDE.md](docs/SETUP_GUIDE.md)** — y compris le **prompt prêt à coller à votre agent de codage** pour qu'il fasse l'installation avec vous.

## Architecture : décisions validées et propositions

- **Validés : Python + SQLite modulaires**, fournisseurs interchangeables, **Telegram principal**, n8n facultatif ; fuseau configurable (par défaut `Africa/Tunis`).
- **Archive centrale durable de tous les textes dont la rétention est permise**, profil de style compact persistant, règles explicites séparées ; SQLite garde aussi paramètres, brouillons versionnés, approbations, reprise et anti-doublon. Les **trois posts récents sont un échantillon, jamais une limite de stockage**.
- **Source A — publications du bot :** après confirmation LinkedIn fiable seulement, conserver le texte original exact envoyé et enregistrer preuve de succès + archive dans une transaction locale atomique, jamais une transaction réseau. ID/URL restent nullables ; `published_at` attesté (précision/fuseau), `confirmed_at` observé et `imported_at` acquis sont distincts. Brouillon ou `UNKNOWN_OUTCOME` n'est pas une publication réussie.
- **Source B — import indépendant du fournisseur :** droits vérifiés avant persistance, parsing borné, comparaison, aperçu immuable, accord lot/éléments puis transaction idempotente. Provenance réelle, observations et versions conservées ; identifiants LinkedIn typés, ambiguïtés humaines, aucun export API réétiqueté en original utilisateur. Un import ne résout pas automatiquement un envoi incertain.
- **Profil descriptif recalculable et référencé**, sans inférence sensible ; textes assistant identifiés, aucune règle normative permanente sans confirmation séparée du texte exact. Retrieval : filtres SQLite + FTS5 si disponible, échantillons récents/thématiques/par période, au plus **6 posts / 12 000 caractères cumulés**, profil **4 000 caractères** ; règles confirmées séparées, jamais tronquées silencieusement. Pas d'envoi de toute l'archive à chaque génération.
- **Aucune archive binaire d'images.** RAM seule de bout en bout, sans BLOB, disque temporaire ni sauvegarde ; seules métadonnées/empreintes/droits autorisés sont persistables. Perte du tampon ou redémarrage : nouvel aperçu, nouvelles approbations image et finale ; aucune suppression Telegram/LinkedIn ni absence de swap OS promise.
- **API officielle LinkedIn validée en principe**, `/rest/posts` visé ; validations **texte + image/absence distinctes + aperçu exact + autorisation finale à usage unique**. Le LLM ne peut ni autoriser ni déclencher une publication.
- **Accès de publication via treg (ADR-16) :** treg est un proxy de credentials hébergé qui détient l'OAuth du membre — aucune application LinkedIn Developer propre ni callback local à créer. L'adaptateur résout dynamiquement la connexion à chaque envoi (`treg connections ls`, aucun nom/secret en dur) ; preuve de succès = HTTP 201 + URN, jamais le scraping.
- **LLM Groq + OpenRouter à comparer** (qualité du français, suivi des instructions, reproduction du style, latence, limites) ; clés via `.env`, fournis par l'utilisateur. Le code refuse tout modèle OpenRouter non `:free` (garde-fou `LLM_MODEL_NOT_FREE`) ; quota épuisé = arrêt explicite, jamais de bascule payante.
- **Tableau de bord web local** (localhost, même SQLite que Telegram, aucune publication possible depuis le dashboard).
- **Rappels facultatifs** : au plus un par jour, fusion et reprise sans rafale ; le bot fonctionne sans rappels.

## Faisabilité et limites honnêtes

**0 € et aucun paiement obligatoire ni fallback payant** : quota gratuit épuisé ou conditions ambiguës, arrêt de la capacité concernée. Aucun accès de compte, SLA ou gratuité perpétuelle présumé ; matériel, Internet et électricité de l'hôte restent à prendre en charge explicitement.

La publication personnelle via `w_member_social` est documentée, pas attestée pour un compte donné :

- La lecture de l'historique via `r_member_social` est restreinte ; import autorisé et déclaration datée ne valent pas surveillance automatique des posts externes.
- **`w_member_social` seul ne permet pas le GET versionné du statut d'image.** Preuves et qualification texte/image séparées.
- Timeout après envoi possible : **`UNKNOWN_OUTCOME`, verrou du compte, zéro retry automatique**, réconciliation explicite. Ni brouillon ni import ne prouvent automatiquement le succès d'un envoi ; aucune garantie réseau « exactly once ».
- La première publication réelle de chaque installation est un vrai test : commencez par un contenu que vous assumez, et vérifiez le résultat directement sur LinkedIn.

**Conformité par origine et usage :** vérifier séparément stockage, analyse, dérivation et transfert vers chaque destination, **Telegram compris**. Un export conserve son origine API ; le consentement ne neutralise pas les conditions. Droits inconnus : aucune persistance provisoire. Restrictions plus strictes et effacements requis/demandés se propagent aux versions, dérivés, index et profil ; la purge proposée des brouillons à 30 jours n'efface pas l'archive autorisée.

Le **skill Apify a été audité** (voir [APIFY_SKILL_AUDIT.md](docs/APIFY_SKILL_AUDIT.md)) : skill d'agent pilotant le CLI Apify, Actors LinkedIn tous community/PPE, scraping bloqué à grande échelle et non conforme par défaut. Réutilisation éventuelle pour l'archive via l'**import générique** (export utilisateur préféré, adaptateur optionnel après droits et accord) ; jamais une dépendance du cœur ni un moyen de publication.

## Documents de référence

| Fichier | Contenu |
|---|---|
| [SETUP_GUIDE.md](docs/SETUP_GUIDE.md) | **Guide d'installation de zéro à votre premier post** (comptes, clés, prompt pour votre agent de codage) |
| [AGENTS.md](AGENTS.md) | Consignes pour les sessions d'agent de codage, règles non négociables et index |
| [PRODUCT_REQUIREMENTS.md](docs/PRODUCT_REQUIREMENTS.md) | Besoin complet, périmètre, parcours, exigences et critères d'acceptation |
| [TECHNICAL_ARCHITECTURE.md](docs/TECHNICAL_ARCHITECTURE.md) | Modules, interfaces, états, validations, données, conservation et exploitation |
| [ARCHITECTURE_DECISIONS.md](docs/ARCHITECTURE_DECISIONS.md) | Comparaison de quatre architectures, raisons, alternatives et limites des choix |
| [DEVELOPMENT_ROADMAP.md](docs/DEVELOPMENT_ROADMAP.md) | Phases, dépendances, gates et autorisations avant développement/actions réelles |
| [API_INTEGRATIONS.md](docs/API_INTEGRATIONS.md) | Capacités documentées vs accès non testés, OAuth, endpoints, limites et sources LinkedIn |
| [FREE_SERVICES_BENCHMARK.md](docs/FREE_SERVICES_BENCHMARK.md) | Comparaison documentaire datée, quotas, pays, confidentialité, cartes et frais possibles |
| [TEST_STRATEGY.md](docs/TEST_STRATEGY.md) | Tests futurs, invariants de sécurité, pannes, recette humaine et preuves attendues |
| [APIFY_SKILL_AUDIT.md](docs/APIFY_SKILL_AUDIT.md) | Audit du skill Apify : fonctionnement, Actors, coûts, limites, conformité, intégration |
| [QUALIFICATION_TREG.md](docs/QUALIFICATION_TREG.md) | Runbook de qualification réelle treg (`/rest/posts` + image) ; chaque étape exige une autorisation distincte |

Code : `src/linkedin_assistant/` (bibliothèque standard uniquement), tests dans `tests/`.

### Mode de publication

`config.toml` porte deux clés explicites :

```toml
publisher = "simulated"        # ou "treg" (publication réelle)
linkedin_api_version = "202611" # LinkedIn-Version YYYYMM, choisie explicitement
```

- `publisher = "simulated"` : aucun appel externe, utile pour apprendre le parcours.
- `publisher = "treg"` : publication réelle via la connexion treg résolue dynamiquement à chaque envoi. Aucun repli silencieux : sans version d'API explicite, le bot refuse de démarrer. La publication reste soumise aux trois validations dans le bot.

### Commandes Telegram

| Commande | Effet |
|---|---|
| `/new` puis un texte | brouillon (une révision par message) |
| `/research <sujet>` | sujet = un simple nom ? le bot demande de préciser l'angle ; sinon recherche bornée → proposition informée par votre archive + images candidates proposées en photo |
| `/link <url>` | lecture de la page puis proposition de post |
| message libre | consigne interprétée par le LLM sur le brouillon courant, ou texte final si le message est déjà complet |
| `/image <url>`, photo, bouton « Utiliser » | image en RAM, attachée au brouillon actif (jusqu'à 4 par post) |
| `/preview` | texte exact + toutes les photos + boutons de validation |
| `/status` `/cancel` `/lastpost <date>` `/reminder on\|off` `/settings <clé> <valeur>` | état, brouillon, déclaration externe, rappels, paramètres |

Les images ne sont **jamais** écrites sur disque ni en base : elles vivent en RAM dans le processus du bot. Un redémarrage les fait disparaître → le bot le signale et exige de renvoyer la photo (nouvel aperçu, nouvelles approbations).

## Risques et réponses

| Risque | Effet | Réponse |
|---|---|---|
| Qualification réelle `/rest/posts` + parcours image | Publication ou image indisponibles | Test autorisé distinct sur votre compte ; preuve = HTTP 201 + URN ; gestion de la rotation treg par résolution dynamique |
| Historique incomplet | Couverture du style et rappels incertains | Import indépendant après droits/aperçu/accord ; dates et couverture visibles, jamais trois posts comme plafond |
| Doublons, versions ou dates ambiguës | Fusion erronée ou mauvais rappel | ID typé prioritaire, repli conservateur texte + date précise/auteur/métadonnées ; arbitrage humain, pas de suppression silencieuse ni de null écrasant une valeur connue |
| Droits/transferts non vérifiés | Stockage ou destination interdits | Vérifier chaque usage/destination, refus sans droits, effacement propagé ; consentement insuffisant à lever une interdiction |
| Image non qualifiée ou tampon perdu | Autorisation image devenue inutilisable | Preuve image séparée ; nouvel aperçu et approbations image/finale, texte seul uniquement par choix explicite |
| Quota gratuit ou hôte indisponible | Traitement interrompu | Arrêt sans paiement, hôte et coûts indirects acceptés ; reprise/sauvegarde des seules données autorisées, jamais des binaires images |
| Réponse LinkedIn perdue | Doublon possible | Verrou du compte, zéro retry automatique, réconciliation ; import seul insuffisant |
