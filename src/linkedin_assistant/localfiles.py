"""Accès en LECTURE SEULE à un dossier local : textes → brouillons, images → candidats photo.

Règles du projet (docs/SETUP_GUIDE.md § 10, appliquées aux fichiers locaux) :
- le dossier configuré est une SANDBOX : tout chemin demandé est résolu et doit
  rester strictement sous ce dossier (aucune traversée, aucun lien symbolique
  sortant, aucun chemin absolu accepté) ;
- lecture seule : aucune écriture, aucun renommage, aucune suppression ;
- le contenu d'un fichier est une donnée NON FIABLE : il ne déclenche jamais
  une publication — il devient un brouillon soumis à la chaîne de validation
  TEXTE → IMAGE → bouton final, comme toute autre source ;
- bornes : nombre de fichiers listés, taille maximale des textes et des
  images (limite de téléversement LinkedIn réutilisée).
"""

from __future__ import annotations

import io
from pathlib import Path, PureWindowsPath

from .media import MAX_IMAGE_BYTES


class LocalFilesError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


TEXT_EXTENSIONS = {".txt", ".md"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif"}
DOCUMENT_EXTENSIONS = {".pdf"}
MAX_TEXT_BYTES = 100_000
MAX_LISTED_PER_KIND = 30
MAX_LISTED_OTHERS = 15
# PDF : lecture du texte uniquement (les posts LinkedIn n'acceptent pas les
# documents) ; bornes plus larges que les textes, pages bornées aussi.
MAX_DOCUMENT_BYTES = 10_000_000
MAX_DOCUMENT_PAGES = 20


def _folder(folder: str | Path) -> Path:
    path = Path(folder)
    if not path.is_absolute():
        raise LocalFilesError("FOLDER_NOT_ABSOLUTE", f"chemin de dossier non absolu : {path}")
    if not path.is_dir():
        raise LocalFilesError("FOLDER_INACCESSIBLE", f"dossier introuvable ou non directory : {path}")
    return path


def _sandbox(folder: Path, name: str) -> Path:
    """Résout un nom relatif et garantit qu'il reste sous le dossier."""
    if not name or PureWindowsPath(name).is_absolute() or name.startswith(("/", "\\")):
        raise LocalFilesError("PATH_REFUSED", "chemin refusé (absolu)")
    parts = PureWindowsPath(name).parts
    if any(part in ("..", "") for part in parts):
        raise LocalFilesError("PATH_REFUSED", "chemin refusé (traversée hors du dossier)")
    root = folder.resolve()
    candidate = (folder / name).resolve()
    if candidate != root and not candidate.is_relative_to(root):
        raise LocalFilesError("PATH_REFUSED", "chemin refusé (hors du dossier)")
    if not candidate.is_file():
        raise LocalFilesError("FILE_NOT_FOUND", f"fichier introuvable : {name}")
    return candidate


def list_files(folder: str | Path) -> dict:
    """Liste récursive, lecture seule, bornée. Retourne chemins relatifs triés."""
    root = _folder(folder)
    texts: list[str] = []
    images: list[str] = []
    documents: list[str] = []
    others: list[str] = []
    truncated = False
    for entry in sorted(root.rglob("*")):
        if not entry.is_file():
            continue
        if any(part.startswith(".") for part in entry.relative_to(root).parts):
            continue
        suffix = entry.suffix.lower()
        rel = entry.relative_to(root).as_posix()
        if suffix in TEXT_EXTENSIONS:
            if len(texts) < MAX_LISTED_PER_KIND:
                texts.append(rel)
            else:
                truncated = True
        elif suffix in DOCUMENT_EXTENSIONS:
            if len(documents) < MAX_LISTED_PER_KIND:
                documents.append(rel)
            else:
                truncated = True
        elif suffix in IMAGE_EXTENSIONS:
            if len(images) < MAX_LISTED_PER_KIND:
                images.append(rel)
            else:
                truncated = True
        elif len(others) < MAX_LISTED_OTHERS:
            others.append(rel)
    return {
        "texts": texts,
        "images": images,
        "documents": documents,
        "others": others,
        "truncated": truncated,
    }


def read_text(folder: str | Path, name: str) -> str:
    """Lit un fichier texte borné ; refuse le binaire et le vide."""
    root = _folder(folder)
    candidate = _sandbox(root, name)
    if candidate.suffix.lower() not in TEXT_EXTENSIONS:
        raise LocalFilesError("TEXT_UNSUPPORTED", f"extension non textuelle : {candidate.suffix}")
    size = candidate.stat().st_size
    if size > MAX_TEXT_BYTES:
        raise LocalFilesError(
            "TEXT_TOO_LARGE",
            f"fichier de {size} octets : maximum {MAX_TEXT_BYTES} octets",
        )
    data = candidate.read_bytes()
    if b"\x00" in data:
        raise LocalFilesError("TEXT_BINARY", "fichier binaire, pas un texte")
    text = data.decode("utf-8", errors="replace")
    if not text.strip():
        raise LocalFilesError("TEXT_EMPTY", "fichier vide")
    return text


def read_image(folder: str | Path, name: str) -> bytes:
    """Lit les octets d'une image locale ; le format est validé par le tampon."""
    root = _folder(folder)
    candidate = _sandbox(root, name)
    if candidate.suffix.lower() not in IMAGE_EXTENSIONS:
        raise LocalFilesError("IMAGE_UNSUPPORTED", f"extension non image : {candidate.suffix}")
    size = candidate.stat().st_size
    if size > MAX_IMAGE_BYTES:
        raise LocalFilesError(
            "IMAGE_TOO_LARGE",
            f"image de {size} octets : maximum {MAX_IMAGE_BYTES} octets",
        )
    return candidate.read_bytes()


def read_document(folder: str | Path, name: str) -> str:
    """Extrait le texte d'un PDF local (borné en taille et en pages).

    La bibliothèque pypdf est importée à l'usage : son absence produit une
    erreur claire, jamais un crash du bot.
    """
    root = _folder(folder)
    candidate = _sandbox(root, name)
    if candidate.suffix.lower() not in DOCUMENT_EXTENSIONS:
        raise LocalFilesError("DOCUMENT_UNSUPPORTED", f"extension non document : {candidate.suffix}")
    size = candidate.stat().st_size
    if size > MAX_DOCUMENT_BYTES:
        raise LocalFilesError(
            "DOCUMENT_TOO_LARGE",
            f"PDF de {size} octets : maximum {MAX_DOCUMENT_BYTES} octets",
        )
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise LocalFilesError(
            "PDF_LIBRARY_MISSING",
            "pypdf absent : .venv\\Scripts\\python -m pip install pypdf",
        ) from exc
    try:
        reader = PdfReader(io.BytesIO(candidate.read_bytes()))
        pages = reader.pages[:MAX_DOCUMENT_PAGES]
        text = "\n".join((page.extract_text() or "") for page in pages).strip()
    except Exception as exc:  # noqa: BLE001 — PDF corrompu : erreur utilisateur
        raise LocalFilesError("PDF_UNREADABLE", f"PDF illisible : {type(exc).__name__}") from exc
    if not text:
        raise LocalFilesError("PDF_TEXT_EMPTY", "aucun texte extractible (PDF scanné ou vide ?)")
    return text[:MAX_TEXT_BYTES]


MAX_RENDER_PAGES = 4
RENDER_SCALE = 2.0  # ~144 DPI : lisible et nettement sous la limite d'upload


def render_document_page(folder: str | Path, name: str, page: int = 0) -> tuple[bytes, int]:
    """Rend une page de PDF en PNG (RAM seule) ; retourne (png, nb_pages).

    L'image reste en mémoire : elle est destinée au tampon d'images du
    brouillon (aucune écriture disque). Bibliothèque pypdfium2 importée à
    l'usage : son absence produit une erreur claire, jamais un crash.
    """
    root = _folder(folder)
    candidate = _sandbox(root, name)
    if candidate.suffix.lower() not in DOCUMENT_EXTENSIONS:
        raise LocalFilesError("DOCUMENT_UNSUPPORTED", f"extension non document : {candidate.suffix}")
    size = candidate.stat().st_size
    if size > MAX_DOCUMENT_BYTES:
        raise LocalFilesError(
            "DOCUMENT_TOO_LARGE",
            f"PDF de {size} octets : maximum {MAX_DOCUMENT_BYTES} octets",
        )
    try:
        import pypdfium2 as pdfium
        from PIL import Image
    except ImportError as exc:
        raise LocalFilesError(
            "PDF_RENDER_LIBRARY_MISSING",
            "pypdfium2/pillow absent : .venv\\Scripts\\python -m pip install pypdfium2 pillow",
        ) from exc
    try:
        document = pdfium.PdfDocument(candidate.read_bytes())
        total = len(document)
        if total == 0:
            raise LocalFilesError("PDF_UNREADABLE", "PDF sans page")
        if not (0 <= page < total):
            raise LocalFilesError("PAGE_OUT_OF_RANGE", f"page {page + 1} hors 1 à {total}")
        if page >= MAX_RENDER_PAGES:
            raise LocalFilesError(
                "PAGE_OUT_OF_RANGE", f"seules les {MAX_RENDER_PAGES} premières pages sont rendues"
            )
        bitmap = document[page].render(scale=RENDER_SCALE)
        buffer = io.BytesIO()
        bitmap.to_pil().save(buffer, format="PNG", optimize=True)
        png = buffer.getvalue()
    except LocalFilesError:
        raise
    except Exception as exc:  # noqa: BLE001 — PDF corrompu : erreur utilisateur
        raise LocalFilesError("PDF_UNREADABLE", f"rendu impossible : {type(exc).__name__}") from exc
    if len(png) > MAX_IMAGE_BYTES:
        raise LocalFilesError(
            "IMAGE_TOO_LARGE",
            f"rendu de {len(png)} octets : maximum {MAX_IMAGE_BYTES} octets",
        )
    return png, total
