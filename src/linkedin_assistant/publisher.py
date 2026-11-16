from __future__ import annotations

import abc
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

from . import store


class CertainPublicationError(Exception):
    """Rejet documenté sans effet externe : une nouvelle autorisation sera requise."""


class AmbiguousPublicationError(Exception):
    """L'envoi a pu aboutir côté LinkedIn : aucune nouvelle tentative automatique."""


class PublisherError(Exception):
    """Le contrat de publication ne peut pas être honoré (configuration/adaptateur)."""


class Publisher(abc.ABC):
    """Contrat unique des adaptateurs de publication (ADR-04, ADR-16).

    - `post(manifest)` envoie exactement le manifeste validé : aucun texte,
      hashtag, lien ou image ajouté ; aucune transformation cachée après accord.
    - Retour attendu : un `dict` de reçu ; champs optionnels nullables (ID/URL
      jamais inventés). Pour LinkedIn la preuve officielle est l'URN (`urn`),
      jamais une lecture non autorisée ni le scraping.
    - Rejet documenté sans effet externe : lever `CertainPublicationError` ;
      une nouvelle autorisation sera exigée pour une nouvelle tentative.
    - Résultat incertain (timeout, réponse perdue, reçu non conforme) : lever
      `AmbiguousPublicationError` ou `TimeoutError` — le socle verrouille le
      compte et n'effectue JAMAIS de nouvelle tentative automatique.
    - Aucun appel n'est déclenché par le LLM, la recherche ou un rappel ; seule
      la consommation atomique d'une autorisation finale valide un envoi.
    - Aucun nom ni secret en dur : un futur adaptateur treg résoudra la
      connexion LinkedIn health=ok dynamiquement (`resolve_treg_connection`).
    """

    @abc.abstractmethod
    def post(self, manifest: dict) -> dict: ...


class SimulatedPublisher(Publisher):
    """Fournisseur simulé : aucun appel réseau, aucun effet externe.

    `is_real = False` : un échec d'archivage survenu ici ne peut pas
    correspondre à une publication réellement effectuée (aucun appel n'est
    parti) ; il est donc tranché en échec documenté, jamais en résultat
    incertain.
    """

    is_real = False

    def __init__(self, outcome: str = "success", receipt: dict | None = None):
        self.outcome = outcome
        self.receipt = receipt
        self.calls = 0

    def post(self, manifest: dict) -> dict:
        self.calls += 1
        if self.outcome == "success":
            if self.receipt is not None:
                return self.receipt
            # Un URN LinkedIn est unique PAR POST : un identifiant constant
            # heurtait la contrainte UNIQUE(namespace, identifier) dès la
            # deuxième publication de la même base (observé lors d'un test
            # Telegram réel le 16 novembre 2026).
            return {"urn": f"urn:li:share:simulated-{store.new_id()}"}
        if self.outcome == "certain_failure":
            raise CertainPublicationError("refus documenté simulé")
        raise AmbiguousPublicationError("réponse perdue simulée")


def resolve_treg_connection(connections) -> str:
    """Résout dynamiquement la connexion treg LinkedIn saine (ADR-16).

    La rotation périodique de treg révoque les secrets et crée un nouveau nom
    `linkedin-N` à chaque reconnexion : aucun nom ni secret n'est codé en dur.
    Retourne le nom unique de la connexion `provider=linkedin` en `health=ok`.
    Aucune ou plusieurs connexions saines : échec conservateur, aucune cible
    choisie arbitrairement. Fonction pure : aucun appel treg n'est effectué ici.
    """
    healthy: list[str] = []
    for entry in connections or []:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("provider", "")).strip().lower() != "linkedin":
            continue
        health = str(entry.get("health", entry.get("status", ""))).strip().lower()
        if health != "ok":
            continue
        name = entry.get("tool") or entry.get("name") or entry.get("id")
        if name:
            healthy.append(str(name))
    if not healthy:
        raise PublisherError("TREG_CONNECTION_MISSING: aucune connexion linkedin health=ok")
    if len(healthy) > 1:
        raise PublisherError("TREG_CONNECTION_AMBIGUOUS: plusieurs connexions linkedin health=ok")
    return healthy[0]


# Estimation empirique de la portion affichée par le FIL LinkedIn avant le
# « …voir plus ». LinkedIn n'expose aucune constante : selon l'appareil et la
# largeur de colonne, le fil montre environ 2 à 3 lignes (~150 à 300
# caractères) puis tronque avec des points de suspension. 280 est une
# approximation prudente (côté desktop), à traiter comme un ordre de grandeur.
FEED_PREVIEW_LIMIT = 280


def feed_preview(text: str, limit: int = FEED_PREVIEW_LIMIT) -> dict:
    """Estime ce que le fil LinkedIn laisse visibles d'un post.

    Le texte envoyé n'est jamais tronqué par l'API (LinkedIn accepte jusqu'à
    3 000 caractères de `commentary`) : c'est l'AFFICHAGE dans le fil qui
    tronque, en montrant le début puis un « … ». Toute information placée
    après la limite (lien, image décrite en URL, conclusion) est invisible
    jusqu'au clic sur « …voir plus ».

    Retour : {"visible", "hidden", "truncated", "limit", "hidden_chars"}.
    """
    if not isinstance(text, str):
        raise PublisherError("TEXT_INVALID: texte attendu")
    visible = text[:limit]
    hidden = text[limit:]
    return {
        "visible": visible,
        "hidden": hidden,
        "truncated": bool(hidden.strip()),
        "limit": limit,
        "hidden_chars": len(hidden),
    }


class TregPublisher(Publisher):
    """Adaptateur réel de publication LinkedIn via la connexion treg (ADR-16).

    - Aucun OAuth propre, aucun callback local : la connexion treg du membre
      (health=ok, capability write) est résolue dynamiquement à CHAQUE envoi
      (`treg connections ls`), jamais de nom ni de secret en dur.
    - Payload conforme au runbook de qualification (docs/QUALIFICATION_TREG.md) :
      POST /rest/posts, en-têtes LinkedIn-Version et X-Restli-Protocol-Version.
    - `api_version` (YYYYMM) est requis explicitement : aucun choix silencieux.
    - Texte envoyé exactement tel qu'approuvé : aucun échappement ni retouche.
    - Garde-fous fail-closed : `UNCONFIGURED`, texte absent, image, visibilité
      inconnue ou version invalide = `PublisherError`, sans aucun appel.
    - Erreurs : 4xx = `CertainPublicationError` (rejet documenté, sans effet
      externe) ; 5xx, sortie illisible ou délai dépassé = `AmbiguousPublicationError`
      (compte verrouillé, JAMAIS de retry automatique).
    - Preuve : `x-restli-id` lu dans la sortie treg si exposée, sinon `urn=None`
      (jamais inventé). Aucun secret n'est journalisé.
    - Format de sortie OBSERVÉ au premier test réel (15 novembre 2026) :
      `treg --json call ...` renvoie `{"result": ..., "_treg": {"http_status": 201,
      "call_id": ...}}`. Le proxy treg n'expose PAS les en-têtes de réponse :
      l'URN `x-restli-id` n'est donc pas récupérable par ce canal, et reste `None`.
      Le `call_id` est conservé comme trace technique dans le reçu.
    - Une sortie illisible reste traitée comme un résultat INCONNU, jamais comme
      un succès.
    """

    VISIBILITIES = ("PUBLIC", "CONNECTIONS")
    #: Envoi réel : un échec d'archivage local après l'appel laisse le résultat
    #: incertain (UNKNOWN_OUTCOME), verrou du compte, aucun retry automatique.
    is_real = True
    _URN_RE = re.compile(r"x-restli-id\s*[:=]\s*[\"']?(urn:li:[^\s\",}]+)", re.IGNORECASE)
    _STATUS_PATTERNS = (
        r'"status"\s*:\s*(\d{3})',
        r"(?i)\bHTTP(?:/[\d.]+)?\s+(\d{3})\b",
        r"(?im)^\s*(\d{3})\s*$",
    )

    def __init__(self, api_version: str, runner=None, timeout_seconds: float = 60.0, buffer=None):
        if not isinstance(api_version, str) or not re.fullmatch(r"\d{6}", api_version):
            raise PublisherError(
                "API_VERSION_INVALID: LinkedIn-Version attendu au format YYYYMM, choisi explicitement"
            )
        self._api_version = api_version
        self._runner = runner if runner is not None else self._subprocess_runner
        self._timeout = float(timeout_seconds)
        self._buffer = buffer

    @staticmethod
    def _subprocess_runner(cmd: list[str], env: dict, timeout: float):
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=timeout,
        )
        return completed.returncode, completed.stdout, completed.stderr

    @staticmethod
    def _child_env() -> dict:
        env = dict(os.environ)
        env["NO_PROXY"] = ""  # bug machine : NO_PROXY système mal parsé par httpx
        env["TREG_TELEMETRY"] = "0"  # télémétrie treg désactivée
        return env

    def _run(self, cmd: list[str]):
        try:
            return self._runner(cmd, self._child_env(), self._timeout)
        except subprocess.TimeoutExpired as exc:
            raise AmbiguousPublicationError("TREG_TIMEOUT: délai dépassé, résultat de l'envoi inconnu") from exc

    def _resolve_connection(self) -> str:
        code, out, err = self._run(["treg", "connections", "ls"])
        if code != 0:
            raise PublisherError(f"TREG_LS_FAILED: treg connections ls a échoué (code {code})")
        try:
            connections = json.loads(out)
        except json.JSONDecodeError as exc:
            raise PublisherError("TREG_LS_UNREADABLE: sortie non JSON") from exc
        if not isinstance(connections, list):
            raise PublisherError("TREG_LS_UNREADABLE: tableau JSON attendu")
        return resolve_treg_connection(connections)

    @staticmethod
    def _write_payload(payload: dict) -> str:
        """Écrit le payload JSON dans un fichier temporaire, supprimé après l'appel.

        Le texte est déjà archivé localement dans SQLite ; ce fichier n'est ni
        versionné ni conservé. Un binaire d'image ne passe jamais par ici.

        Écriture en ASCII pur (`ensure_ascii=True`) : les caractères non ASCII
        (accents, emoji) sont sérialisés en séquences `\\uXXXX`, donc le fichier
        ne dépend d'aucun encodage local. Le texte transmis est sémantiquement
        identique, mais immune au décalage cp1252/UTF-8 constaté sur cette
        machine (cause possible de texte corrompu ou tronqué en amont).
        """
        handle = tempfile.NamedTemporaryFile(
            mode="w", encoding="ascii", suffix=".json", prefix="linkedin_post_", delete=False
        )
        with handle as fh:
            json.dump(payload, fh, ensure_ascii=True)
        return handle.name

    def post(self, manifest: dict) -> dict:
        if not isinstance(manifest, dict):
            raise PublisherError("MANIFEST_INVALID: dict attendu")
        account = manifest.get("account")
        if not isinstance(account, str) or not account.strip() or account == "urn:li:person:UNCONFIGURED":
            raise PublisherError("LINKEDIN_ACCOUNT_UNCONFIGURED: publication refusée sans URN de membre vérifié")
        text = manifest.get("text")
        if not isinstance(text, str) or not text.strip():
            raise PublisherError("MANIFEST_TEXT_MISSING: texte exact approuvé requis")
        if manifest.get("image_hash"):
            raise PublisherError(
                "IMAGE_NOT_UPLOADED: image non matérialisée ; utiliser manifest['image'] "
                "puis upload_image() avant publication"
            )
        visibility = manifest.get("visibility") or "PUBLIC"
        if visibility not in self.VISIBILITIES:
            raise PublisherError(f"VISIBILITY_INVALID: {visibility!r} hors {self.VISIBILITIES}")
        # Prévention : le fil LinkedIn tronque l'affichage des posts longs.
        # On signale ce qui sera masqué AVANT l'envoi (stderr uniquement, aucun
        # secret, aucune modification du texte envoyé).
        preview = feed_preview(text)
        if preview["truncated"]:
            hidden_links = re.findall(r"https?://\S+", preview["hidden"])
            detail = (
                f" ; liens dans la zone masquée : {', '.join(hidden_links)}" if hidden_links else ""
            )
            print(
                f"[apercu fil] {preview['hidden_chars']} caractères seront masqués par l'aperçu "
                f"LinkedIn (limite ~{preview['limit']}) : tout ce qui suit cette limite "
                f"(liens, conclusion) reste invisible jusqu'au clic sur « …voir plus »{detail}.",
                file=sys.stderr,
            )
        payload = {
            "author": account,
            "commentary": text,
            "visibility": visibility,
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }
        media = manifest.get("media")
        planned = manifest.get("image")
        if planned and not media:
            # Image approuvée mais pas encore téléversée : le téléversement
            # officiel a lieu ICI, après consommation de l'autorisation finale
            # (donc jamais avant), et seulement si les octets approuvés sont
            # encore en RAM.
            media = self._upload_planned_image(planned, account)
        content = self._build_content(media)
        if content:
            payload["content"] = content
        connection = self._resolve_connection()
        path = self._write_payload(payload)
        try:
            cmd = [
                "treg",
                "--json",
                "call",
                connection,
                "rest/posts",
                "--method",
                "POST",
                "--header",
                f"LinkedIn-Version: {self._api_version}",
                "--header",
                "X-Restli-Protocol-Version: 2.0.0",
                "--content-type",
                "application/json",
                "--data",
                f"@{path}",
            ]
            code, out, err = self._run(cmd)
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
        return self._interpret(code, out, err)

    @classmethod
    def _find_status(cls, text: str) -> int | None:
        found: list[int] = []
        for pattern in cls._STATUS_PATTERNS:
            match = re.search(pattern, text)
            if match:
                found.append(int(match.group(1)))
        if not found:
            return None
        if len(set(found)) > 1:
            return None  # statuts contradictoires dans la sortie : incertitude
        return found[0]

    @staticmethod
    def _build_content(media) -> dict | None:
        """Construit le bloc `content` de la Posts API à partir d'un média déjà téléversé.

        - 1 image  -> `content.media` {id, altText}
        - n images -> `content.multiImage` {images:[{id, altText}]}

        Les URN d'image proviennent de `upload_image()` : aucune URL d'image
        brute n'est envoyée à LinkedIn (elles ne sont jamais rendues en image
        dans un post, seulement comme texte).
        """
        if not media:
            return None
        if not isinstance(media, dict):
            raise PublisherError("MEDIA_INVALID: dict attendu")
        images = media.get("images")
        if images:
            if not isinstance(images, list) or not images:
                raise PublisherError("MEDIA_INVALID: liste d'images invalide")
            entries = []
            for image in images:
                if not isinstance(image, dict) or not image.get("id"):
                    raise PublisherError("MEDIA_INVALID: URN d'image manquant")
                entry = {"id": image["id"]}
                if image.get("altText"):
                    entry["altText"] = image["altText"]
                entries.append(entry)
            return {"multiImage": {"images": entries}}
        if media.get("id"):
            block = {"id": media["id"]}
            if media.get("altText"):
                block["altText"] = media["altText"]
            return {"media": block}
        raise PublisherError("MEDIA_INVALID: ni 'id' ni 'images' exploitable")

    def _upload_planned_image(self, planned: dict, owner: str) -> dict:
        """Téléverse l'image approuvée (octets en RAM) et renvoie son URN.

        Refus fail-closed : pas de tampon, image perdue (redémarrage) ou
        empreinte absente des octets ⇒ aucun appel externe, aucune
        publication. L'image n'est jamais inventée ni remplacée.
        """
        if self._buffer is None:
            raise PublisherError("IMAGE_BUFFER_ABSENT: aucun tampon d'image disponible")
        token = planned.get("token")
        asset = self._buffer.get(token)
        if asset is None:
            raise PublisherError(
                "IMAGE_BUFFER_LOST: image perdue (redémarrage du bot) ; "
                "renvoie l'image puis relance /preview"
            )
        expected = planned.get("sha256")
        if expected and expected != asset.sha256:
            raise PublisherError(
                "IMAGE_MISMATCH: les octets en mémoire ne correspondent pas à l'image approuvée"
            )
        return self.upload_image(
            asset.data,
            owner=owner,
            content_type=asset.content_type,
            alt_text=asset.alt_text or planned.get("alt_text"),
        )

    def upload_image(self, content: bytes, owner: str, content_type: str = "image/png",
                     alt_text: str | None = None) -> dict:
        """Téléverse une image (RAM seule) et renvoie son URN LinkedIn.

        Parcours officiel documenté (runbook docs/QUALIFICATION_TREG.md) :
        1. `POST /rest/images?action=initializeUpload` avec le propriétaire
           (URN de membre) -> URL de téléversement pré-signée + URN d'image ;
        2. `PUT` des octets sur l'URL pré-signée (aucun secret local, aucun
           jeton transmis) ;
        3. l'URN retourné est référencé dans `content.media`/`content.multiImage`.

        Les octets ne sont écrits NI sur disque NI en base : ils restent en RAM
        pendant l'appel. Aucun échec de téléversement ne crée de publication.
        """
        if not isinstance(content, (bytes, bytearray)) or not content:
            raise PublisherError("IMAGE_CONTENT_MISSING: octets d'image requis")
        if not isinstance(owner, str) or not owner.strip() or owner == "urn:li:person:UNCONFIGURED":
            raise PublisherError("LINKEDIN_ACCOUNT_UNCONFIGURED: téléversement refusé sans URN de membre")
        body = {"initializeUploadRequest": {"owner": owner}}
        cmd = [
            "treg",
            "--json",
            "call",
            self._resolve_connection(),
            "rest/images",
            "--method",
            "POST",
            "--query",
            "action=initializeUpload",
            "--header",
            f"LinkedIn-Version: {self._api_version}",
            "--header",
            "X-Restli-Protocol-Version: 2.0.0",
            "--content-type",
            "application/json",
            "--data",
            json.dumps(body, ensure_ascii=True),
        ]
        code, out, err = self._run(cmd)
        payload = self._parse_json(out)
        upload_url, image_urn = self._extract_upload(payload)
        if not upload_url or not image_urn:
            raise PublisherError(
                f"IMAGE_INIT_FAILED: initializeUpload sans uploadUrl/URN exploitables (code {code})"
            )
        self._put_binary(upload_url, bytes(content), content_type)
        result = {"id": image_urn}
        if alt_text:
            result["altText"] = alt_text
        return result

    @staticmethod
    def _parse_json(out: str):
        """Extrait le corps utile de la sortie `treg --json` (objet ou chaîne JSON)."""
        try:
            envelope = json.loads(out.strip())
        except (json.JSONDecodeError, ValueError):
            return None
        if not isinstance(envelope, dict):
            return None
        result = envelope.get("result")
        if isinstance(result, str):
            try:
                return json.loads(result)
            except (json.JSONDecodeError, ValueError):
                return result
        return result

    @classmethod
    def _extract_upload(cls, payload):
        """Retrouve `uploadUrl` et l'URN d'image dans une réponse initializeUpload."""
        upload_url = None
        image_urn = None

        def walk(node):
            nonlocal upload_url, image_urn
            if isinstance(node, dict):
                for key, value in node.items():
                    normalized = str(key).replace("_", "").lower()
                    if normalized == "uploadurl" and isinstance(value, str) and value.startswith("http"):
                        upload_url = value
                    elif isinstance(value, str) and value.startswith("urn:li:image"):
                        image_urn = value
                    else:
                        walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(payload)
        return upload_url, image_urn

    @staticmethod
    def _put_binary(url: str, data: bytes, content_type: str) -> None:
        """PUT des octets sur l'URL pré-signée (RAM seule, aucun secret local)."""
        request = urllib.request.Request(
            url, data=data, method="PUT", headers={"Content-Type": content_type}
        )
        openers = [
            urllib.request.build_opener(urllib.request.ProxyHandler({})),
            urllib.request.build_opener(),
        ]
        last_error = None
        for opener in openers:
            try:
                with opener.open(request, timeout=60) as response:
                    status = getattr(response, "status", None) or response.getcode()
                if status not in (200, 201, 202, 204):
                    raise PublisherError(f"IMAGE_UPLOAD_HTTP_{status}: téléversement refusé")
                return
            except urllib.error.HTTPError as exc:
                raise PublisherError(f"IMAGE_UPLOAD_HTTP_{exc.code}: téléversement refusé") from exc
            except urllib.error.URLError as exc:
                last_error = exc
            except OSError as exc:
                last_error = exc
        raise PublisherError(f"IMAGE_UPLOAD_FAILED: {last_error}")

    @classmethod
    def _interpret(cls, code: int, out: str, err: str) -> dict:
        combined = f"{out}\n{err}"
        status = None
        call_id = None
        try:
            envelope = json.loads(out.strip())
        except (json.JSONDecodeError, ValueError):
            envelope = None
        if isinstance(envelope, dict):
            meta = envelope.get("_treg")
            if isinstance(meta, dict):
                raw_status = meta.get("http_status")
                if isinstance(raw_status, int):
                    status = raw_status
                raw_call = meta.get("call_id")
                if isinstance(raw_call, str):
                    call_id = raw_call
        if status is None:
            status = cls._find_status(combined)
        urn_match = cls._URN_RE.search(combined)
        urn = urn_match.group(1) if urn_match else None
        if status is None:
            raise AmbiguousPublicationError(
                "RECEIPT_UNREADABLE: statut HTTP absent ou ambigu dans la sortie treg"
            )
        if status == 201:
            receipt = {"urn": urn, "http_status": 201}
            if call_id:
                receipt["call_id"] = call_id
            return receipt
        if 200 <= status < 300:
            raise AmbiguousPublicationError(f"RECEIPT_NON_CONFORME: HTTP {status} alors que 201 est attendu")
        if 400 <= status < 500:
            raise CertainPublicationError(
                f"LINKEDIN_HTTP_{status}: rejet documenté par LinkedIn, aucune publication créée"
            )
        raise AmbiguousPublicationError(f"LINKEDIN_HTTP_{status}: résultat incertain, aucune nouvelle tentative")


def publish(conn: sqlite3.Connection, intent_id: str, adapter, now: str | None = None) -> str:
    intent = conn.execute("SELECT * FROM publication_intents WHERE id = ?", (intent_id,)).fetchone()
    if intent is None:
        raise store.StoreError("INTENT_NOT_FOUND", intent_id)
    version = conn.execute(
        "SELECT v.manifest_json FROM draft_versions v JOIN drafts d ON d.id = v.draft_id AND d.current_revision = v.revision WHERE d.id = ?",
        (intent["draft_id"],),
    ).fetchone()
    manifest = store._loads(version["manifest_json"])
    store.mark_sending(conn, intent_id, now)
    try:
        receipt = adapter.post(manifest)
        if not isinstance(receipt, dict):
            raise AmbiguousPublicationError("reçu non conforme au contrat Publisher (dict attendu)")
    except CertainPublicationError as exc:
        store.record_failure(conn, intent_id, str(exc), now)
        return "FAILED"
    except (AmbiguousPublicationError, TimeoutError) as exc:
        store.mark_unknown(conn, intent_id, str(exc), now)
        return "UNKNOWN_OUTCOME"
    except PublisherError as exc:
        # Erreur de configuration/adaptateur (ex. UNCONFIGURED, image non supporté) :
        # refus local sans aucun effet externe, enregistrement d'échec documenté.
        store.record_failure(conn, intent_id, str(exc), now)
        return "FAILED"
    try:
        store.record_success(conn, intent_id, receipt, now)
    except Exception as exc:  # noqa: BLE001
        # L'envoi a pu aboutir : c'est l'ARCHIVAGE local de la preuve qui a
        # échoué. Le compte reste verrouillé, aucun retry automatique,
        # réconciliation explicite requise (règle « timeout après envoi »).
        reason = f"archivage local de la preuve impossible après envoi : {exc}"
        if getattr(adapter, "is_real", True):
            store.mark_unknown(conn, intent_id, reason, now)
            return "UNKNOWN_OUTCOME"
        store.record_failure(conn, intent_id, reason, now)
        return "FAILED"
    return "PUBLISHED"


def build_publisher(config, buffer=None) -> Publisher:
    """Construit l'adaptateur de publication selon la configuration locale.

    - `publisher = "simulated"` : aucun appel externe (apprentissage, tests).
    - `publisher = "treg"` : publication réelle via la connexion treg résolue
      dynamiquement ; `linkedin_api_version` est obligatoire (choix explicite
      de la version d'API, jamais un choix silencieux).

    Aucun repli silencieux : si la configuration demande `treg`, l'adaptateur
    treg est construit ou le démarrage échoue avec un message explicite.
    """
    mode = str(getattr(config, "publisher", "simulated")).strip().lower()
    if mode == "treg":
        return TregPublisher(getattr(config, "linkedin_api_version", ""), buffer=buffer)
    return SimulatedPublisher()
