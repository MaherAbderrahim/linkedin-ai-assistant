from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from . import extracting, localfiles, media, prefs, reminders, research as research_mod, searching, store
from .config import Config
from .db import transaction
from .hashing import NORM_VERSION, normalized_hash, sha256_text
from .llm import SimulatedProvider
from .publisher import publish
from .telegram import TelegramClient, escape_html, is_authorized, keyboard, split_message

SIMULATION_NOTE = "Mode simulation : aucune publication réelle sur LinkedIn."

DEFAULT_MODELS = {
    "groq": "openai/gpt-oss-120b",
    "openrouter": "google/gemma-4-31b-it:free",
}


class Conversation:
    def __init__(
        self,
        conn: sqlite3.Connection,
        config: Config,
        client: TelegramClient,
        publisher,
        *,
        buffer=None,
        search_provider=None,
        llm_provider=None,
    ):
        self.conn = conn
        self.config = config
        self.client = client
        self.publisher = publisher
        self.buffer = buffer if buffer is not None else media.ImageBuffer()
        self._search_provider = search_provider
        self._llm_provider = llm_provider

    # ------------------------------------------------------------------ utils

    def handle(self, update: dict) -> None:
        if not is_authorized(update, self.config.owner_id, self.config.chat_id):
            return
        if "callback_query" in update:
            self._callback(update["callback_query"])
        elif "message" in update:
            self._message(update["message"])

    def _reply(self, text: str, markup: dict | None = None) -> None:
        segments = split_message(escape_html(text))
        for i, segment in enumerate(segments):
            self.client.send_message(
                self.config.chat_id, segment, markup if i == len(segments) - 1 else None
            )

    def _expiry(self) -> str:
        return (datetime.now(timezone.utc) + timedelta(seconds=self.config.approval_ttl_seconds)).isoformat()

    def _active_draft(self) -> str | None:
        return store.get_setting(self.conn, "active_draft")

    def _is_real_publisher(self) -> bool:
        return bool(getattr(self.publisher, "is_real", False))

    def _publish_label(self) -> str:
        return "Publier sur LinkedIn" if self._is_real_publisher() else "Publier — SIMULATION"

    # -------------------------------------------------------------- commandes

    def _message(self, message: dict) -> None:
        text = message.get("text")
        photo = message.get("photo")
        if text is None and photo is None:
            self._reply("Seuls les messages texte et les photos sont traités.")
            return
        if photo:
            self._photo(photo)
            return
        text = (text or "").strip()
        if text == "/start":
            self._reply(
                "Assistant LinkedIn personnel. /new crée un brouillon, envoyez ensuite le texte, "
                "/preview affiche l'aperçu et les validations. /research <sujet> propose un post "
                "recherché (images candidates proposées en photo), /link <url> part d'un article, "
                "/folder liste vos fichiers locaux (textes → brouillons, images → candidats photo), "
                "/language fr|en|ar choisit la langue des posts, /humanize réécrit le brouillon "
                "pour un ton plus humain, /drafts reprend un brouillon sauvegardé, "
                "envoyez une photo pour illustrer, un message libre est interprété par le modèle "
                "quand un brouillon existe, /lastpost déclare une publication externe, "
                "/reminder on|off gère les rappels, /settings liste et ajuste les paramètres "
                "progressifs. Aucune publication sans bouton final dédié. "
                + ("" if self._is_real_publisher() else SIMULATION_NOTE)
            )
            return
        if text == "/status":
            self._reply(self._status())
            return
        if text.startswith("/settings"):
            self._settings_command(text[len("/settings"):].strip())
            return
        if text == "/new":
            draft_id = store.create_draft(self.conn)
            store.set_setting(self.conn, "active_draft", draft_id)
            self._reply("Brouillon créé. Envoyez le texte du post (il sera enregistré comme révision).")
            return
        if text == "/preview":
            self._preview()
            return
        if text == "/cancel":
            store.set_setting(self.conn, "active_draft", "")
            store.set_setting(self.conn, "image_mode", "")
            self._reply("Brouillon actif désélectionné (il reste en base, rien n'est supprimé).")
            return
        if text.startswith("/lastpost"):
            self._declare_publication(text[len("/lastpost"):].strip())
            return
        if text.startswith("/reminder"):
            self._reminder_command(text[len("/reminder"):].strip())
            return
        if text.startswith("/research"):
            self._research_command(text[len("/research"):].strip())
            return
        if text.startswith("/link"):
            self._link_command(text[len("/link"):].strip())
            return
        if text.startswith("/image"):
            self._image_command(text[len("/image"):].strip())
            return
        if text.startswith("/folder"):
            self._folder_command(text[len("/folder"):].strip())
            return
        if text.startswith("/language"):
            self._language_command(text[len("/language"):].strip())
            return
        if text == "/humanize":
            self._humanize_command()
            return
        if text == "/drafts":
            self._drafts_command()
            return
        if text.startswith("/"):
            self._reply(
                "Commande inconnue. /start, /new, /preview, /status, /cancel, /lastpost, "
                "/reminder, /settings, /research, /link, /image, /folder, /language, "
                "/humanize, /drafts."
            )
            return
        self._free_text(text)

    # ---------------------------------------------------------------- recherche

    def _free_text(self, text: str) -> None:
        """Message libre : clarification en attente, lien, ou brouillon."""
        pending = self._pending_research()
        if pending:
            self._clear_pending_research()
            topic = f"{pending['topic']} — {text}".strip(" —")
            self._run_research(topic)
            return
        url = self._extract_url(text)
        if url:
            self._run_link(url)
            return
        self._save_text(text)

    @staticmethod
    def _extract_url(text: str) -> str | None:
        for token in text.split():
            candidate = token.strip("<>(),.;:!?\"'")
            if candidate.startswith(("http://", "https://")) and extracting.is_public_http_url(candidate):
                return candidate
        return None

    def _pending_research(self) -> dict | None:
        raw = store.get_setting(self.conn, "pending_research")
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None

    def _clear_pending_research(self) -> None:
        store.set_setting(self.conn, "pending_research", "")

    def _research_command(self, topic: str) -> None:
        if not topic:
            self._reply("Usage : /research <sujet>, ex. /research l'API Posts de LinkedIn")
            return
        if research_mod.needs_clarification(topic):
            store.set_setting(
                self.conn,
                "pending_research",
                json.dumps({"topic": topic, "created_at": store.utcnow()}),
            )
            self._reply(research_mod.clarification_question(topic))
            return
        self._run_research(topic)

    def _link_command(self, url: str) -> None:
        if not url:
            self._reply("Usage : /link <url>, ex. /link https://exemple.fr/article")
            return
        self._run_link(url)

    def _research_settings(self) -> dict:
        def pref(key, default=None):
            try:
                value = prefs.get(self.conn, key)
            except prefs.PreferencesError:
                return default
            return value if value is not None else default

        return {
            "tone": pref("editorial_tone", "neutre"),
            "language": pref("editorial_language", "fr"),
            "length": int(pref("editorial_length", 1200) or 1200),
            "audience": pref("editorial_audience", "") or "",
        }

    def _memory_context(self, topic: str = "") -> str:
        """Contexte de style tiré de la BASE LOCALE : profil descriptif,
        exemples récents de l'archive et règles confirmées.

        Bornes : 3 posts × 900 caractères, 5 règles, profil ≤ 4 000 caractères.
        Descriptif et recalculable, jamais une règle normative non confirmée :
        le LLM s'en inspire, il ne reçoit aucun ordre de publication.
        """
        from . import profile as profile_mod, retrieval as retrieval_mod

        account = self.config.linkedin_account
        parts: list[str] = []
        try:
            data = profile_mod.get(self.conn, account)
            if data is None or data.get("stale"):
                profile_mod.refresh(self.conn, account)
                data = profile_mod.get(self.conn, account)
            if data:
                prof = data.get("profile") or {}
                length = prof.get("length") or {}
                terms = [term for term, _count in (prof.get("top_terms") or [])[:12]]
                bits = []
                if length.get("avg"):
                    bits.append(f"longueur moyenne observée : {length['avg']} caractères")
                if terms:
                    bits.append("termes récurrents : " + ", ".join(terms))
                if bits:
                    parts.append(
                        f"STYLE OBSERVÉ (archive locale, {prof.get('posts', 0)} publication(s)) : "
                        + " ; ".join(bits)
                    )
        except Exception:  # noqa: BLE001 — le style est un bonus, jamais un bloquant
            pass
        try:
            selected = retrieval_mod.select(
                self.conn, account, topic=(topic or None), limit=3, max_chars=12000
            )
            for index, post in enumerate(selected["posts"][:3], start=1):
                sample = (post.get("text") or "").strip()[:900]
                if sample:
                    parts.append(
                        f"EXEMPLE RÉCENT DE L'ARCHIVE ({post.get('published_at') or 'date inconnue'}), "
                        f"à imiter sans le recopier :\n{sample}"
                    )
            rules = selected["rules"][:5]
            if rules:
                parts.append("RÈGLES CONFIRMÉES PAR L'UTILISATEUR :\n- " + "\n- ".join(rules))
        except Exception:  # noqa: BLE001
            pass
        return "\n\n".join(parts)

    def _search(self):
        if self._search_provider is not None:
            return self._search_provider
        name = prefs.get(self.conn, "search_provider") or "tavily"
        try:
            return searching.provider(name)
        except searching.SearchError:
            return searching.SimulatedSearchProvider()

    def _llm(self):
        if self._llm_provider is not None:
            return self._llm_provider
        from . import llm as llm_mod

        name = prefs.get(self.conn, "llm_provider") or "groq"
        model = prefs.get(self.conn, "llm_model") or DEFAULT_MODELS.get(name, "")
        if name == "none" or not model:
            return SimulatedProvider(name or "none", model or "simulated")
        try:
            return llm_mod.provider(name, model)
        except llm_mod.LLMError:
            return SimulatedProvider(name, model)

    def _budget(self) -> searching.SearchBudget:
        def pref_int(key, default):
            try:
                value = prefs.get(self.conn, key)
            except prefs.PreferencesError:
                return default
            try:
                return int(value)
            except (TypeError, ValueError):
                return default

        return searching.SearchBudget(
            max_queries=pref_int("search_max_queries", 3),
            max_pages=pref_int("search_max_pages", 5),
        )

    def _run_research(self, topic: str) -> None:
        self._reply(f"Recherche en cours sur « {topic} »…")
        settings = self._research_settings()
        try:
            outcome = research_mod.research(
                topic,
                search_provider=self._search(),
                llm_provider=self._llm(),
                budget=self._budget(),
                tone=settings["tone"],
                language=settings["language"],
                length=settings["length"],
                audience=settings["audience"],
                style_context=self._memory_context(topic),
            )
        except research_mod.ResearchError as exc:
            self._reply(f"Recherche impossible ({exc.code}) : {exc}")
            return
        except searching.SearchError as exc:
            self._reply(f"Recherche impossible ({exc.code}) : {exc}")
            return
        if outcome.status != "draft":
            self._reply(outcome.question or "Aucune proposition.")
            return
        draft_id = self._create_draft(outcome.text)
        sources = "\n".join(f"- {s.title} — {s.url}" for s in outcome.sources)
        self._reply(
            f"Proposition (brouillon {draft_id[:8]}) :\n\n{outcome.text}\n\n"
            f"Sources lues :\n{sources}"
        )
        self._propose_images(outcome.sources)
        self._reply(
            "Corrigez le texte librement : une consigne (« rends ça plus humain », "
            "« commence par… ») sera interprétée par le modèle, qui réécrira le post. "
            "Ajoutez une image si vous le souhaitez, puis /preview pour valider."
        )

    def _run_link(self, url: str) -> None:
        self._reply("Lecture de la page…")
        try:
            source = research_mod.read_url(url)
        except research_mod.ResearchError as exc:
            self._reply(f"Page non lisible ({exc.code}) : {exc}")
            return
        settings = self._research_settings()
        prompt = research_mod.build_prompt(
            f"l'article suivant : {url}",
            [source],
            tone=settings["tone"],
            language=settings["language"],
            length=settings["length"],
            audience=settings["audience"],
            style_context=self._memory_context(source.title),
        )
        from . import llm as llm_mod

        try:
            result = self._llm().generate("linkedin_post", prompt)
        except llm_mod.LLMError as exc:
            self._reply(f"Rédaction impossible ({exc.code}) : {exc}")
            return
        text = (result.text or "").strip()
        if not text:
            self._reply("Le modèle n'a rien proposé.")
            return
        draft_id = self._create_draft(text)
        self._reply(
            f"Proposition (brouillon {draft_id[:8]}) :\n\n{text}\n\n"
            f"Source : {source.title} — {source.url}"
        )
        self._propose_images([source])
        self._reply(
            "Corrigez librement (une consigne sera interprétée par le modèle), "
            "ajoutez une image, puis /preview pour valider."
        )

    def _create_draft(self, text: str) -> str:
        draft_id = store.create_draft(self.conn)
        store.set_setting(self.conn, "active_draft", draft_id)
        store.add_revision(self.conn, draft_id, text, self._manifest(text))
        return draft_id

    def _write_post(self, topic: str, source: research_mod.Source) -> str | None:
        """Rédige un post via le même pipeline que /research et /link.

        Renvoie None si le modèle est indisponible ou simulé : l'appelant
        garde alors le texte brut de la source (jamais une publication sans
        validation ; le texte brut reste corrigeable par consignes libres).
        """
        provider = self._llm()
        if not getattr(provider, "is_real", False):
            self._reply("Modèle non configuré ou simulé : texte brut du fichier utilisé (consignes libres possibles).")
            return None
        settings = self._research_settings()
        prompt = research_mod.build_prompt(
            topic,
            [source],
            tone=settings["tone"],
            language=settings["language"],
            length=settings["length"],
            audience=settings["audience"],
            style_context=self._memory_context(topic),
        )
        from . import llm as llm_mod

        try:
            result = provider.generate("linkedin_post", prompt)
        except llm_mod.LLMError as exc:
            self._reply(f"Rédaction impossible ({exc.code}) : {exc} — texte brut du fichier utilisé.")
            return None
        text = (result.text or "").strip()
        if not text:
            self._reply("Le modèle n'a rien proposé — texte brut du fichier utilisé.")
            return None
        return text

    # ------------------------------------------------------------------ images

    MAX_IMAGES_PER_DRAFT = media.MAX_IMAGES_PER_DRAFT

    def _manifest(self, text: str, images: list | None = None) -> dict:
        manifest = {
            "account": self.config.linkedin_account,
            "visibility": self._visibility(),
        }
        if images:
            manifest["images"] = images
        return manifest

    def _visibility(self) -> str:
        """PUBLIC ou CONNECTIONS, choisi par paramètre (jamais implicite)."""
        try:
            value = prefs.get(self.conn, "post_visibility")
        except prefs.PreferencesError:
            value = None
        return "CONNECTIONS" if (value or "public").strip().lower() == "connections" else "PUBLIC"

    def _propose_images(self, sources: list) -> None:
        """Propose jusqu'à 2 images tirées des pages lues.

        Les images sont envoyées EN IMAGE dans Telegram (pas un lien) avec un
        bouton « Utiliser ». Rien n'est attaché sans clic explicite ; les
        octets restent en RAM et chaque candidat passe les garde-fous SSRF
        et la signature binaire (`fetch_binary`). Une proposition qui échoue
        n'est jamais bloquante.
        """
        urls: list[str] = []
        for source in sources:
            for url in (getattr(source, "images", None) or []):
                if url not in urls:
                    urls.append(url)
        if not urls:
            return
        assets = []
        for url in urls:
            try:
                data, content_type = extracting.fetch_binary(url, timeout=15.0)
                asset = self.buffer.add(
                    data,
                    content_type=content_type,
                    filename=urlparse(url).path.rsplit("/", 1)[-1] or "image",
                    source="proposed",
                )
            except Exception:  # noqa: BLE001 — proposition, jamais un bloquant
                continue
            assets.append(asset)
            if len(assets) >= 2:
                break
        if not assets:
            return
        sent = 0
        for asset in assets:
            try:
                self.client.send_photo(
                    self.config.chat_id,
                    asset.data,
                    caption=f"Image proposée par la recherche ({asset.content_type}, "
                    f"empreinte {asset.sha256[:12]})",
                    content_type=asset.content_type,
                )
                sent += 1
            except Exception:  # noqa: BLE001 — l'aperçu est un bonus
                pass
        if not sent:
            return
        buttons = [
            (f"Utiliser l'image {index + 1}", f"use:{asset.token}")
            for index, asset in enumerate(assets)
        ]
        self._reply(
            "Images proposées depuis les pages lues. Cliquez pour attacher, "
            "ou envoyez vos propres photos (ou /image <url>).",
            keyboard(buttons),
        )

    def _use_proposed(self, token: str) -> None:
        asset = self.buffer.get(token)
        if asset is None:
            self._reply(
                "Image proposée introuvable (expirée ou bot redémarré). "
                "Renvoyez la photo ou /image <url>."
            )
            return
        self._attach_asset(asset)
        self._preview()

    def _image_add_mode(self, draft_id: str) -> None:
        store.set_setting(self.conn, "image_mode", draft_id)
        self._reply(
            f"Mode ajout d'image activé (maximum {self.MAX_IMAGES_PER_DRAFT} images par post). "
            "Envoyez 1, 2 ou plus de photos depuis le téléphone (une par message ou en album), "
            "ou /image <url> : chaque photo devient une image du brouillon. "
            "Puis /preview pour voir le rendu et valider les images exactes."
        )

    def _photo(self, photo: list) -> None:
        """Photo envoyée depuis le téléphone : octets en RAM, jamais sur disque."""
        if not photo:
            return
        best = photo[-1]
        file_id = best.get("file_id")
        if not file_id:
            self._reply("Photo illisible.")
            return
        try:
            meta = self.client.get_file(file_id)
            data = self.client.download(meta["file_path"])
        except Exception as exc:  # noqa: BLE001 — message utilisateur, jamais de trace
            self._reply(f"Photo non récupérée ({type(exc).__name__}).")
            return
        try:
            asset = self.buffer.add(
                data,
                content_type="image/png",
                filename=f"telegram_{best.get('file_unique_id', 'photo')}.jpg",
                source="telegram",
            )
        except media.MediaError as exc:
            self._reply(f"Photo refusée ({exc.code}) : {exc}")
            return
        self._attach_asset(asset)

    def _image_command(self, url: str) -> None:
        if not url:
            self._reply("Usage : /image <url>, ex. /image https://exemple.fr/image.jpg")
            return
        try:
            data, content_type = extracting.fetch_binary(url)
            asset = self.buffer.add(
                data,
                content_type=content_type,
                filename=urlparse(url).path.rsplit("/", 1)[-1] or "image",
                source="url",
            )
        except extracting.ExtractError as exc:
            self._reply(f"Image refusée ({exc.code}) : {exc}")
            return
        except media.MediaError as exc:
            self._reply(f"Image refusée ({exc.code}) : {exc}")
            return
        self._attach_asset(asset)

    def _attach_asset(self, asset) -> None:
        """Attache l'image au brouillon actif en créant une révision.

        Plusieurs images sont permises (jusqu'à 4 = limite LinkedIn par post) :
        chacune est une entrée du manifeste, approuvée sur son empreinte exacte.
        """
        draft_id = self._active_draft()
        if not draft_id:
            draft_id = self._create_draft("")
        current = self._current_images(draft_id)
        if len(current) >= self.MAX_IMAGES_PER_DRAFT:
            self._reply(
                f"Limite de {self.MAX_IMAGES_PER_DRAFT} images par post atteinte. "
                "Retirez une image ou /preview pour valider celles-ci."
            )
            return
        images = [*current, asset.manifest_entry()]
        manifest = self._manifest(self._current_text(draft_id), images=images)
        try:
            revision = store.add_revision(self.conn, draft_id, self._current_text(draft_id), manifest)
        except store.StoreError as exc:
            self._reply(f"Image non attachée ({exc.code}) : {exc}")
            return
        self._reply(
            f"Image attachée ({len(images)}/{self.MAX_IMAGES_PER_DRAFT} — {asset.content_type}, "
            f"{asset.size} octets, empreinte {asset.sha256[:12]}). "
            f"Révision {revision}. /preview pour voir le rendu et valider les images exactes."
        )

    # ------------------------------------------------------------------ dossier

    def _folder_command(self, arg: str) -> None:
        folder = getattr(self.config, "local_folder", None)
        if folder is None:
            self._reply(
                "Dossier local non configuré. Ajoutez dans config.toml :\n"
                'local_folder = "D:/Linkedin"\n'
                "puis redémarrez le bot. Le dossier n'est jamais écrit : lecture seule."
            )
            return
        try:
            listing = localfiles.list_files(folder)
        except localfiles.LocalFilesError as exc:
            self._reply(f"Dossier local indisponible ({exc.code}) : {exc}")
            return
        if not arg:
            self._folder_listing(folder, listing)
            return
        token = arg.strip()
        if token.lower().startswith("d") and token[1:].isdigit():
            self._folder_document(listing, int(token[1:]))
            return
        if token.lower().startswith("img") and token[3:].isdigit():
            self._folder_image(listing, int(token[3:]))
            return
        if token.lower().startswith("i") and token[1:].isdigit():
            self._folder_image(listing, int(token[1:]))
            return
        if token.isdigit():
            self._folder_text(listing, int(token))
            return
        self._reply(
            "Usage : /folder liste ; /folder <n> texte → brouillon ; "
            "/folder d<n> PDF → brouillon ; /folder i<n> image → brouillon actif."
        )

    def _folder_listing(self, folder, listing: dict) -> None:
        texts = listing["texts"]
        images = listing["images"]
        documents = listing["documents"]
        others = listing["others"]
        if not texts and not images and not documents and not others:
            self._reply(
                f"Aucun fichier exploitable dans {folder}.\n"
                "Textes attendus : .txt, .md — Images : .jpg, .jpeg, .png, .gif — Documents : .pdf."
            )
            return
        lines = [f"Dossier local (lecture seule) : {folder}", ""]
        if texts:
            lines.append("Textes :")
            lines += [f" {i + 1}. {name}" for i, name in enumerate(texts)]
            lines.append("")
        if documents:
            lines.append("Documents (PDF) :")
            lines += [f" d{i + 1}. {name}" for i, name in enumerate(documents)]
            lines.append("")
        if images:
            lines.append("Images :")
            lines += [f" i{i + 1}. {name}" for i, name in enumerate(images)]
            lines.append("")
        if others:
            lines.append("Autres (non exploitables) :")
            lines += [f" - {name}" for name in others]
            lines.append("")
        if listing["truncated"]:
            lines.append("(liste tronquée : limite de fichiers affichés atteinte)")
            lines.append("")
        lines += [
            "/folder <numéro> : le texte devient un brouillon.",
            "/folder d<numéro> : le texte du PDF devient un brouillon.",
            "/folder i<numéro> : l'image est attachée au brouillon actif.",
        ]
        self._reply("\n".join(lines))

    def _folder_text(self, listing: dict, number: int) -> None:
        texts = listing["texts"]
        if not (1 <= number <= len(texts)):
            self._reply(
                f"Numéro invalide : 1 à {len(texts)} (textes listés). /folder pour revoir la liste."
            )
            return
        name = texts[number - 1]
        try:
            raw = localfiles.read_text(self.config.local_folder, name)
        except localfiles.LocalFilesError as exc:
            self._reply(f"Fichier illisible ({exc.code}) : {exc}")
            return
        polished = self._write_post(
            f"post LinkedIn à partir du fichier local « {name} »",
            research_mod.Source(title=name, url="fichier local", excerpt=raw, images=[]),
        )
        text = polished if polished else raw
        intro = (
            "Proposition rédigée par le modèle à partir du fichier"
            if polished
            else "Texte du fichier"
        )
        draft_id = self._create_draft(text)
        self._reply(
            f"{intro} « {name} » (brouillon {draft_id[:8]}) :\n\n{text}\n\n"
            "Corrigez librement (une consigne sera interprétée par le modèle), ajoutez une "
            "image si besoin, puis /preview. Contenu de fichier = donnée non fiable : la "
            "publication reste soumise à la chaîne TEXTE → IMAGE → bouton final."
        )

    def _folder_document(self, listing: dict, number: int) -> None:
        documents = listing["documents"]
        if not (1 <= number <= len(documents)):
            self._reply(
                f"Numéro invalide : d1 à d{len(documents)} (PDF listés). /folder pour revoir la liste."
            )
            return
        name = documents[number - 1]
        try:
            raw = localfiles.read_document(self.config.local_folder, name)
        except localfiles.LocalFilesError as exc:
            if exc.code != "PDF_TEXT_EMPTY":
                self._reply(f"PDF illisible ({exc.code}) : {exc}")
                return
            # PDF scanné (sans couche texte) : OCR vision du LLM.
            raw = self._folder_ocr(name)
            if raw is None:
                return
        polished = self._write_post(
            f"post LinkedIn à partir du document local « {name} »",
            research_mod.Source(title=name, url="fichier local", excerpt=raw, images=[]),
        )
        text = polished if polished else raw
        intro = (
            "Proposition rédigée par le modèle à partir du PDF"
            if polished
            else "Texte du PDF"
        )
        draft_id = self._create_draft(text)
        self._reply(
            f"{intro} « {name} » (brouillon {draft_id[:8]}) :\n\n{text}\n\n"
            "Corrigez librement (une consigne sera interprétée par le modèle), puis /preview. "
            "Contenu de fichier = donnée non fiable : la publication reste soumise à la "
            "chaîne TEXTE → IMAGE → bouton final."
        )
        self._folder_propose_render(name)

    def _folder_ocr(self, name: str) -> str | None:
        """Lit le texte d'un PDF scanné : rendu de la 1re page + OCR vision.

        La page rendue est un PNG en RAM ; l'OCR n'est jamais un garant du
        contenu : le résultat devient un brouillon comme toute autre source.
        """
        try:
            png, _ = localfiles.render_document_page(self.config.local_folder, name)
        except localfiles.LocalFilesError as exc:
            self._reply(f"OCR impossible ({exc.code}) : {exc}")
            return None
        from . import llm as llm_mod

        try:
            if self._llm_provider is not None:
                provider = self._llm_provider
            else:
                pname = prefs.get(self.conn, "llm_provider") or "groq"
                if pname == "none":
                    self._reply("OCR indisponible : LLM désactivé (/settings).")
                    return None
                provider = llm_mod.vision_provider(pname)
        except llm_mod.LLMError as exc:
            self._reply(f"OCR indisponible ({exc.code}) : {exc}")
            return None
        prompt = (
            "Extrais intégralement le texte visible dans cette image de document. "
            "Réponds UNIQUEMENT avec le texte extrait, sans commentaire ni ajout."
        )
        try:
            result = provider.generate_vision("ocr", prompt, png, "image/png")
        except Exception as exc:  # noqa: BLE001 — l'OCR est un confort, jamais bloquant
            self._reply(f"OCR impossible : {type(exc).__name__}: {exc}")
            return None
        text = (result.text or "").strip()
        if not text:
            self._reply("L'OCR n'a rien lu sur la page.")
            return None
        self._reply(f"Texte lu par OCR vision ({provider.name}/{provider.model}).")
        return text

    def _folder_propose_render(self, name: str) -> None:
        """Propose la 1re page du PDF rendue en image (RAM seule, jamais
        attachée sans clic explicite, comme toute image proposée)."""
        try:
            png, _ = localfiles.render_document_page(self.config.local_folder, name)
            asset = self.buffer.add(
                png,
                content_type="image/png",
                filename=name.rsplit("/", 1)[-1].rsplit(".", 1)[0] + ".png",
                source="folder_pdf",
            )
            self.client.send_photo(
                self.config.chat_id,
                asset.data,
                caption=f"Page 1 du PDF rendue en image ({asset.content_type}, empreinte {asset.sha256[:12]})",
                content_type=asset.content_type,
            )
        except Exception:  # noqa: BLE001 — la proposition est un bonus, jamais bloquant
            return
        self._reply(
            "Image candidate proposée depuis le PDF. Cliquez pour l'attacher au brouillon actif, "
            "ou /preview pour valider sans image.",
            keyboard([("Utiliser l'image du PDF", f"use:{asset.token}")]),
        )

    def _folder_image(self, listing: dict, number: int) -> None:
        images = listing["images"]
        if not (1 <= number <= len(images)):
            self._reply(
                f"Numéro invalide : i1 à i{len(images)} (images listées). /folder pour revoir la liste."
            )
            return
        name = images[number - 1]
        try:
            data = localfiles.read_image(self.config.local_folder, name)
            asset = self.buffer.add(
                data,
                content_type="",
                filename=name.rsplit("/", 1)[-1],
                source="folder",
            )
        except localfiles.LocalFilesError as exc:
            self._reply(f"Image refusée ({exc.code}) : {exc}")
            return
        except media.MediaError as exc:
            self._reply(f"Image refusée ({exc.code}) : {exc}")
            return
        self._attach_asset(asset)

    def _current_text(self, draft_id: str) -> str:
        row = self.conn.execute(
            "SELECT v.text FROM draft_versions v JOIN drafts d ON d.id = v.draft_id "
            "AND d.current_revision = v.revision WHERE d.id = ?",
            (draft_id,),
        ).fetchone()
        return row["text"] if row else ""

    def _current_images(self, draft_id: str) -> list[dict]:
        """Entrées d'images de la révision courante (« images » ; héritage « image »)."""
        row = self.conn.execute(
            "SELECT v.manifest_json FROM draft_versions v JOIN drafts d ON d.id = v.draft_id "
            "AND d.current_revision = v.revision WHERE d.id = ?",
            (draft_id,),
        ).fetchone()
        if row is None:
            return []
        try:
            manifest = json.loads(row["manifest_json"])
        except json.JSONDecodeError:
            return []
        images = manifest.get("images")
        if isinstance(images, list):
            return [entry for entry in images if isinstance(entry, dict)]
        legacy = manifest.get("image")
        return [legacy] if isinstance(legacy, dict) else []

    # ---------------------------------------------------------------- brouillon

    def _save_text(self, text: str) -> None:
        draft_id = self._active_draft()
        note = ""
        if draft_id and self._current_text(draft_id).strip():
            # Un brouillon existe déjà : le message est une consigne, une
            # critique, ou le texte final complet. Interprétation par le LLM.
            revision = self._llm_revise(draft_id, text)
            if revision is not None:
                text, note = revision
        if not draft_id:
            draft_id = store.create_draft(self.conn)
            store.set_setting(self.conn, "active_draft", draft_id)
        manifest = self._manifest(text, images=self._current_images(draft_id))
        try:
            revision = store.add_revision(self.conn, draft_id, text, manifest)
        except store.StoreError as exc:
            self._reply(f"Enregistrement refusé ({exc.code}) : {exc}")
            return
        if len(text) > 3000:
            self._reply(
                f"ATTENTION : {len(text)} caractères — LinkedIn refuse un commentary "
                "au-delà de 3 000. Raccourcissez avant publication."
            )
        self._reply(
            f"Révision {revision} enregistrée{note}. "
            "/preview pour vérifier et valider le texte exact."
        )

    def _llm_revise(self, draft_id: str, message: str) -> tuple[str, str] | None:
        """Interprète le message libre PAR LE LLM (consigne, texte, ou les deux).

        - adaptateur simulé → None : le texte brut est enregistré sans
          « interprétation » simulée ;
        - erreur LLM → (texte brut, note) : enregistré tel quel, jamais bloquant ;
        - sortie vide ou identique au brouillon → None.
        La sortie reste une PROPOSITION de brouillon : elle ne valide rien et
        ne publie rien ; les validations TEXT/IMAGE/FINAL restent requises.
        """
        provider = self._llm()
        if not getattr(provider, "is_real", False):
            return None
        settings = self._research_settings()
        prompt = research_mod.build_revision_prompt(
            self._current_text(draft_id),
            message,
            tone=settings["tone"],
            language=settings["language"],
        )
        try:
            result = provider.generate("draft_revision", prompt)
        except Exception as exc:  # noqa: BLE001 — le texte brut reste enregistré
            code = getattr(exc, "code", type(exc).__name__)
            return message, f" (interprétation LLM impossible ({code}) — texte enregistré tel quel)"
        new_text = (result.text or "").strip()
        if not new_text or new_text == self._current_text(draft_id).strip():
            return None
        return new_text, f" (reformulée par {result.provider}/{result.model})"

    def _preview(self) -> None:
        draft_id = self._active_draft()
        if not draft_id:
            self._reply("Aucun brouillon actif. /new ou envoyez directement un texte.")
            return
        draft = self.conn.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,)).fetchone()
        if draft is None or draft["current_revision"] == 0:
            self._reply("Brouillon vide. Envoyez le texte du post.")
            return
        store.set_setting(self.conn, "image_mode", "")
        version = self.conn.execute(
            "SELECT text FROM draft_versions WHERE draft_id = ? AND revision = ?",
            (draft_id, draft["current_revision"]),
        ).fetchone()
        self._reply(f"Aperçu — révision {draft['current_revision']} (texte exact) :\n\n{version['text']}")
        images = self._current_images(draft_id)
        missing = False
        for index, entry in enumerate(images, start=1):
            asset = self.buffer.get(entry.get("token"))
            if asset is None:
                missing = True
                continue
            try:
                self.client.send_photo(
                    self.config.chat_id,
                    asset.data,
                    caption=f"Image jointe {index}/{len(images)} "
                    f"(révision {draft['current_revision']}, {asset.content_type})",
                    content_type=asset.content_type,
                )
            except Exception:  # noqa: BLE001 — l'aperçu photo est un bonus
                pass
        if missing:
            self._reply(
                "ATTENTION : au moins une image n'est plus en mémoire (redémarrage du bot). "
                "Renvoyez les photos, puis /preview à nouveau."
            )
            return
        self._reply(
            "Validez ce texte exact, puis l'image (ou son absence), puis l'autorisation finale.",
            keyboard(
                [
                    ("Approuver le texte", f"text:{draft_id}"),
                    ("🖼 Ajouter une image", f"imgadd:{draft_id}"),
                ]
            ),
        )

    # -------------------------------------------------------------- validations

    def _callback(self, callback: dict) -> None:
        self.client.answer_callback(callback["id"])
        data = callback.get("data", "")
        actor = str(self.config.owner_id)
        try:
            if data.startswith("text:"):
                self._approve_text(data[5:], actor)
            elif data.startswith("image:"):
                self._approve_image(data[6:], actor)
            elif data.startswith("noimg:"):
                self._approve_no_image(data[6:], actor)
            elif data.startswith("pub:"):
                self._final_publish(data[4:], actor)
            elif data.startswith("imgadd:"):
                self._image_add_mode(data[7:])
            elif data.startswith("use:"):
                self._use_proposed(data[4:])
            elif data.startswith("lang:"):
                self._language_command(data[5:])
            elif data.startswith("resume:"):
                self._resume_draft(data[7:])
            else:
                self._reply("Bouton inconnu ou expiré. Refaites /preview.")
        except store.StoreError as exc:
            self._reply(f"Action refusée ({exc.code}) : {exc}")

    def _draft_revision(self, draft_id: str) -> int:
        draft = self.conn.execute("SELECT current_revision FROM drafts WHERE id = ?", (draft_id,)).fetchone()
        if draft is None or draft["current_revision"] == 0:
            raise store.StoreError("DRAFT_NOT_FOUND", "brouillon absent ou vide")
        return draft["current_revision"]

    def _approve_text(self, draft_id: str, actor: str) -> None:
        revision = self._draft_revision(draft_id)
        if store.find_valid_approval(self.conn, draft_id, revision, "TEXT") is None:
            store.record_approval(self.conn, draft_id, revision, "TEXT", actor, expires_at=self._expiry())
        images = self._current_images(draft_id)
        if images:
            missing = [entry for entry in images if self.buffer.get(entry.get("token")) is None]
            if missing:
                self._reply(
                    "Image perdue (redémarrage) : impossible d'approuver. "
                    "Renvoyez les photos, puis /preview à nouveau."
                )
                return
            self._reply(
                f"Texte approuvé (révision {revision}). Approuvez maintenant les {len(images)} image(s) exacte(s).",
                keyboard(
                    [
                        ("Approuver les images", f"image:{draft_id}"),
                        ("🖼 Ajouter une image", f"imgadd:{draft_id}"),
                    ]
                ),
            )
            return
        self._reply(
            f"Texte approuvé (révision {revision}). Ajoutez une image si vous voulez, "
            "ou validez l'absence d'image.",
            keyboard(
                [
                    ("🖼 Ajouter une image", f"imgadd:{draft_id}"),
                    ("Sans image", f"noimg:{draft_id}"),
                ]
            ),
        )

    def _approve_image(self, draft_id: str, actor: str) -> None:
        revision = self._draft_revision(draft_id)
        images = self._current_images(draft_id)
        if not images:
            raise store.StoreError("NO_IMAGE", "aucune image à approuver sur cette révision")
        hashes = []
        for entry in images:
            asset = self.buffer.get(entry.get("token"))
            if asset is None:
                raise store.StoreError(
                    "IMAGE_BUFFER_LOST", "image perdue au redémarrage ; renvoyez la photo et refaites /preview"
                )
            if entry.get("sha256") and entry["sha256"] != asset.sha256:
                raise store.StoreError("IMAGE_MISMATCH", "les octets ne correspondent pas à l'image approuvée")
            hashes.append(asset.sha256)
        if store.find_valid_approval(self.conn, draft_id, revision, "IMAGE") is None:
            store.record_approval(self.conn, draft_id, revision, "IMAGE", actor, expires_at=self._expiry())
        self._reply(
            f"{len(images)} image(s) approuvée(s) (empreintes {', '.join(h[:12] for h in hashes)}). "
            "Autorisation finale ci-dessous : elle vaut pour CETTE révision exacte.",
            keyboard([(self._publish_label(), self._final_button(draft_id, revision))]),
        )

    def _final_button(self, draft_id: str, revision: int) -> str:
        """Réserve l'autorisation finale et renvoie son identifiant de bouton."""
        final_id = store.find_valid_approval(self.conn, draft_id, revision, "FINAL")
        if final_id is None:
            final_id = store.record_approval(
                self.conn, draft_id, revision, "FINAL", str(self.config.owner_id), expires_at=self._expiry()
            )
        return f"pub:{final_id}"

    def _approve_no_image(self, draft_id: str, actor: str) -> None:
        revision = self._draft_revision(draft_id)
        if store.find_valid_approval(self.conn, draft_id, revision, "NO_IMAGE") is None:
            store.record_approval(self.conn, draft_id, revision, "NO_IMAGE", actor, expires_at=self._expiry())
        self._reply(
            "Absence d'image validée. Autorisation finale ci-dessous : elle vaut pour CETTE révision exacte. "
            "Toute modification du texte ou de l'image l'invalide.",
            keyboard([(self._publish_label(), self._final_button(draft_id, revision))]),
        )

    def _final_publish(self, approval_id: str, actor: str) -> None:
        intent_id = store.consume_final_and_create_intent(self.conn, approval_id, actor)
        outcome = publish(self.conn, intent_id, self.publisher)
        if outcome == "PUBLISHED":
            self._reply(
                "Publication enregistrée et texte exact archivé. "
                + ("" if self._is_real_publisher() else SIMULATION_NOTE)
            )
        elif outcome == "FAILED":
            self._reply("Refus documenté : aucune publication. Une nouvelle autorisation sera requise.")
        else:
            self._reply(
                "Résultat incertain : l'envoi a pu aboutir. Compte verrouillé, aucun retry automatique. "
                "Réconciliation explicite requise avant toute nouvelle publication."
            )

    # ------------------------------------------------------------------ divers

    def _declare_publication(self, value: str) -> None:
        if not value:
            self._reply("Usage : /lastpost <date ISO>, ex. /lastpost 2026-11-10T09:00:00+01:00")
            return
        try:
            declared = datetime.fromisoformat(value)
        except ValueError:
            self._reply("Date invalide. Usage : /lastpost 2026-11-10T09:00:00+01:00")
            return
        now = datetime.now(timezone.utc)
        date_only = "T" not in value and " " not in value
        if date_only:
            precision = "day"
            if declared.date() > now.astimezone(reminders.TZ).date():
                self._reply("Date future refusée : déclarez une publication déjà effectuée.")
                return
        else:
            precision = "second"
            if declared.tzinfo is None:
                self._reply("Ajoutez le décalage horaire, ex. 2026-11-10T09:00:00+01:00.")
                return
            if declared > now:
                self._reply("Date future refusée : déclarez une publication déjà effectuée.")
                return
        post_id = store.new_id()
        version_id = store.new_id()
        now_iso = store.utcnow()
        with transaction(self.conn):
            self.conn.execute(
                "INSERT INTO history_posts (id, account, current_version, published_at, published_at_precision, published_at_tz, confirmed_at, visibility, created_at, updated_at) "
                "VALUES (?, ?, 1, ?, ?, NULL, NULL, NULL, ?, ?)",
                (post_id, self.config.linkedin_account, value, precision, now_iso, now_iso),
            )
            self.conn.execute(
                "INSERT INTO history_versions (id, post_id, version, text, exact_hash, normalized_hash, norm_version, authorship, observed_at) VALUES (?, ?, 1, '', ?, ?, ?, 'user', ?)",
                (version_id, post_id, sha256_text(""), normalized_hash(""), NORM_VERSION, now_iso),
            )
            self.conn.execute(
                "INSERT INTO history_sources (id, post_id, version_id, origin, method, imported_at, fields_json, policy_json) "
                "VALUES (?, ?, ?, 'user_declared', 'telegram_declaration', ?, ?, ?)",
                (
                    store.new_id(),
                    post_id,
                    version_id,
                    now_iso,
                    '{"declared_via":"telegram"}',
                    '{"storage":"allowed","basis":"déclaration directe de l’utilisateur"}',
                ),
            )
        self._reply(
            f"Publication externe déclarée : {value} (précision {precision}). "
            "Les rappels utilisent cette date attestée, jamais la date d'import."
        )

    def _settings_command(self, arg: str) -> None:
        if not arg:
            self._reply(prefs.display(self.conn))
            return
        parts = arg.split(None, 1)
        key = parts[0].strip()
        if len(parts) == 1:
            try:
                self._reply(prefs.show(self.conn, key))
            except prefs.PreferencesError as exc:
                self._reply(f"Réglage refusé ({exc.code}) : {exc}")
            return
        try:
            normalized = prefs.set_value(self.conn, key, parts[1].strip())
        except prefs.PreferencesError as exc:
            self._reply(f"Réglage refusé ({exc.code}) : {exc}")
            return
        self._reply(f"Réglage enregistré : {key} = {normalized}. Même base que le tableau de bord.")

    def _language_command(self, arg: str) -> None:
        """Langue des posts générés : /language fr|en|ar (ou boutons)."""
        value = (arg or "").strip().lower()
        if not value:
            try:
                current = prefs.get(self.conn, "editorial_language") or "fr"
            except prefs.PreferencesError:
                current = "fr"
            self._reply(
                f"Langue des posts : {current}. Choisissez :",
                keyboard(
                    [
                        ("Français", "lang:fr"),
                        ("English", "lang:en"),
                        ("العربية", "lang:ar"),
                    ]
                ),
            )
            return
        try:
            normalized = prefs.set_value(self.conn, "editorial_language", value)
        except prefs.PreferencesError as exc:
            self._reply(f"Langue refusée ({exc.code}) : {exc}. Choix : fr, en, ar.")
            return
        self._reply(
            f"Langue des posts : {normalized}. Les prochaines générations (dossier, recherche, "
            "lien, /humanize) utiliseront cette langue."
        )

    HUMANIZE_INSTRUCTION = (
        "Réécris ce post pour qu'il sonne vraiment humain, comme écrit par une personne "
        "réelle et non par une IA. Varie le rythme (phrases courtes et longues), garde un "
        "ton direct et personnel à la première personne, utilise des formulations concrètes. "
        "Supprime les tournures d'IA (« il est important de noter », « plongeons », "
        "« dans un monde où », « n'est-ce pas ? »), les tirets cadratins, les emojis, les "
        "hashtags et les listes à puces. Conserve les faits, le sens et la langue du texte."
    )

    def _humanize_command(self) -> None:
        """Réécrit le brouillon actif pour un ton plus humain (nouvelle révision)."""
        draft_id = self._active_draft()
        if not draft_id or not self._current_text(draft_id).strip():
            self._reply("Aucun brouillon actif avec du texte. /new, /folder d1 ou un texte d'abord.")
            return
        result = self._llm_revise(draft_id, self.HUMANIZE_INSTRUCTION)
        if result is None:
            self._reply(
                "Humanisation impossible (modèle simulé/indisponible ou texte inchangé). "
                "Vérifiez /settings llm_provider et llm_model."
            )
            return
        text, note = result
        manifest = self._manifest(text, images=self._current_images(draft_id))
        try:
            revision = store.add_revision(self.conn, draft_id, text, manifest)
        except store.StoreError as exc:
            self._reply(f"Enregistrement refusé ({exc.code}) : {exc}")
            return
        self._reply(
            f"Texte humanisé{note} — révision {revision} :\n\n{text}\n\n"
            "/preview pour vérifier et valider le texte exact."
        )

    def _drafts_command(self) -> None:
        """Liste les brouillons sauvegardés (hors publiés) et permet d'en reprendre un."""
        rows = self.conn.execute(
            "SELECT d.id, d.state, d.current_revision, d.updated_at, v.text "
            "FROM drafts d LEFT JOIN draft_versions v ON v.draft_id = d.id "
            "AND v.revision = d.current_revision "
            "WHERE d.current_revision > 0 AND d.state != 'PUBLISHED' "
            "ORDER BY d.updated_at DESC LIMIT 10"
        ).fetchall()
        if not rows:
            self._reply("Aucun brouillon sauvegardé (hors publications). /new ou /folder pour commencer.")
            return
        lines = [
            "Brouillons sauvegardés (les images vivent en RAM : perdues après redémarrage) :",
            "",
        ]
        buttons = []
        for index, row in enumerate(rows, start=1):
            preview = " ".join((row["text"] or "").split())[:50] or "(vide)"
            lines.append(f"{index}. [{row['state']}] rev {row['current_revision']} — {preview}")
            buttons.append((f"Reprendre {index}", f"resume:{row['id']}"))
        lines += ["", "Reprendre réactive le brouillon : /preview pour valider, consignes libres pour corriger."]
        self._reply("\n".join(lines), keyboard(buttons))

    def _resume_draft(self, draft_id: str) -> None:
        row = self.conn.execute(
            "SELECT state, current_revision FROM drafts WHERE id = ?", (draft_id,)
        ).fetchone()
        if row is None or row["current_revision"] == 0:
            self._reply("Brouillon introuvable ou vide.")
            return
        if row["state"] == "PUBLISHED":
            self._reply("Ce brouillon est déjà publié ; un doublon serait refusé à l'envoi.")
            return
        if row["state"] == "BLOCKED":
            self._reply(
                "Ce brouillon est bloqué (échec ou résultat incertain) : résolution explicite "
                "requise avant toute nouvelle publication. /status pour l'état."
            )
            return
        store.set_setting(self.conn, "active_draft", draft_id)
        text = self._current_text(draft_id)
        images = self._current_images(draft_id)
        note = ""
        if images:
            note = (
                f"\n\n⚠ {len(images)} image(s) référencée(s) mais les octets approuvés ne sont "
                "plus en RAM : renvoyez la photo ou /folder i<n> pour la rattacher, puis /preview."
            )
        self._reply(
            f"Brouillon réactivé (révision {row['current_revision']}) :\n\n{text}\n\n"
            "/preview pour valider (nouvelles validations texte/image requises), "
            "ou un message libre pour corriger." + note
        )

    def _reminder_command(self, arg: str) -> None:
        if arg == "on":
            reminders.set_enabled(self.conn, True)
            settings = reminders._settings(self.conn)
            days = ",".join(str(d) for d in sorted(settings["days"]))
            self._reply(
                f"Rappels activés : {settings['hour']} h ({days}), seuil {settings['inactivity_hours']} h, "
                "Africa/Tunis (paramètres proposés, modifiables via /settings)."
            )
        elif arg == "off":
            reminders.set_enabled(self.conn, False)
            self._reply("Rappels désactivés. Le bot reste utilisable sans rappels.")
        else:
            settings = reminders._settings(self.conn)
            self._reply(
                f"Rappels : {'activés' if settings['enabled'] else 'désactivés'}, "
                f"heure {settings['hour']} h, jours {sorted(settings['days'])}, "
                f"seuil {settings['inactivity_hours']} h, dernier envoi {settings['last_date'] or 'jamais'}."
            )

    def _status(self) -> str:
        lines = [
            "SIMULATION — aucun jeton Telegram configuré." if self.config.simulation else "Telegram configuré.",
            "Publication LinkedIn : REELLE (adaptateur treg)."
            if self._is_real_publisher()
            else "Publication LinkedIn : SIMULATION (aucun envoi réel).",
            f"Compte LinkedIn : {self.config.linkedin_account}",
            f"Images en mémoire : {len(self.buffer)} (RAM seule, perdues au redémarrage).",
        ]
        draft_id = self._active_draft()
        if draft_id:
            draft = self.conn.execute("SELECT state, current_revision FROM drafts WHERE id = ?", (draft_id,)).fetchone()
            if draft is not None:
                lines.append(f"Brouillon actif : {draft['state']}, révision {draft['current_revision']}")
        pending = self._pending_research()
        if pending:
            lines.append(f"Clarification en attente sur : {pending.get('topic')}")
        lock = self.conn.execute(
            "SELECT state FROM publication_intents WHERE state IN ('CREATED','SENDING','UNKNOWN_OUTCOME') ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        if lock is not None:
            lines.append(f"Verrou de publication actif : {lock['state']}")
        count = self.conn.execute("SELECT COUNT(*) c FROM history_posts").fetchone()["c"]
        lines.append(f"Archive : {count} publication(s) confirmée(s).")
        return "\n".join(lines)
