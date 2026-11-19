"""Dossier local : lecture seule, sandbox, textes → brouillons, images → candidats.

Le contenu d'un fichier est une donnée non fiable : il crée un brouillon
soumis à la chaîne de validation, jamais une publication directe.
"""

import types

import pytest

from linkedin_assistant import localfiles, media, store
from linkedin_assistant.conversation import Conversation
from linkedin_assistant.config import Config
from linkedin_assistant.localfiles import LocalFilesError
from linkedin_assistant.publisher import SimulatedPublisher

from test_images_flow import PNG
from test_phase2 import msg

# PNG valide de test_images_flow ; extensions reconnues uniquement.


def make_pdf(text: str) -> bytes:
    """PDF minimal valide avec une page de texte (pour pypdf)."""
    header = b"%PDF-1.4\n"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length 60 >>\nstream\nBT /F1 12 Tf 72 720 Td (" + text.encode("latin-1") + b") Tj ET\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = bytearray(header)
    offsets = [0]
    for index, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode() + body + b"\nendobj\n"
    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_at}\n%%EOF\n".encode()
    )
    return bytes(out)


@pytest.fixture()
def folder(tmp_path):
    root = tmp_path / "linkedin"
    (root / "posts").mkdir(parents=True)
    (root / "posts" / "note.md").write_text("Idée de post depuis un fichier local.\n", encoding="utf-8")
    (root / "posts" / "brouillon.txt").write_text("Texte brut déjà prêt.", encoding="utf-8")
    (root / "photos").mkdir()
    (root / "photos" / "illustration.png").write_bytes(PNG)
    (root / "certificats").mkdir()
    (root / "certificats" / "badge.pdf").write_bytes(make_pdf("Certification AWS Cloud Foundations."))
    (root / "certificats" / "scans.pdf").write_bytes(make_pdf(""))
    (root / "notes.docx").write_bytes(b"PK\x03\x04fake")
    (root / "photos" / ".hidden.png").write_bytes(PNG)
    hidden_dir = root / ".cachette"
    hidden_dir.mkdir()
    (hidden_dir / "secret.txt").write_text("ne doit jamais être listé", encoding="utf-8")
    (root / "data.bin").write_bytes(b"\x00\x01")
    return root


def make_config(tmp_path, folder=None):
    config = Config(owner_id=42, chat_id=42, db_path=tmp_path / "x.db", linkedin_account="urn:li:person:test")
    object.__setattr__(config, "local_folder", folder)
    return config


class FakeClient:
    def __init__(self):
        self.sent = []
        self.photos = []

    def send_message(self, chat_id, text, reply_markup=None):
        self.sent.append((chat_id, text, reply_markup))
        return {"message_id": len(self.sent)}

    def send_photo(self, chat_id, photo, caption=None, content_type="image/png"):
        self.photos.append(photo)
        return {"message_id": len(self.photos)}


@pytest.fixture()
def conv(conn, tmp_path, folder):
    client = FakeClient()
    return Conversation(
        conn, make_config(tmp_path, folder), client, SimulatedPublisher(), buffer=media.ImageBuffer()
    )


# ------------------------------------------------------------------ sandbox

def test_list_files_classifies_and_skips_hidden(folder):
    listing = localfiles.list_files(folder)
    assert listing["texts"] == ["posts/brouillon.txt", "posts/note.md"]
    assert listing["documents"] == ["certificats/badge.pdf", "certificats/scans.pdf"]
    assert listing["images"] == ["photos/illustration.png"]
    assert listing["others"] == ["data.bin", "notes.docx"]
    assert listing["truncated"] is False


def test_read_text_ok(folder):
    assert "fichier local" in localfiles.read_text(folder, "posts/note.md")


def test_read_image_ok(folder):
    assert localfiles.read_image(folder, "photos/illustration.png") == PNG


def test_read_document_extracts_text(folder):
    text = localfiles.read_document(folder, "certificats/badge.pdf")
    assert "AWS Cloud Foundations" in text


def test_read_document_rejects_bad_pdf(folder):
    (folder / "certificats" / "casse.pdf").write_bytes(b"%PDF-1.4 garbage")
    with pytest.raises(LocalFilesError) as exc:
        localfiles.read_document(folder, "certificats/casse.pdf")
    assert exc.value.code == "PDF_UNREADABLE"


def test_read_document_too_large(folder):
    (folder / "certificats" / "gros.pdf").write_bytes(
        b"%PDF-1.4\n" + b"\x00" * (localfiles.MAX_DOCUMENT_BYTES + 1)
    )
    with pytest.raises(LocalFilesError) as exc:
        localfiles.read_document(folder, "certificats/gros.pdf")
    assert exc.value.code == "DOCUMENT_TOO_LARGE"


def test_render_document_page_png(folder):
    png, total = localfiles.render_document_page(folder, "certificats/badge.pdf")
    assert png.startswith(b"\x89PNG")
    assert total == 1
    assert len(png) < localfiles.MAX_IMAGE_BYTES


def test_render_page_out_of_range(folder):
    with pytest.raises(LocalFilesError) as exc:
        localfiles.render_document_page(folder, "certificats/badge.pdf", page=5)
    assert exc.value.code == "PAGE_OUT_OF_RANGE"


def test_render_too_large_rejected(folder):
    (folder / "certificats" / "gros.pdf").write_bytes(
        b"%PDF-1.4\n" + b"\x00" * (localfiles.MAX_DOCUMENT_BYTES + 1)
    )
    with pytest.raises(LocalFilesError) as exc:
        localfiles.render_document_page(folder, "certificats/gros.pdf")
    assert exc.value.code == "DOCUMENT_TOO_LARGE"


def test_traversal_rejected(folder):
    for name in ("../outside.txt", "posts/../../outside.txt", "posts/..\\..\\outside.txt", "C:/outside.txt"):
        with pytest.raises(LocalFilesError) as exc:
            localfiles.read_text(folder, name)
        assert exc.value.code == "PATH_REFUSED"


def test_symlink_escape_rejected(folder, tmp_path):
    outside = tmp_path / "outside.md"
    outside.write_text("secret", encoding="utf-8")
    link = folder / "fuite.md"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("symlinks indisponibles")
    with pytest.raises(LocalFilesError) as exc:
        localfiles.read_text(folder, "fuite.md")
    assert exc.value.code == "PATH_REFUSED"


def test_missing_file(folder):
    with pytest.raises(LocalFilesError) as exc:
        localfiles.read_text(folder, "posts/absent.md")
    assert exc.value.code == "FILE_NOT_FOUND"


def test_binary_and_empty_text_rejected(tmp_path):
    root = tmp_path / "f"
    root.mkdir()
    (root / "b.md").write_bytes(b"\x00binary")
    (root / "e.md").write_bytes(b"   \n")
    (root / "big.md").write_bytes(b"x" * (localfiles.MAX_TEXT_BYTES + 1))
    with pytest.raises(LocalFilesError) as exc:
        localfiles.read_text(root, "b.md")
    assert exc.value.code == "TEXT_BINARY"
    with pytest.raises(LocalFilesError) as exc:
        localfiles.read_text(root, "e.md")
    assert exc.value.code == "TEXT_EMPTY"
    with pytest.raises(LocalFilesError) as exc:
        localfiles.read_text(root, "big.md")
    assert exc.value.code == "TEXT_TOO_LARGE"


def test_image_too_large_rejected(tmp_path):
    root = tmp_path / "f"
    root.mkdir()
    (root / "huge.png").write_bytes(b"\x00" * (localfiles.MAX_IMAGE_BYTES + 1))
    with pytest.raises(LocalFilesError) as exc:
        localfiles.read_image(root, "huge.png")
    assert exc.value.code == "IMAGE_TOO_LARGE"


def test_folder_missing(tmp_path):
    with pytest.raises(LocalFilesError) as exc:
        localfiles.list_files(tmp_path / "inexistant")
    assert exc.value.code == "FOLDER_INACCESSIBLE"


# -------------------------------------------------------------- conversation

def test_folder_without_config(conn, tmp_path):
    conv = Conversation(conn, make_config(tmp_path), FakeClient(), SimulatedPublisher())
    conv.handle(msg("/folder"))
    assert "non configuré" in conv.client.sent[-1][1]


def test_folder_listing(conv):
    conv.handle(msg("/folder"))
    text = conv.client.sent[-1][1]
    assert "posts/note.md" in text
    assert "photos/illustration.png" in text
    assert ".cachette" not in text
    assert "i1" in text


def test_folder_number_too_big(conv):
    conv.handle(msg("/folder 99"))
    assert "Numéro invalide" in conv.client.sent[-1][1]


def test_folder_text_creates_draft(conv, conn):
    conv.handle(msg("/folder 2"))
    text = conv.client.sent[-1][1]
    assert "fichier local" in text
    draft_id = store.get_setting(conn, "active_draft")
    assert draft_id
    current = conv._current_text(draft_id)
    assert "fichier local" in current


def test_folder_image_attaches_to_active_draft(conv, conn):
    conv.handle(msg("/new"))
    conv.handle(msg("Texte du post."))
    conv.handle(msg("/folder i1"))
    draft_id = store.get_setting(conn, "active_draft")
    images = conv._current_images(draft_id)
    assert len(images) == 1
    assert images[0]["source"] == "folder"


def test_folder_document_creates_draft(conv, conn):
    # Pas de vrai modèle : le texte brut du PDF est conservé.
    conv.handle(msg("/folder d1"))
    joined = "\n".join(text for _, text, _ in conv.client.sent)
    assert "AWS Cloud Foundations" in joined
    assert "texte brut" in joined
    draft_id = store.get_setting(conn, "active_draft")
    assert "AWS Cloud Foundations" in conv._current_text(draft_id)


def test_folder_document_writes_post_with_llm(conn, tmp_path, folder):
    class FakePostLLM(FakeVisionLLM):
        is_real = True

        def generate(self, task, prompt):
            assert task == "linkedin_post"
            assert "SOURCE" in prompt
            return types.SimpleNamespace(
                text="Post poli annonçant la certification.", name=self.name, model=self.model, usage={}
            )

    conv = folder_conv(conn, tmp_path, folder, llm=FakePostLLM())
    conv.handle(msg("/folder d1"))
    draft_reply = conv.client.sent[0][1]
    assert "Post poli annonçant la certification." in draft_reply
    draft_id = store.get_setting(conn, "active_draft")
    assert conv._current_text(draft_id) == "Post poli annonçant la certification."
    # l'image candidate est toujours proposée
    assert conv.client.photos


def test_folder_text_writes_post_with_llm(conn, tmp_path, folder):
    class FakePostLLM(FakeVisionLLM):
        is_real = True

        def generate(self, task, prompt):
            return types.SimpleNamespace(
                text="Post à partir du fichier texte.", name=self.name, model=self.model, usage={}
            )

    conv = folder_conv(conn, tmp_path, folder, llm=FakePostLLM())
    conv.handle(msg("/folder 2"))
    draft_id = store.get_setting(conn, "active_draft")
    assert conv._current_text(draft_id) == "Post à partir du fichier texte."


class FakeVisionLLM:
    name = "groq"
    model = "vision-test"

    def __init__(self):
        self.vision_calls = []

    def generate(self, task, prompt):
        return types.SimpleNamespace(text="révision", name=self.name, model=self.model, usage={})

    def generate_vision(self, task, prompt, data, content_type):
        self.vision_calls.append((task, content_type, len(data)))
        return types.SimpleNamespace(
            text="Texte OCR du certificat.", name=self.name, model=self.model, usage={}
        )


def folder_conv(conn, tmp_path, folder, llm=None):
    return Conversation(
        conn,
        make_config(tmp_path, folder),
        FakeClient(),
        SimulatedPublisher(),
        buffer=media.ImageBuffer(),
        llm_provider=llm,
    )


def test_folder_document_proposes_render(conv):
    conv.handle(msg("/folder d1"))
    assert len(conv.client.photos) == 1
    assert conv.client.photos[0].startswith(b"\x89PNG")
    markup = conv.client.sent[-1][2]
    assert markup["inline_keyboard"][0][0]["callback_data"].startswith("use:")


def test_folder_scanned_pdf_uses_vision_ocr(conn, tmp_path, folder):
    llm = FakeVisionLLM()
    conv = folder_conv(conn, tmp_path, folder, llm=llm)
    conv.handle(msg("/folder d2"))
    assert len(llm.vision_calls) == 1
    assert llm.vision_calls[0][0] == "ocr"
    draft_id = store.get_setting(conn, "active_draft")
    assert "Texte OCR du certificat." in conv._current_text(draft_id)


def test_folder_scanned_pdf_ocr_failure_is_not_fatal(conn, tmp_path, folder):
    class BrokenLLM(FakeVisionLLM):
        def generate_vision(self, task, prompt, data, content_type):
            raise Exception("LLMError")  # pas une LLMError : doit rester non fatal

    conv = folder_conv(conn, tmp_path, folder, llm=BrokenLLM())
    conv.handle(msg("/folder d2"))
    text = conv.client.sent[-1][1]
    assert "OCR" in text or "impossible" in text or "rien" in text
    # le brouillon n'est pas créé à partir d'un texte inexistant
    assert not store.get_setting(conn, "active_draft")


def test_folder_document_number_too_big(conv):
    conv.handle(msg("/folder d9"))
    assert "Numéro invalide" in conv.client.sent[-1][1]


def test_folder_image_without_draft_creates_empty(conv, conn):
    conv.handle(msg("/folder img1"))
    draft_id = store.get_setting(conn, "active_draft")
    assert draft_id
    assert conv._current_images(draft_id)


def test_folder_image_too_large_rejected(conv, folder):
    huge = folder / "photos" / "huge.png"
    huge.write_bytes(b"\x00" * (localfiles.MAX_IMAGE_BYTES + 1))
    conv.handle(msg("/folder i1"))
    assert "refusée" in conv.client.sent[-1][1]
