"""Tampon d'images RAM seule : validation, empreintes, aucune persistance."""

import pytest

from linkedin_assistant import media


PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    b"\x1f\x15\xc4\x89"
    b"\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01"
    b"\r\n-\xb4"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)
JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 32


def test_png_accepted_and_fingerprinted():
    buffer = media.ImageBuffer()
    asset = buffer.add(PNG, content_type="image/png", filename="a.png", source="telegram")
    assert asset.content_type == "image/png"
    assert asset.size == len(PNG)
    assert len(asset.sha256) == 64
    assert asset.source == "telegram"
    assert len(buffer) == 1


def test_jpeg_accepted():
    buffer = media.ImageBuffer()
    asset = buffer.add(JPEG, content_type="image/jpeg", filename="a.jpg", source="url")
    assert asset.content_type == "image/jpeg"


def test_non_image_refused():
    buffer = media.ImageBuffer()
    with pytest.raises(media.MediaError) as exc:
        buffer.add(b"ceci n'est pas une image", content_type="image/png", filename="x.png", source="url")
    assert exc.value.code == "IMAGE_UNSUPPORTED"
    assert len(buffer) == 0


def test_oversized_refused():
    buffer = media.ImageBuffer(max_bytes=1024)
    with pytest.raises(media.MediaError) as exc:
        buffer.add(PNG + b"\x00" * 2048, content_type="image/png", filename="x.png", source="url")
    assert exc.value.code == "IMAGE_TOO_LARGE"


def test_empty_refused():
    buffer = media.ImageBuffer()
    with pytest.raises(media.MediaError) as exc:
        buffer.add(b"", content_type="image/png", filename="x.png", source="url")
    assert exc.value.code == "IMAGE_EMPTY"


def test_limit_per_draft():
    buffer = media.ImageBuffer(max_images=2)
    buffer.add(PNG, content_type="image/png", filename="1.png", source="url")
    buffer.add(JPEG, content_type="image/jpeg", filename="2.jpg", source="url")
    with pytest.raises(media.MediaError) as exc:
        buffer.add(PNG, content_type="image/png", filename="3.png", source="url")
    assert exc.value.code == "IMAGE_LIMIT"


def test_manifest_entry_carries_no_bytes():
    buffer = media.ImageBuffer()
    asset = buffer.add(PNG, content_type="image/png", filename="a.png", source="telegram", alt_text="un visuel")
    entry = asset.manifest_entry()
    assert "data" not in entry
    assert entry["sha256"] == asset.sha256
    assert entry["token"] == asset.token
    assert entry["alt_text"] == "un visuel"
    assert entry["size"] == len(PNG)


def test_get_returns_none_after_clear():
    buffer = media.ImageBuffer()
    asset = buffer.add(PNG, content_type="image/png", filename="a.png", source="url")
    assert buffer.get(asset.token) is not None
    buffer.clear()
    assert buffer.get(asset.token) is None


def test_declared_type_is_corrected_by_bytes():
    """Un Content-Type menteur ne passe pas : la signature fait foi."""
    buffer = media.ImageBuffer()
    asset = buffer.add(PNG, content_type="image/jpeg", filename="a.png", source="url")
    assert asset.content_type == "image/png"
