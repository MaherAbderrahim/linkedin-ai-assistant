"""Assistance IA du brouillon : mémoire locale, révision LLM, images proposées.

Aucun test n'accède au réseau : les providers LLM et la lecture d'images sont
fictifs ; le LLM ne valide rien et ne publie rien.
"""

import json

import pytest

from linkedin_assistant import extracting, media, research, searching, store
from linkedin_assistant.conversation import Conversation
from linkedin_assistant.hashing import content_fingerprint
from linkedin_assistant.llm import LLMError, LLMProvider, LLMResult, SimulatedProvider
from linkedin_assistant.publisher import SimulatedPublisher

from test_images_flow import PNG
from test_phase2 import button_data, cb, last_button, msg


class RealFakeLLM(LLMProvider):
    """Provider fictif mais is_real=True : la révision passe par le LLM."""

    is_real = True

    def __init__(self, text="Post réécrit par le modèle.", error=None):
        self.name = "fake"
        self.model = "fake-model"
        self.text = text
        self.error = error
        self.prompts = []

    def generate(self, task, prompt):
        self.prompts.append((task, prompt))
        if self.error:
            raise self.error
        return LLMResult(
            provider=self.name, model=self.model, text=self.text, latency_ms=1, usage={}
        )


class FakeClient:
    def __init__(self):
        self.sent = []
        self.photos = []
        self.callbacks = []

    def get_updates(self, offset, timeout):
        return []

    def send_message(self, chat_id, text, reply_markup=None):
        self.sent.append((chat_id, text, reply_markup))
        return {"message_id": len(self.sent)}

    def send_photo(self, chat_id, photo, caption=None, content_type="image/png"):
        self.photos.append((chat_id, photo, caption, content_type))
        return {"message_id": len(self.photos)}

    def answer_callback(self, callback_query_id, text=None):
        self.callbacks.append(callback_query_id)
        return {}


@pytest.fixture()
def client():
    return FakeClient()


@pytest.fixture()
def config(tmp_path):
    from linkedin_assistant.config import Config

    return Config(owner_id=42, chat_id=42, db_path=tmp_path / "x.db", linkedin_account="urn:li:person:test")


@pytest.fixture()
def buffer():
    return media.ImageBuffer()


@pytest.fixture()
def conv(conn, config, client, buffer):
    return Conversation(conn, config, client, SimulatedPublisher(), buffer=buffer)


@pytest.fixture()
def conv_with_llm(conn, config, client):
    llm = RealFakeLLM()
    conv = Conversation(conn, config, client, SimulatedPublisher(), llm_provider=llm)
    return conv, llm


def archive_post(conn, text: str) -> None:
    """Sème une publication dans l'archive (source A, authorship assistant)."""
    with conn:
        now = store.utcnow()
        conn.execute(
            "INSERT INTO history_posts (id, account, current_version, published_at, "
            "published_at_precision, confirmed_at, visibility, created_at, updated_at) "
            "VALUES (?, ?, 1, ?, 'second', ?, 'PUBLIC', ?, ?)",
            ("hp_" + store.new_id(), "urn:li:person:test", now, now, now, now),
        )
        row = conn.execute("SELECT id FROM history_posts ORDER BY rowid DESC LIMIT 1").fetchone()
        post_id = row["id"]
        conn.execute(
            "INSERT INTO history_versions (id, post_id, version, text, exact_hash, "
            "normalized_hash, norm_version, authorship, observed_at) VALUES (?, ?, 1, ?, ?, ?, 'n1', 'assistant', ?)",
            ("hv_" + store.new_id(), post_id, text, "", "", now),
        )


# --- extraction d'images candidates ----------------------------------------


def test_extract_image_urls_from_og_and_img():
    markup = (
        '<html><head><meta property="og:image" content="https://exemple.fr/hero.png">'
        '<meta name="twitter:image" content="/relatif.jpg"></head>'
        '<body><img src="https://exemple.fr/photo.PNG">'
        '<img src="data:image/png;base64,AAA">'
        '<img src="icone.svg">'
        '<img src="https://exemple.fr/hero.png">'
        "</body></html>"
    )
    urls = extracting.extract_image_urls(markup, "https://exemple.fr/article")
    assert urls[0] == "https://exemple.fr/hero.png"
    assert "https://exemple.fr/relatif.jpg" in urls
    assert "https://exemple.fr/photo.PNG" in urls
    assert not any(u.startswith("data:") for u in urls)
    assert not any(u.endswith(".svg") for u in urls)
    assert urls.count("https://exemple.fr/hero.png") == 1


def test_extract_image_urls_refuses_private_hosts():
    markup = '<img src="http://127.0.0.1/secret.png">'
    assert extracting.extract_image_urls(markup, "https://exemple.fr/a") == []


def test_extract_image_urls_empty_markup():
    assert extracting.extract_image_urls("", "https://exemple.fr/a") == []


def test_read_url_collects_image_candidates(monkeypatch):
    monkeypatch.setattr(
        extracting,
        "fetch",
        lambda url, timeout=15.0: '<html><meta property="og:image" content="https://exemple.fr/visuel.png">'
        "<title>Article</title><p>Contenu.</p></html>",
    )
    source = research.read_url("https://exemple.fr/article")
    assert source.images == ["https://exemple.fr/visuel.png"]


# --- prompt de révision ------------------------------------------------------


def test_revision_prompt_delimits_draft_and_message():
    prompt = research.build_revision_prompt("Brouillon actuel.", "Rends ça plus humain")
    assert "=== BROUILLON ACTUEL ===" in prompt
    assert "Brouillon actuel." in prompt
    assert "Rends ça plus humain" in prompt
    assert "renvoie UNIQUEMENT le texte final du post" in prompt
    assert "n'annonce jamais une publication" in prompt


# --- révision du brouillon par le LLM ----------------------------------------


def test_free_text_is_interpreted_by_llm(conn, conv_with_llm, client):
    conv, llm = conv_with_llm
    conv.handle(msg("/new", uid=1))
    conv.handle(msg("Post initial IA, très formel.", uid=2))
    conv.handle(msg("Rends ça plus humain : commence par poser une question.", uid=3))
    version = conn.execute(
        "SELECT text FROM draft_versions ORDER BY revision DESC LIMIT 1"
    ).fetchone()
    assert version["text"] == "Post réécrit par le modèle."
    assert llm.prompts[0][0] == "draft_revision"
    assert "Post initial IA, très formel." in llm.prompts[0][1]
    assert any("reformulée" in sent[1] for sent in client.sent)


def test_free_text_falls_back_to_raw_on_llm_error(conn, conv_with_llm, client):
    conv, _llm = conv_with_llm
    conv.handle(msg("/new", uid=1))
    conv.handle(msg("Post initial.", uid=2))
    conv_with_llm[1].error = LLMError("LLM_QUOTA", "quota épuisé")
    conv.handle(msg("Raccourcis.", uid=3))
    texts = [r["text"] for r in conn.execute("SELECT text FROM draft_versions ORDER BY revision")]
    assert texts[1] == "Raccourcis."
    assert any("interprétation LLM impossible" in sent[1] for sent in client.sent)


def test_first_text_of_empty_draft_is_saved_raw(conn, conv_with_llm, client):
    conv, llm = conv_with_llm
    conv.handle(msg("/new", uid=1))
    conv.handle(msg("Mon texte exact que le modèle ne doit pas toucher.", uid=2))
    assert llm.prompts == []
    version = conn.execute(
        "SELECT text FROM draft_versions ORDER BY revision DESC LIMIT 1"
    ).fetchone()
    assert version["text"] == "Mon texte exact que le modèle ne doit pas toucher."


def test_simulated_llm_does_not_interpret(conn, conv, client):
    conv.handle(msg("/new", uid=1))
    conv.handle(msg("Post initial.", uid=2))
    conv.handle(msg("Consigne de révision.", uid=3))
    texts = [
        r["text"]
        for r in conn.execute("SELECT text FROM draft_versions ORDER BY revision")
    ]
    assert texts[1] == "Consigne de révision."


# --- mémoire locale (archive + profil) --------------------------------------


def test_memory_context_includes_archive_and_profile(conn, conv):
    archive_post(conn, "Post passé sur les MCP et l'infrastructure IA.")
    context = conv._memory_context("MCP")
    assert "Post passé sur les MCP" in context
    assert "STYLE OBSERVÉ" in context or "EXEMPLE RÉCENT" in context


def test_memory_context_empty_without_archive(conn, conv):
    assert "EXEMPLE RÉCENT" not in conv._memory_context()


def test_memory_context_passed_to_research(conn, conv, client, monkeypatch):
    archive_post(conn, "Post passé sur les MCP.")
    monkeypatch.setattr(
        extracting,
        "fetch",
        lambda url, timeout=15.0: "<html><title>Article MCP</title><p>Contenu utile.</p></html>",
    )
    llm = RealFakeLLM(text="Proposition.")
    conv2 = Conversation(
        conn, conv.config, client, SimulatedPublisher(),
        search_provider=_FakeSearch(), llm_provider=llm,
    )
    conv2.handle(msg("/research l'API Posts de LinkedIn", uid=1))
    style_prompt = [p for _task, p in llm.prompts if "STYLE OBSERVÉ" in p or "EXEMPLE RÉCENT" in p]
    assert style_prompt, "l'archive locale doit alimenter le prompt de proposition"


class _FakeSearch(searching.SearchProvider):
    name = "fake"

    def search(self, query, max_results):
        return [searching.SearchHit(title="Article MCP", url="https://exemple.fr/a", snippet="s")]


# --- bouton d'ajout d'image + images proposées -------------------------------


def test_imgadd_button_activates_image_mode(conn, conv, client):
    conv.handle(msg("/new", uid=1))
    conv.handle(msg("Texte.", uid=2))
    conv.handle(msg("/preview", uid=3))
    conv.handle(cb(last_button(client), uid=4))  # texte
    conv.handle(cb(button_data(client, "imgadd:"), uid=5))
    assert store.get_setting(conn, "image_mode") is not None
    assert any("Mode ajout d'image" in sent[1] for sent in client.sent)


def test_preview_clears_image_mode_and_shows_add_button(conn, conv, client):
    conv.handle(msg("/new", uid=1))
    conv.handle(msg("Texte.", uid=2))
    conv.handle(cb("imgadd:whatever", uid=3))
    conv.handle(msg("/preview", uid=4))
    markup = client.sent[-1][2]
    prefixes = [row[0]["callback_data"] for row in markup["inline_keyboard"]]
    assert any(p.startswith("text:") for p in prefixes)
    assert any(p.startswith("imgadd:") for p in prefixes)


def test_multiple_images_attached_up_to_limit(conn, conv, buffer, client):
    conv.handle(msg("/new", uid=1))
    conv.handle(msg("Texte du post.", uid=2))
    tokens = []
    for index in range(4):
        asset = buffer.add(
            PNG + bytes([index]), content_type="image/png", filename=f"a{index}.png", source="telegram"
        )
        tokens.append(asset.token)
        conv._attach_asset(asset)
    row = conn.execute(
        "SELECT manifest_json FROM draft_versions v JOIN drafts d ON d.id = v.draft_id "
        "AND d.current_revision = v.revision WHERE d.id = ?",
        (store.get_setting(conn, "active_draft"),),
    ).fetchone()
    manifest = json.loads(row["manifest_json"])
    assert len(manifest["images"]) == 4
    assert [e["token"] for e in manifest["images"]] == tokens
    # 5e image refusée
    extra = buffer.add(PNG + b"x", content_type="image/png", filename="extra.png", source="telegram")
    conv._attach_asset(extra)
    assert any("Limite de 4 images" in sent[1] for sent in client.sent)
    assert len(manifest["images"]) == 4


def test_content_fingerprint_covers_image_list():
    base = {"account": "urn:li:person:test", "text": "a", "visibility": "PUBLIC"}
    single = dict(base, images=[{"sha256": "h1"}])
    different = dict(base, images=[{"sha256": "h2"}])
    assert content_fingerprint(single) != content_fingerprint(different)
    assert content_fingerprint(dict(base)) != content_fingerprint(single)


def test_use_proposed_image_attaches_and_previews(conn, conv, buffer, client):
    conv.handle(msg("/new", uid=1))
    conv.handle(msg("Texte du post.", uid=2))
    asset = buffer.add(PNG, content_type="image/png", filename="prop.png", source="proposed")
    client.sent.clear()
    conv.handle(cb(f"use:{asset.token}", uid=3))
    # l'image est attachée puis l'aperçu renvoyé avec la photo affichée
    row = conn.execute(
        "SELECT manifest_json FROM draft_versions v JOIN drafts d ON d.id = v.draft_id "
        "AND d.current_revision = v.revision WHERE d.id = ?",
        (store.get_setting(conn, "active_draft"),),
    ).fetchone()
    manifest = json.loads(row["manifest_json"])
    assert manifest["images"][0]["token"] == asset.token
    assert len(client.photos) == 1


def test_use_unknown_token_is_not_fatal(conn, conv, client):
    conv.handle(msg("/new", uid=1))
    conv.handle(msg("Texte.", uid=2))
    conv.handle(cb("use:img_inconnu", uid=3))
    assert any("introuvable" in sent[1] for sent in client.sent)


def test_propose_images_sends_photo_and_button(conn, conv, buffer, client, monkeypatch):
    from linkedin_assistant import research as research_mod

    def fake_binary(url, timeout=15.0, max_bytes=None, allowed_types=None):
        return PNG, "image/png"

    monkeypatch.setattr(extracting, "fetch_binary", fake_binary)
    source = research_mod.Source(
        title="Article", url="https://exemple.fr/a",
        excerpt="x", images=["https://exemple.fr/hero.png"],
    )
    conv._propose_images([source])
    assert len(client.photos) == 1
    markup = client.sent[-1][2]
    assert markup["inline_keyboard"][0][0]["callback_data"].startswith("use:")


def test_propose_images_skips_unfetchable_candidates(conn, conv, client, monkeypatch):
    from linkedin_assistant import research as research_mod

    def failing(url, timeout=15.0, max_bytes=None, allowed_types=None):
        raise extracting.ExtractError("UNSUPPORTED_TYPE", "non image")

    monkeypatch.setattr(extracting, "fetch_binary", failing)
    source = research_mod.Source(
        title="Article", url="https://exemple.fr/a", excerpt="x", images=["https://exemple.fr/x.png"]
    )
    conv._propose_images([source])
    assert client.photos == []
    assert client.sent == []  # aucune image proposée : aucun message envoyé


def test_no_proposal_without_candidates(conn, conv, client):
    from linkedin_assistant import research as research_mod

    source = research_mod.Source(title="Article", url="https://exemple.fr/a", excerpt="x")
    conv._propose_images([source])
    assert client.photos == []


def test_preview_shows_every_attached_image(conn, conv, buffer, client):
    conv.handle(msg("/new", uid=1))
    conv.handle(msg("Texte du post.", uid=2))
    for index in range(3):
        asset = buffer.add(
            PNG + bytes([index]), content_type="image/png", filename=f"a{index}.png", source="telegram"
        )
        conv._attach_asset(asset)
    client.photos.clear()
    conv.handle(msg("/preview", uid=3))
    assert len(client.photos) == 3
    row = conn.execute(
        "SELECT manifest_json FROM draft_versions v JOIN drafts d ON d.id = v.draft_id "
        "AND d.current_revision = v.revision WHERE d.id = ?",
        (store.get_setting(conn, "active_draft"),),
    ).fetchone()
    assert len(json.loads(row["manifest_json"])["images"]) == 3
