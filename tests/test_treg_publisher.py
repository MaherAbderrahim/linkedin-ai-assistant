"""Tests de l'adaptateur réel TregPublisher — aucun appel treg effectué.

Tous les tests injectent un runner factice : aucun processus treg, aucun
réseau. Le format de sortie réel de `treg call` reste à confirmer au premier
test autorisé (runbook docs/QUALIFICATION_TREG.md) ; une sortie illisible est
traitée comme un résultat inconnu, jamais comme un succès.
"""

import json
import os
import subprocess

import pytest

from linkedin_assistant import store
from linkedin_assistant.publisher import (
    FEED_PREVIEW_LIMIT,
    AmbiguousPublicationError,
    CertainPublicationError,
    PublisherError,
    TregPublisher,
    feed_preview,
    publish,
)
from conftest import ACCOUNT, approved_draft


CONNECTIONS_OK = json.dumps([{"tool": "linkedin-2", "provider": "linkedin", "health": "ok"}])
CONNECTIONS_NONE = json.dumps([])
CONNECTIONS_TWO = json.dumps(
    [
        {"tool": "linkedin-2", "provider": "linkedin", "health": "ok"},
        {"tool": "linkedin-3", "provider": "linkedin", "health": "ok"},
    ]
)

TEXT_EXACT = "Bonjour LinkedIn. (test) [crochets] {accolades} <chevrons> @arobase | barre ~ tilde émoji 🙂"


class FakeRunner:
    """Runner factice : enregistre les commandes, lit le payload, sorties fixées."""

    def __init__(self, outputs, errors=None):
        self.outputs = list(outputs)
        self.errors = list(errors or [])
        self.calls = []
        self.envs = []
        self.payloads = []
        self.raw_payloads = []

    def __call__(self, cmd, env, timeout):
        self.calls.append(list(cmd))
        self.envs.append(dict(env))
        if self.errors:
            raise self.errors.pop(0)
        code, out, err = self.outputs.pop(0)
        if cmd[:3] == ["treg", "connections", "ls"]:
            return code, out, err
        data_arg = cmd[cmd.index("--data") + 1]
        if data_arg.startswith("@"):
            # Payload écrit dans un fichier temporaire : lu pendant l'appel,
            # car le fichier est supprimé juste après.
            with open(data_arg[1:], "rb") as fh:
                raw = fh.read()
            self.raw_payloads.append(raw)
            self.payloads.append(json.loads(raw.decode("ascii")))
        else:
            raw = data_arg.encode("ascii")
            self.raw_payloads.append(raw)
            self.payloads.append(json.loads(data_arg))
        return code, out, err


def make_manifest(text: str = TEXT_EXACT, account: str = ACCOUNT, visibility: str = "PUBLIC",
                  image_hash=None, image=None) -> dict:
    manifest = {"account": account, "visibility": visibility, "text": text}
    if image_hash is not None:
        manifest["image_hash"] = image_hash
    if image is not None:
        manifest["image"] = image
    return manifest


def make_adapter(runner: FakeRunner) -> TregPublisher:
    return TregPublisher(api_version="202501", runner=runner)


# --- garde-fous locaux : aucun appel n'est déclenché -----------------------


def test_api_version_must_be_explicit_yyyy_mm():
    with pytest.raises(PublisherError):
        TregPublisher(api_version="2025-01")
    with pytest.raises(PublisherError):
        TregPublisher(api_version="")
    with pytest.raises(PublisherError):
        TregPublisher(api_version=None)


def test_unconfigured_account_refused_without_any_call():
    runner = FakeRunner([])
    with pytest.raises(PublisherError) as exc:
        make_adapter(runner).post(make_manifest(account="urn:li:person:UNCONFIGURED"))
    assert "LINKEDIN_ACCOUNT_UNCONFIGURED" in str(exc.value)
    assert runner.calls == []


def test_missing_text_refused_without_any_call():
    runner = FakeRunner([])
    with pytest.raises(PublisherError) as exc:
        make_adapter(runner).post(make_manifest(text=""))
    assert "MANIFEST_TEXT_MISSING" in str(exc.value)
    assert runner.calls == []


def test_blank_text_refused_without_any_call():
    runner = FakeRunner([])
    with pytest.raises(PublisherError):
        make_adapter(runner).post(make_manifest(text="   "))
    assert runner.calls == []


def test_image_manifest_refused_without_any_call():
    runner = FakeRunner([])
    with pytest.raises(PublisherError) as exc:
        make_adapter(runner).post(make_manifest(image_hash="abc123"))
    assert "IMAGE_NOT_UPLOADED" in str(exc.value)
    assert runner.calls == []


def test_image_reference_refused_without_any_call():
    runner = FakeRunner([])
    with pytest.raises(PublisherError):
        make_adapter(runner).post(make_manifest(image={"id": "x"}))
    assert runner.calls == []


def test_invalid_visibility_refused_without_any_call():
    runner = FakeRunner([])
    with pytest.raises(PublisherError) as exc:
        make_adapter(runner).post(make_manifest(visibility="FRIENDS"))
    assert "VISIBILITY_INVALID" in str(exc.value)
    assert runner.calls == []


# --- résolution dynamique de la connexion treg -----------------------------


def test_no_healthy_connection_fails_closed():
    runner = FakeRunner([(0, CONNECTIONS_NONE, "")])
    with pytest.raises(PublisherError) as exc:
        make_adapter(runner).post(make_manifest())
    assert "TREG_CONNECTION_MISSING" in str(exc.value)
    assert len(runner.calls) == 1  # seule la résolution a été appelée
    assert runner.payloads == []


def test_two_healthy_connections_fail_closed():
    runner = FakeRunner([(0, CONNECTIONS_TWO, "")])
    with pytest.raises(PublisherError) as exc:
        make_adapter(runner).post(make_manifest())
    assert "TREG_CONNECTION_AMBIGUOUS" in str(exc.value)
    assert runner.payloads == []


def test_connections_ls_failure_fails_closed():
    runner = FakeRunner([(1, "", "boom")])
    with pytest.raises(PublisherError) as exc:
        make_adapter(runner).post(make_manifest())
    assert "TREG_LS_FAILED" in str(exc.value)
    assert runner.payloads == []


def test_connections_ls_unreadable_fails_closed():
    runner = FakeRunner([(0, "pas du json", "")])
    with pytest.raises(PublisherError) as exc:
        make_adapter(runner).post(make_manifest())
    assert "TREG_LS_UNREADABLE" in str(exc.value)
    assert runner.payloads == []


# --- envoi conforme au runbook --------------------------------------------


def test_success_returns_receipt_and_exact_payload():
    runner = FakeRunner(
        [
            (0, CONNECTIONS_OK, ""),
            (0, '{"result":"", "_treg":{"http_status":201,"call_id":"d5d046ec-test"}}', ""),
        ]
    )
    receipt = make_adapter(runner).post(make_manifest())
    # Format réel observé le 15 nov. 2026 : l'URN `x-restli-id` n'est PAS
    # exposé par le proxy treg -> urn=None (jamais inventé), call_id = trace.
    assert receipt == {"urn": None, "http_status": 201, "call_id": "d5d046ec-test"}

    assert len(runner.calls) == 2
    connections_cmd, call_cmd = runner.calls
    assert connections_cmd == ["treg", "connections", "ls"]
    assert call_cmd[:4] == ["treg", "--json", "call", "linkedin-2"]
    assert call_cmd[4] == "rest/posts"
    assert call_cmd[call_cmd.index("--method") + 1] == "POST"
    assert "LinkedIn-Version: 202501" in call_cmd
    assert "X-Restli-Protocol-Version: 2.0.0" in call_cmd
    assert "application/json" in call_cmd

    payload = runner.payloads[0]
    assert payload["author"] == ACCOUNT
    # Texte exact approuvé : aucun échappement ni retouche ajoutés.
    assert payload["commentary"] == TEXT_EXACT
    assert payload["visibility"] == "PUBLIC"
    assert payload["distribution"] == {
        "feedDistribution": "MAIN_FEED",
        "targetEntities": [],
        "thirdPartyDistributionChannels": [],
    }
    assert payload["lifecycleState"] == "PUBLISHED"
    assert payload["isReshareDisabledByAuthor"] is False

    # Le fichier payload temporaire est supprimé après l'appel.
    data_path = call_cmd[call_cmd.index("--data") + 1]
    assert data_path.startswith("@")
    assert not os.path.exists(data_path[1:])

    # Environnement enfant : préfixes obligatoires, télémétrie désactivée.
    for env in runner.envs:
        assert env["NO_PROXY"] == ""
        assert env["TREG_TELEMETRY"] == "0"


def test_connections_visibility():
    runner = FakeRunner(
        [
            (0, CONNECTIONS_OK, ""),
            (0, "HTTP 201\n", ""),
        ]
    )
    receipt = make_adapter(runner).post(make_manifest(visibility="CONNECTIONS"))
    assert receipt["http_status"] == 201
    assert runner.payloads[0]["visibility"] == "CONNECTIONS"


def test_201_without_urn_header_yields_null_urn():
    runner = FakeRunner([(0, CONNECTIONS_OK, ""), (0, "HTTP 201\n", "")])
    receipt = make_adapter(runner).post(make_manifest())
    assert receipt == {"urn": None, "http_status": 201}


def test_urn_header_is_captured_when_exposed():
    runner = FakeRunner(
        [
            (0, CONNECTIONS_OK, ""),
            (0, 'HTTP 201\nx-restli-id: urn:li:share:abc123\n', ""),
        ]
    )
    receipt = make_adapter(runner).post(make_manifest())
    assert receipt == {"urn": "urn:li:share:abc123", "http_status": 201}


def test_json_envelope_error_status_is_documented_rejection():
    runner = FakeRunner(
        [
            (0, CONNECTIONS_OK, ""),
            (0, '{"result":"AUTHORIZATION_ERROR","_treg":{"http_status":403,"call_id":"x"}}', ""),
        ]
    )
    with pytest.raises(CertainPublicationError) as exc:
        make_adapter(runner).post(make_manifest())
    assert "LINKEDIN_HTTP_403" in str(exc.value)


def test_json_envelope_without_status_is_unknown_outcome():
    runner = FakeRunner([(0, CONNECTIONS_OK, ""), (0, '{"result":"","_treg":{}}', "")])
    with pytest.raises(AmbiguousPublicationError) as exc:
        make_adapter(runner).post(make_manifest())
    assert "RECEIPT_UNREADABLE" in str(exc.value)


# --- interprétation des réponses : aucune réussite simulée -----------------


@pytest.mark.parametrize("status", [400, 401, 403, 422, 429])
def test_client_errors_are_documented_rejections(status):
    runner = FakeRunner([(0, CONNECTIONS_OK, ""), (0, f"HTTP {status}\n", "")])
    with pytest.raises(CertainPublicationError) as exc:
        make_adapter(runner).post(make_manifest())
    assert f"LINKEDIN_HTTP_{status}" in str(exc.value)


@pytest.mark.parametrize("status", [500, 502, 503])
def test_server_errors_are_uncertain_outcomes(status):
    runner = FakeRunner([(0, CONNECTIONS_OK, ""), (0, f"HTTP {status}\n", "")])
    with pytest.raises(AmbiguousPublicationError) as exc:
        make_adapter(runner).post(make_manifest())
    assert f"LINKEDIN_HTTP_{status}" in str(exc.value)


def test_unexpected_2xx_is_not_a_success():
    runner = FakeRunner([(0, CONNECTIONS_OK, ""), (0, "HTTP 200\n", "")])
    with pytest.raises(AmbiguousPublicationError) as exc:
        make_adapter(runner).post(make_manifest())
    assert "RECEIPT_NON_CONFORME" in str(exc.value)


def test_unreadable_output_is_unknown_outcome_never_success():
    runner = FakeRunner([(0, CONNECTIONS_OK, ""), (0, "bonjour", "")])
    with pytest.raises(AmbiguousPublicationError) as exc:
        make_adapter(runner).post(make_manifest())
    assert "RECEIPT_UNREADABLE" in str(exc.value)


def test_conflicting_status_is_unknown_outcome():
    runner = FakeRunner([(0, CONNECTIONS_OK, ""), (0, "HTTP 201\n400\n", "")])
    with pytest.raises(AmbiguousPublicationError):
        make_adapter(runner).post(make_manifest())


def test_timeout_is_unknown_outcome():
    runner = FakeRunner([], errors=[subprocess.TimeoutExpired(cmd="treg", timeout=60)])
    with pytest.raises(AmbiguousPublicationError) as exc:
        make_adapter(runner).post(make_manifest())
    assert "TREG_TIMEOUT" in str(exc.value)


# --- intégration avec la machine à états publish() -------------------------


def test_publish_flow_records_success_and_urn(conn):
    draft_id, revision, final = approved_draft(conn)
    intent_id = store.consume_final_and_create_intent(conn, final, "owner")
    runner = FakeRunner(
        [
            (0, CONNECTIONS_OK, ""),
            (0, '{"result":"", "_treg":{"http_status":201,"call_id":"flow-ok"}}', ""),
        ]
    )
    result = publish(conn, intent_id, make_adapter(runner))
    assert result == "PUBLISHED"
    intent = conn.execute("SELECT state FROM publication_intents WHERE id = ?", (intent_id,)).fetchone()
    assert intent["state"] == "PUBLISHED"
    # Aucun URN exposé par treg -> aucun identifiant inventé dans l'archive.
    urns = conn.execute("SELECT identifier FROM history_identifiers WHERE namespace = 'linkedin_urn'").fetchall()
    assert urns == []
    receipt = conn.execute("SELECT receipt_json FROM publication_intents WHERE id = ?", (intent_id,)).fetchone()
    assert "201" in receipt["receipt_json"]
    assert "flow-ok" in receipt["receipt_json"]
    draft = conn.execute("SELECT state FROM drafts WHERE id = ?", (draft_id,)).fetchone()
    assert draft["state"] == "PUBLISHED"


def test_publisher_error_records_failure_without_network_call(conn):
    draft_id, revision, final = approved_draft(conn, account="urn:li:person:UNCONFIGURED")
    intent_id = store.consume_final_and_create_intent(conn, final, "owner")
    runner = FakeRunner([])
    result = publish(conn, intent_id, make_adapter(runner))
    assert result == "FAILED"
    intent = conn.execute("SELECT state FROM publication_intents WHERE id = ?", (intent_id,)).fetchone()
    assert intent["state"] == "FAILED"
    draft = conn.execute("SELECT state, blocked_reason FROM drafts WHERE id = ?", (draft_id,)).fetchone()
    assert draft["state"] == "BLOCKED"
    assert draft["blocked_reason"] == "publication_failed"
    assert runner.calls == []  # aucun appel treg, aucun envoi


# --- parcours média (initializeUpload + PUT) -------------------------------

INIT_OK = json.dumps(
    {
        "result": {
            "value": {
                "uploadUrl": "https://upload.example.invalid/presigned",
                "image": "urn:li:image:abc123",
            }
        },
        "_treg": {"http_status": 201, "call_id": "init-1"},
    }
)


class FakeUploader:
    """Capture les PUT pré-signés au lieu de toucher le réseau."""

    def __init__(self, status: int = 200):
        self.status = status
        self.calls = []

    def __call__(self, url, data, content_type):
        self.calls.append((url, data, content_type))
        return self.status


def test_upload_image_initializes_and_puts_bytes(monkeypatch):
    runner = FakeRunner([(0, CONNECTIONS_OK, ""), (0, INIT_OK, "")])
    uploader = FakeUploader()
    monkeypatch.setattr(TregPublisher, "_put_binary", staticmethod(uploader))
    adapter = make_adapter(runner)
    result = adapter.upload_image(b"\x89PNG\r\n\x1a\nDATA", owner=ACCOUNT, alt_text="Capture")
    assert result == {"id": "urn:li:image:abc123", "altText": "Capture"}
    assert len(runner.calls) == 2
    init_cmd = runner.calls[1]
    assert init_cmd[:4] == ["treg", "--json", "call", "linkedin-2"]
    assert init_cmd[4] == "rest/images"
    assert "action=initializeUpload" in init_cmd
    assert init_cmd[init_cmd.index("--method") + 1] == "POST"
    assert uploader.calls[0][0] == "https://upload.example.invalid/presigned"
    assert uploader.calls[0][1] == b"\x89PNG\r\n\x1a\nDATA"
    assert uploader.calls[0][2] == "image/png"


def test_upload_image_refuses_empty_content():
    runner = FakeRunner([])
    with pytest.raises(PublisherError) as exc:
        make_adapter(runner).upload_image(b"", owner=ACCOUNT)
    assert "IMAGE_CONTENT_MISSING" in str(exc.value)
    assert runner.calls == []


def test_upload_image_refuses_unconfigured_owner():
    runner = FakeRunner([])
    with pytest.raises(PublisherError) as exc:
        make_adapter(runner).upload_image(b"DATA", owner="urn:li:person:UNCONFIGURED")
    assert "LINKEDIN_ACCOUNT_UNCONFIGURED" in str(exc.value)
    assert runner.calls == []


def test_upload_image_without_upload_url_fails_closed():
    runner = FakeRunner(
        [
            (0, CONNECTIONS_OK, ""),
            (0, '{"result":{"value":{"image":"urn:li:image:abc"}},"_treg":{"http_status":201}}', ""),
        ]
    )
    with pytest.raises(PublisherError) as exc:
        make_adapter(runner).upload_image(b"DATA", owner=ACCOUNT)
    assert "IMAGE_INIT_FAILED" in str(exc.value)


def test_post_with_multi_image_payload():
    runner = FakeRunner(
        [
            (0, CONNECTIONS_OK, ""),
            (0, '{"result":"", "_treg":{"http_status":201,"call_id":"media-1"}}', ""),
        ]
    )
    manifest = make_manifest()
    manifest["media"] = {
        "images": [
            {"id": "urn:li:image:aaa", "altText": "Capture interface"},
            {"id": "urn:li:image:bbb", "altText": "Rendu three.js"},
        ]
    }
    receipt = make_adapter(runner).post(manifest)
    assert receipt["http_status"] == 201
    content = runner.payloads[0]["content"]
    assert content["multiImage"]["images"] == [
        {"id": "urn:li:image:aaa", "altText": "Capture interface"},
        {"id": "urn:li:image:bbb", "altText": "Rendu three.js"},
    ]


def test_post_with_single_media_payload():
    runner = FakeRunner(
        [
            (0, CONNECTIONS_OK, ""),
            (0, '{"result":"", "_treg":{"http_status":201}}', ""),
        ]
    )
    manifest = make_manifest()
    manifest["media"] = {"id": "urn:li:image:aaa", "altText": "Capture interface"}
    make_adapter(runner).post(manifest)
    assert runner.payloads[0]["content"] == {
        "media": {"id": "urn:li:image:aaa", "altText": "Capture interface"}
    }


def test_media_without_urn_is_refused():
    runner = FakeRunner([])
    manifest = make_manifest()
    manifest["media"] = {"images": [{"altText": "sans URN"}]}
    with pytest.raises(PublisherError) as exc:
        make_adapter(runner).post(manifest)
    assert "MEDIA_INVALID" in str(exc.value)
    assert runner.calls == []


def test_planned_image_is_uploaded_then_published(monkeypatch):
    """Parcours complet : image approuvée en RAM → initializeUpload → PUT → post."""
    from linkedin_assistant import media

    buffer = media.ImageBuffer()
    asset = buffer.add(b"\x89PNG\r\n\x1a\nDATA", content_type="image/png", filename="a.png", source="url")
    runner = FakeRunner(
        [
            (0, CONNECTIONS_OK, ""),  # résolution de la connexion
            (0, INIT_OK, ""),  # initializeUpload
            (0, CONNECTIONS_OK, ""),  # résolution de la connexion (post)
            (0, '{"result":"", "_treg":{"http_status":201,"call_id":"post-1"}}', ""),
        ]
    )
    uploader = FakeUploader()
    monkeypatch.setattr(TregPublisher, "_put_binary", staticmethod(uploader))
    adapter = TregPublisher(api_version="202501", runner=runner, buffer=buffer)

    manifest = make_manifest()
    manifest["image"] = asset.manifest_entry()
    receipt = adapter.post(manifest)

    assert receipt["http_status"] == 201
    # l'image a été téléversée (PUT sur l'URL pré-signée) puis référencée
    assert len(uploader.calls) == 1
    assert uploader.calls[0][1] == b"\x89PNG\r\n\x1a\nDATA"
    # payloads[0] = corps d'initializeUpload, payloads[1] = corps de la publication
    assert runner.payloads[1]["content"] == {"media": {"id": "urn:li:image:abc123"}}


def test_planned_image_refused_when_buffer_lost(monkeypatch):
    """Tampon perdu (redémarrage) : refus SANS aucun appel externe."""
    from linkedin_assistant import media

    buffer = media.ImageBuffer()
    asset = buffer.add(b"\x89PNG\r\n\x1a\nDATA", content_type="image/png", filename="a.png", source="url")
    entry = asset.manifest_entry()
    buffer.clear()
    runner = FakeRunner([])
    adapter = TregPublisher(api_version="202501", runner=runner, buffer=buffer)
    manifest = make_manifest()
    manifest["image"] = entry
    with pytest.raises(PublisherError) as exc:
        adapter.post(manifest)
    assert "IMAGE_BUFFER_LOST" in str(exc.value)
    assert runner.calls == []


def test_planned_image_refused_when_bytes_differ(monkeypatch):
    """Les octets doivent correspondre à l'image approuvée (empreinte)."""
    from linkedin_assistant import media

    buffer = media.ImageBuffer()
    asset = buffer.add(b"\x89PNG\r\n\x1a\nDATA", content_type="image/png", filename="a.png", source="url")
    entry = asset.manifest_entry()
    entry["sha256"] = "0" * 64
    runner = FakeRunner([])
    adapter = TregPublisher(api_version="202501", runner=runner, buffer=buffer)
    manifest = make_manifest()
    manifest["image"] = entry
    with pytest.raises(PublisherError) as exc:
        adapter.post(manifest)
    assert "IMAGE_MISMATCH" in str(exc.value)
    assert runner.calls == []


def test_payload_file_is_pure_ascii_and_preserves_text():
    runner = FakeRunner(
        [
            (0, CONNECTIONS_OK, ""),
            (0, '{"result":"", "_treg":{"http_status":201}}', ""),
        ]
    )
    text = "Émoji ⚠️ et accents : é è à ç"
    make_adapter(runner).post(make_manifest(text=text))
    raw = runner.raw_payloads[0]
    assert all(byte < 128 for byte in raw)  # ASCII pur : immune à l'encodage local
    assert json.loads(raw.decode("ascii"))["commentary"] == text


# --- aperçu du fil LinkedIn (prévention des contenus masqués) --------------


def test_feed_preview_reports_hidden_content():
    text = "A" * 300 + "LIEN https://github.com/ruvnet/RuView"
    preview = feed_preview(text)
    assert preview["truncated"] is True
    assert preview["limit"] == FEED_PREVIEW_LIMIT
    assert preview["hidden_chars"] == len(text) - FEED_PREVIEW_LIMIT
    assert "LIEN" in preview["hidden"]  # le lien serait invisible dans le fil
    assert preview["visible"].startswith("A")


def test_feed_preview_short_post_is_not_truncated():
    preview = feed_preview("Court post.")
    assert preview["truncated"] is False
    assert preview["hidden"] == ""


def test_post_warns_when_feed_preview_will_hide_content(capsys):
    runner = FakeRunner(
        [
            (0, CONNECTIONS_OK, ""),
            (0, '{"result":"", "_treg":{"http_status":201}}', ""),
        ]
    )
    long_text = "Début. " + "complément. " * 40 + " https://github.com/ruvnet/RuView"
    make_adapter(runner).post(make_manifest(text=long_text))
    captured = capsys.readouterr()
    assert "apercu fil" in captured.err
    assert "masqués" in captured.err
    # Le lien caché est nommé explicitement (cause du premier échec).
    assert "https://github.com/ruvnet/RuView" in captured.err
    # Le texte envoyé reste INTACT : l'avertissement ne modifie rien.
    assert json.loads(runner.raw_payloads[0].decode("ascii"))["commentary"] == long_text


def test_post_does_not_warn_for_short_text(capsys):
    runner = FakeRunner(
        [
            (0, CONNECTIONS_OK, ""),
            (0, '{"result":"", "_treg":{"http_status":201}}', ""),
        ]
    )
    make_adapter(runner).post(make_manifest(text="Post court, tout visible."))
    assert "apercu fil" not in capsys.readouterr().err
