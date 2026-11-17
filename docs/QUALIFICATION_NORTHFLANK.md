# Qualification Northflank (runbook — non exécuté à ce jour)

Objectif : vérifier sur **une installation jetable** que Northflank Sandbox peut
héberger le bot 24/7 avec base persistante, sans carte et sans exposer de secret
réel. Chaque étape est une action distincte, autorisée une à une.

**Règles de qualification (non négociables) :**

- **Jeton de test uniquement** : un bot BotFather jetable, jamais le bot réel ;
- **`publisher = "simulated"`** : aucune publication LinkedIn pendant la
  qualification ; aucune clé Groq/Tavily réelle sur la plateforme au début ;
- **Aucune donnée réelle** : la base qualifiée est jetable, jamais l'archive
  réelle ;
- Si la plateforme exige une carte à une étape : **arrêt immédiat**, verdict
  consigné (critère E2), retour à l'hébergement local.

## Contexte de la décision (17 novembre 2026)

- Docs officielles Northflank (« Pricing on Northflank ») : *« all users must add
  a payment method to start creating resources on Northflank, regardless of plan
  selection »* — conflit avec la page pricing (« No card needed ») ; la réalité
  s'est révélée dépendre du parcours d'inscription.
- Sandbox annoncé : 2 services + 2 jobs + 1 addon, **jusqu'à 20 $/mois de
  ressources**, « Always on, no sleeping », pas destiné à la production.
- Estimation de coût du bot (~0,1–0,5 vCPU + 256–512 Mo RAM, volume ~1 Go) :
  ~3–9 $/mois — dans l'enveloppe gratuite. Estimation, pas une promesse.

## Étapes

1. **Compte** (utilisateur) : création du compte Northflank. **Point de mesure
   E2** : une carte/moyen de paiement est-il exigé à l'inscription ou à la
   création de la première ressource ? Si carte exigée et indisponible ⇒ arrêt.
2. **Région** : `Europe - West` (Londres) — proche, juridiction UE.
3. **Préparation du dépôt** (fait le 17 novembre 2026) : `deploy/Dockerfile` +
   `deploy/entrypoint.py` — la config est générée sur le volume à partir des
   variables `OWNER_ID` / `CHAT_ID` ; `publisher = "simulated"` ;
   base sur `/data/assistant.db`.
4. **Service** : Deploy repository → dépôt GitHub → branche `main` → build via
   `deploy/Dockerfile`. Variables d'environnement à injecter par l'utilisateur
   dans l'UI (jamais dans le dépôt) : `OWNER_ID`, `CHAT_ID` (ID numérique
   Telegram), `TELEGRAM_BOT_TOKEN` (jeton du bot de test).
5. **Volume persistant** : attacher un volume monté sur `/data` (taille
   minimale). **Mesure E5** : la base doit survivre à un redéploiement.
6. **Test runtime** : `/start` au bot de test → réponse du bot en mode
   simulation (note « Mode simulation » affichée). **Mesure E4/E6** : le
   processus tourne, le shell interne n'est pas bloqué (pas de publication
   pendant la qualification, donc treg non sollicité).
7. **Stabilité 24 h** : le service reste actif sans sommeil (aucun spin-down
   après inactivité) ; consommation relevée dans l'UI Northflank et comparée à
   l'estimation (~3–9 $/mois).
8. **Persistance** : redéploiement du service ⇒ `/data/assistant.db` intact
   (vérifier via `/status` du bot : brouillons et paramètres conservés).
   Échec = critère E5 non satisfait ⇒ arrêt.
9. **Décision** : si 1–8 passent, la poursuite (clés réelles, `publisher =
   "treg"`, publication réelle) exige une **autorisation distincte** et se
   traite comme une nouvelle installation (SETUP_GUIDE § 7). Sinon, consigner
   le verdict et rester sur l'hébergement local.

## Retour arrière

Supprimer le projet Northflank (service + volume + jeton de test révoqué via
BotFather `/revoke`). Aucune donnée réelle n'a jamais quitté la machine locale.
