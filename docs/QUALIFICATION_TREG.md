# Runbook de qualification treg — `/rest/posts` et parcours image

Date : 14 novembre 2026. **Statut : préparation uniquement — RIEN dans ce document n'a été exécuté.** Chaque étape réelle exige une autorisation distincte de l'utilisateur, sur l'action ET le contenu exact. Contexte : [ADR-16](ARCHITECTURE_DECISIONS.md), [API_INTEGRATIONS.md §2](API_INTEGRATIONS.md).

## État préalable (attesté, ne pas refaire sans nécessité)

- Connexion treg `linkedin` health=ok, capability `write`, consentement navigateur utilisateur.
- Identité vérifiée : `treg call linkedin v2/userinfo` → 200 (sub membre, `w_member_social`, expiration 2027-01-13).
- Catalogue attesté (lecture, 0 $) : `linkedin.linkedin.user.post.create` → `POST https://api.linkedin.com/rest/posts`.
- Crédit d'essai treg : 1,00 $ initial, reste 0,9921 $ au 14 nov — **la publication est 0 $, ne pas appeler les endpoints mesurés** (`treg.linkedin.user.posts`, `treg.linkedin.post.detail`, `treg.google.serp.organic`).

## Rappel machine (à chaque commande treg)

- Préfixer `NO_PROXY=` (vide) : le `NO_PROXY` système contient `[::1],::1` mal parsé par httpx, qui fait planter toute commande.
- Télémétrie désactivée : `TREG_TELEMETRY=0`.
- Aucun secret dans la ligne de commande, un log ou un message Telegram.

## Étape 1 — Qualification texte seul (Phase 6, premier test réel)

Prérequis d'autorisation : contenu du post de test choisi et approuvé par l'utilisateur (portée PUBLIC ou CONNECTIONS annoncée ; coût 0 $ annoncé ; publication sur le profil personnel).

1. Créer `post.json` (fichier local, jamais versionné) :
   ```json
   {
     "author": "urn:li:person:UkLKzuK9bT",
     "commentary": "Texte exact approuvé par l'utilisateur (échapper ( ) [ ] { } < > @ | ~ avec backslash).",
     "visibility": "PUBLIC",
     "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
     "lifecycleState": "PUBLISHED",
     "isReshareDisabledByAuthor": false
   }
   ```
2. Commande :
   ```
   NO_PROXY= TREG_TELEMETRY=0 treg call linkedin rest/posts --method POST \
     --header "LinkedIn-Version: <YYYYMM supporté, choisi explicitement>" \
     --header "X-Restli-Protocol-Version: 2.0.0" \
     --data '@post.json'
   ```
3. Preuve attendue : **HTTP 201, URN dans l'en-tête `x-restli-id`, corps vide**. Conserver l'URN dans l'archive locale (source A) ; ne pas fabriquer de permalien ; la publication de confirmation Telegram n'est pas une reprise.
4. En cas de 4xx : rejet documenté (pas de retry automatique) ; 401 ⇒ rotation/réconnexion treg (`treg connections connect --provider linkedin --capability write`, consentement navigateur) puis `treg connections ls` pour résoudre le nouveau `linkedin-N`.
5. Échec = capacité non activée ; aucune bascule vers une voie non officielle.

## Étape 2 — Qualification image (Phase 7, après étape 1)

1. `initializeUpload` (`POST /rest/images?action=initializeUpload`, propriétaire membre) → URL de téléversement pré-signée.
2. Envoi du fichier exact (PNG/JPG/GIF, ≤ 8 Mo selon catalogue — à vérifier au test) :
   `curl.exe -X PUT --upload-file fichier.png "<uploadUrl>"` — **pas Invoke-WebRequest**.
3. Référence dans le post : `content.media{id}` (1 image) ou `content.multiImage{images:[{id,altText}]}` (2+) ; **422 sur multiImage ⇒ repli `media`** (image unique), jamais de retry aveugle.
4. `w_member_social` seul ne permet pas le GET versionné du statut image : ne pas implémenter de polling. Le fichier est approuvé au préalable (empreinte) ; aucun binaire persisté (RAM seule).

## Critères de fin de qualification

- [ ] Un POST texte autorisé → 201 + URN conservés, archive atomique vérifiée.
- [ ] Version `LinkedIn-Version` supportée consignée avec date.
- [ ] Un upload image autorisé → référence média ; publication avec image éprouvée (ou limite documentée).
- [ ] Résolution dynamique `treg connections ls` validée après une rotation.
- [ ] Aucun endpoint treg mesuré appelé ; solde inchangé.

## Interdits permanents

Navigateur/cookies, scraping, contournement d'un refus, endpoint mesuré sans autorisation, publication sans accord explicite sur le contenu exact, retry automatique après `UNKNOWN_OUTCOME`.
