from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

from . import extracting, media, prefs, reminders, research as research_mod, searching, store
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
                "recherché, /link <url> part d'un article, envoyez une photo pour illustrer, "
                "/lastpost déclare une publication externe, /reminder on|off gère les rappels, "
                "/settings liste et ajuste les paramètres progressifs. "
                "Aucune publication sans bouton final dédié. "
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
        if text.startswith("/"):
            self._reply(
                "Commande inconnue. /start, /new, /preview, /status, /cancel, /lastpost, "
                "/reminder, /settings, /research, /link, /image."
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

    def _style_context(self) -> str:
        """Profil de style descriptif (recalculable), jamais une règle normative."""
        try:
            from . import profile as profile_mod

            data = profile_mod.get(self.conn, self.config.linkedin_account)
        except Exception:  # noqa: BLE001 — le style est un bonus, jamais un bloquant
            return ""
        if not data:
            return ""
        prof = data.get("profile") or {}
        length = prof.get("length") or {}
        terms = [term for term, _count in (prof.get("top_terms") or [])[:12]]
        if not terms and not length:
            return ""
        parts = []
        if length.get("avg"):
            parts.append(f"longueur moyenne observée : {length['avg']} caractères")
        if terms:
            parts.append("termes récurrents : " + ", ".join(terms))
        return " ; ".join(parts)

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
                style_context=self._style_context(),
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
            f"Sources lues :\n{sources}\n\n"
            "Corrigez le texte librement (chaque message crée une révision), "
            "ajoutez une photo si vous le souhaitez, puis /preview pour valider."
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
            style_context=self._style_context(),
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
            f"Source : {source.title} — {source.url}\n\n"
            "Corrigez si besoin, ajoutez une photo, puis /preview pour valider."
        )

    def _create_draft(self, text: str) -> str:
        draft_id = store.create_draft(self.conn)
        store.set_setting(self.conn, "active_draft", draft_id)
        store.add_revision(self.conn, draft_id, text, self._manifest(text))
        return draft_id

    # ------------------------------------------------------------------ images

    def _manifest(self, text: str, image: dict | None = None) -> dict:
        return {
            "account": self.config.linkedin_account,
            "visibility": self._visibility(),
            "image": image,
        }

    def _visibility(self) -> str:
        """PUBLIC ou CONNECTIONS, choisi par paramètre (jamais implicite)."""
        try:
            value = prefs.get(self.conn, "post_visibility")
        except prefs.PreferencesError:
            value = None
        return "CONNECTIONS" if (value or "public").strip().lower() == "connections" else "PUBLIC"

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
        """Attache l'image au brouillon actif en créant une révision."""
        draft_id = self._active_draft()
        if not draft_id:
            draft_id = self._create_draft("")
        text = self._current_text(draft_id)
        manifest = self._manifest(text, image=asset.manifest_entry())
        try:
            revision = store.add_revision(self.conn, draft_id, text, manifest)
        except store.StoreError as exc:
            self._reply(f"Image non attachée ({exc.code}) : {exc}")
            return
        self._reply(
            f"Image attachée ({asset.content_type}, {asset.size} octets, empreinte {asset.sha256[:12]}). "
            f"Révision {revision}. /preview pour voir le rendu et valider l'image exacte."
        )

    def _current_text(self, draft_id: str) -> str:
        row = self.conn.execute(
            "SELECT v.text FROM draft_versions v JOIN drafts d ON d.id = v.draft_id "
            "AND d.current_revision = v.revision WHERE d.id = ?",
            (draft_id,),
        ).fetchone()
        return row["text"] if row else ""

    def _current_image(self, draft_id: str) -> dict | None:
        row = self.conn.execute(
            "SELECT v.manifest_json FROM draft_versions v JOIN drafts d ON d.id = v.draft_id "
            "AND d.current_revision = v.revision WHERE d.id = ?",
            (draft_id,),
        ).fetchone()
        if row is None:
            return None
        try:
            manifest = json.loads(row["manifest_json"])
        except json.JSONDecodeError:
            return None
        return manifest.get("image")

    # ---------------------------------------------------------------- brouillon

    def _save_text(self, text: str) -> None:
        draft_id = self._active_draft()
        if not draft_id:
            draft_id = store.create_draft(self.conn)
            store.set_setting(self.conn, "active_draft", draft_id)
        manifest = self._manifest(text, image=self._current_image(draft_id))
        try:
            revision = store.add_revision(self.conn, draft_id, text, manifest)
        except store.StoreError as exc:
            self._reply(f"Enregistrement refusé ({exc.code}) : {exc}")
            return
        self._reply(f"Révision {revision} enregistrée. /preview pour vérifier et valider le texte exact.")

    def _preview(self) -> None:
        draft_id = self._active_draft()
        if not draft_id:
            self._reply("Aucun brouillon actif. /new ou envoyez directement un texte.")
            return
        draft = self.conn.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,)).fetchone()
        if draft is None or draft["current_revision"] == 0:
            self._reply("Brouillon vide. Envoyez le texte du post.")
            return
        version = self.conn.execute(
            "SELECT text FROM draft_versions WHERE draft_id = ? AND revision = ?",
            (draft_id, draft["current_revision"]),
        ).fetchone()
        self._reply(f"Aperçu — révision {draft['current_revision']} (texte exact) :\n\n{version['text']}")
        image = self._current_image(draft_id)
        if image:
            asset = self.buffer.get(image.get("token"))
            if asset is None:
                self._reply(
                    "ATTENTION : l'image n'est plus en mémoire (redémarrage du bot). "
                    "Renvoyez la photo, puis /preview à nouveau."
                )
                return
            try:
                self.client.send_photo(
                    self.config.chat_id,
                    asset.data,
                    caption=f"Image jointe (révision {draft['current_revision']}, {asset.content_type})",
                )
            except Exception:  # noqa: BLE001 — l'aperçu photo est un bonus
                pass
        self._reply(
            "Validez ce texte exact, puis l'image (ou son absence), puis l'autorisation finale.",
            keyboard([("Approuver le texte", f"text:{draft_id}")]),
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
        image = self._current_image(draft_id)
        if image:
            asset = self.buffer.get(image.get("token"))
            if asset is None:
                self._reply(
                    "Image perdue (redémarrage) : impossible d'approuver. "
                    "Renvoyez la photo, puis /preview à nouveau."
                )
                return
            self._reply(
                f"Texte approuvé (révision {revision}). Approuvez maintenant l'image exacte "
                f"({asset.content_type}, {asset.size} octets).",
                keyboard([("Approuver l'image", f"image:{draft_id}")]),
            )
            return
        self._reply(
            f"Texte approuvé (révision {revision}). Validez maintenant l'absence d'image.",
            keyboard([("Sans image", f"noimg:{draft_id}")]),
        )

    def _approve_image(self, draft_id: str, actor: str) -> None:
        revision = self._draft_revision(draft_id)
        image = self._current_image(draft_id)
        if not image:
            raise store.StoreError("NO_IMAGE", "aucune image à approuver sur cette révision")
        asset = self.buffer.get(image.get("token"))
        if asset is None:
            raise store.StoreError(
                "IMAGE_BUFFER_LOST", "image perdue au redémarrage ; renvoyez la photo et refaites /preview"
            )
        if image.get("sha256") and image["sha256"] != asset.sha256:
            raise store.StoreError("IMAGE_MISMATCH", "les octets ne correspondent pas à l'image approuvée")
        if store.find_valid_approval(self.conn, draft_id, revision, "IMAGE") is None:
            store.record_approval(self.conn, draft_id, revision, "IMAGE", actor, expires_at=self._expiry())
        self._reply(
            f"Image approuvée (empreinte {asset.sha256[:12]}). "
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
