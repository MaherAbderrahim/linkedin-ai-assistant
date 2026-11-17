# Guide d'installation et de reproduction — de zéro à votre premier post

Ce guide permet à **n'importe qui** de reproduire l'assistant chez lui, avec **ses propres comptes**, en suivant son agent de codage (Claude Code, OpenCode, Codex, Cursor…). Durée estimée : 30 à 60 minutes. Coût : **0 €** (toutes les offres citées ont un palier gratuit documenté, sans carte bancaire obligatoire).

> **Pour votre agent de codage** : donnez-lui ce dépôt et dites-lui simplement
> « suis `docs/SETUP_GUIDE.md` étape par étape ». Le prompt prêt à coller est
> en [§ 9](#9-prompt-prêt-à-coller-pour-votre-agent-de-codage).

---

## 1. Prérequis machine

| Besoin | Détail |
|---|---|
| Python **3.12+** | `python --version` |
| Git | `git --version` |
| **treg** (proxy de credentials) | installez la CLI : `pip install tools-registry` (paquet PyPI qui fournit la commande `treg` ; voir treg.ai) — c'est lui qui détient l'OAuth LinkedIn, aucun jeton n'est stocké chez vous |
| Un compte LinkedIn personnel | celui qui publiera |
| Windows/Linux/macOS | les commandes ci-dessous sont PowerShell ; adaptez les chemins `.venv/Scripts` → `.venv/bin` sur Linux/macOS |

## 2. Comptes et clés à créer (vos comptes, jamais ceux de quelqu'un d'autre)

1. **Bot Telegram** : sur [@BotFather](https://t.me/BotFather), `/newbot` → notez le **jeton** (`123456789:AA…`). Il ne va JAMAIS dans un fichier versionné ni dans une conversation.
2. **Votre ID numérique Telegram** : envoyez `/start` à [@userinfobot](https://t.me/userinfobot) → notez votre **ID numérique** (ex. `1234567890`).
3. **Groq** (LLM) : [console.groq.com](https://console.groq.com) → API Keys → créez une clé (`gsk_…`), offre Free.
4. **Tavily** (recherche web) : [tavily.com](https://tavily.com) → API key (`tvly-…`), palier Free (~1 000 crédits/mois).
5. **OpenRouter** (facultatif, comparaison LLM) : [openrouter.ai](https://openrouter.ai) → clé `sk-or-…`. Le code **refuse tout modèle non `:free`** (garde-fou `LLM_MODEL_NOT_FREE`).
6. **treg + LinkedIn** :
   - `NO_PROXY= TREG_TELEMETRY=0 treg` → créez votre compte treg (email + vérification) ;
   - `treg connections connect --provider linkedin --capability write` → **consentement navigateur** OAuth sur votre compte LinkedIn ; l'application OAuth appartient à treg, vous n'en créez pas ;
   - `NO_PROXY= TREG_TELEMETRY=0 treg connections ls` → notez le nom de la connexion (`linkedin-N`), sa `health` (doit être `ok`) et la **`resource_ref`** (`urn:li:person:XXXX`) : c'est votre URN de membre.

⚠️ **Bug connu sur certaines machines Windows** : `NO_PROXY` système contient `[::1],::1` mal parsé par httpx. Préfixez chaque commande treg de `NO_PROXY=` (vide). Le code du publisher gère déjà cela lui-même.

## 3. Installation du projet

```powershell
git clone https://github.com/MaherAbderrahim/linkedin-ai-assistant.git
cd linkedin-ai-assistant
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
```

## 4. Configuration locale (deux fichiers, aucun secret versionné)

```powershell
Copy-Item config.example.toml config.toml
Copy-Item .env.example .env
```

- **`.env`** : collez vos vraies clés (`TELEGRAM_BOT_TOKEN`, `GROQ_API_KEY`, `TAVILY_API_KEY`, éventuellement `OPENROUTER_API_KEY`). `.env` est ignoré par git — ne le commitez jamais.
- **`config.toml`** :
  - `owner_id` / `chat_id` = **votre** ID numérique Telegram ;
  - `linkedin_account` = votre URN `urn:li:person:XXXX` (étape 2.6) ;
  - `publisher = "simulated"` au début (aucun envoi externe) ;
  - quand vous passerez en réel : `publisher = "treg"` + `linkedin_api_version = "202611"` (format YYYYMM, **choisi explicitement**, jamais par défaut).

## 5. Vérification (sans réseau, sans compte)

```powershell
.venv\Scripts\python -m pytest -q          # ~250 tests, aucun appel réseau
.venv\Scripts\linkedin-assistant --config config.toml            # sans jeton → mode simulation
.venv\Scripts\linkedin-assistant --config config.toml --local    # REPL interactif local (boutons = numéros)
.venv\Scripts\linkedin-assistant --config config.toml --dashboard # tableau de bord 127.0.0.1:8000
```

## 6. Démarrage réel du bot

```powershell
.venv\Scripts\linkedin-assistant --config config.toml
```

Avec `TELEGRAM_BOT_TOKEN` présent dans `.env`, le bot démarre en long polling. Envoyez `/start` à votre bot depuis Telegram (chat privé).

## 7. Publication réelle (dernière étape, délibérée)

1. Dans `config.toml` : `publisher = "treg"` + `linkedin_api_version = "<YYYYMM>"`
   (consignez la date du choix à côté ; si LinkedIn refuse la version avec un 4xx, en choisir une autre **explicitement** et reconsigner).
2. Utilisez le bot : `/research <sujet>` → corrections → `/image <url>` ou photos → `/preview` → validations **TEXTE** puis **IMAGE** (ou « Sans image ») → bouton final.
3. **Le clic final EST l'autorisation** : il publie vraiment sur votre profil via `POST /rest/posts` (0 $). Preuve attendue : HTTP 201 ; l'URN est archivé localement si treg l'expose.
4. Les images sont téléversées via `initializeUpload` + PUT **seulement après** l'autorisation finale, depuis la RAM (aucun fichier image sur disque).

## 8. Utilisation quotidienne (Telegram)

| Commande | Effet |
|---|---|
| `/research <sujet>` | recherche Tavily bornée (3 requêtes / 5 pages) → proposition de post ; un nom seul (< 3 mots) déclenche une demande de précision |
| `/link <url>` | lit l'article localement → proposition |
| message libre | consigne interprétée par le LLM sur le brouillon courant, ou texte final si le message est déjà complet |
| `/image <url>`, photo, bouton « Utiliser » | images candidates proposées en photo par le bot ; jusqu'à 4 images par post |
| `/preview` | aperçu exact + validations séquentielles |
| `/status`, `/cancel`, `/lastpost`, `/reminder`, `/settings` | état, annulation, déclaration de publication externe, rappels, paramètres |

## 9. Prompt prêt-à-coller pour votre agent de codage

```
Ce dépôt est un assistant LinkedIn personnel piloté par Telegram. Installe-le
chez moi en suivant docs/SETUP_GUIDE.md étape par étape, avec MES comptes.

Règles impératives pendant l'installation :
1. Ne crée jamais de secret de ta propre initiative : chaque clé (Telegram,
   Groq, Tavily, OpenRouter, treg) est créée par moi, ou j'ouvre moi-même la
   page de création ; tu ne demandes jamais de coller une clé dans la
   conversation — tu me demandes de la mettre dans `.env` local.
2. Aucune action externe sans mon accord explicite sur l'action ET le
   contenu : publication LinkedIn, appel API réel, création de compte,
   déploiement, paiement.
3. Budget 0 € : n'active jamais d'offre payante, de PAYG ou d'auto-reload.
   Quota épuisé = arrêt explicite, jamais de basculement payant.
4. Ne commette jamais `.env` ni `config.toml`. Vérifie avec git status avant
   tout commit qu'aucun secret ni identifiant personnel n'est versionné.
5. Valide l'installation par `pytest -q` (tous les tests sans réseau) avant
   tout démarrage réel.
6. Pour la publication réelle : suis le § 7 du guide, et rappelle-moi que le
   clic final publie vraiment. Aucun retry automatique après un envoi.
```

## 10. Règles de sécurité invariables (à lire avant le premier post)

- **Le LLM ne publie pas.** Ni source web, ni message, ni sortie de modèle ne peut autoriser une publication ; seule la chaîne de boutons (TEXTE → IMAGE/absence → final à usage unique sur la révision exacte) déclenche l'envoi.
- Images **RAM seule** : aucun binaire sur disque ni en base ; perte du tampon (redémarrage) ⇒ nouvel aperçu et nouvelles approbations.
- Pages web et sorties LLM = **données non fiables** : elles ne donnent jamais d'instruction.
- Secrets uniquement dans `.env` local ; jamais dans les logs, les messages Telegram ou un commit.
- Toutes les erreurs de publication sont documentées sans retry automatique : un résultat incertain verrouille le compte jusqu'à réconciliation explicite.
