from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone

from . import prefs, reminders, store
from .config import Config
from .db import transaction
from .hashing import NORM_VERSION, normalized_hash, sha256_text
from .publisher import publish
from .telegram import TelegramClient, escape_html, is_authorized, keyboard, split_message

SIMULATION_NOTE = "Mode simulation : aucune publication réelle sur LinkedIn."


class Conversation:
    def __init__(self, conn: sqlite3.Connection, config: Config, client: TelegramClient, publisher):
        self.conn = conn
        self.config = config
        self.client = client
        self.publisher = publisher

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

    def _message(self, message: dict) -> None:
        text = message.get("text")
        if text is None:
            self._reply("Phase 2 : seuls les messages texte sont traités.")
            return
        text = text.strip()
        if text == "/start":
            self._reply(
                "Assistant LinkedIn personnel. /new crée un brouillon, envoyez ensuite le texte, "
                "/preview affiche l'aperçu et les validations. /lastpost déclare une publication externe, "
                "/reminder on|off gère les rappels, /settings liste et ajuste les paramètres progressifs. "
                "Aucune publication sans bouton final dédié. "
                + SIMULATION_NOTE
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
        if text.startswith("/"):
            self._reply("Commande inconnue. /start, /new, /preview, /status, /cancel, /lastpost, /reminder, /settings.")
            return
        self._save_text(text)

    def _save_text(self, text: str) -> None:
        draft_id = self._active_draft()
        if not draft_id:
            draft_id = store.create_draft(self.conn)
            store.set_setting(self.conn, "active_draft", draft_id)
        manifest = {
            "account": self.config.linkedin_account,
            "visibility": "PUBLIC",
            "image_hash": None,
        }
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
        self._reply(
            "Validez ce texte exact, puis l'absence d'image, puis l'autorisation finale.",
            keyboard([("Approuver le texte", f"text:{draft_id}")]),
        )

    def _callback(self, callback: dict) -> None:
        self.client.answer_callback(callback["id"])
        data = callback.get("data", "")
        actor = str(self.config.owner_id)
        try:
            if data.startswith("text:"):
                self._approve_text(data[5:], actor)
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
        self._reply(
            f"Texte approuvé (révision {revision}). Phase 2 : pas d'image, validez l'absence d'image.",
            keyboard([("Sans image", f"noimg:{draft_id}")]),
        )

    def _approve_no_image(self, draft_id: str, actor: str) -> None:
        revision = self._draft_revision(draft_id)
        if store.find_valid_approval(self.conn, draft_id, revision, "NO_IMAGE") is None:
            store.record_approval(self.conn, draft_id, revision, "NO_IMAGE", actor, expires_at=self._expiry())
        final_id = store.find_valid_approval(self.conn, draft_id, revision, "FINAL")
        if final_id is None:
            final_id = store.record_approval(self.conn, draft_id, revision, "FINAL", actor, expires_at=self._expiry())
        label = "Publier — SIMULATION"
        self._reply(
            "Autorisation finale à usage unique, liée à cette révision exacte. "
            "Toute modification du texte l'invalide.",
            keyboard([(label, f"pub:{final_id}")]),
        )

    def _final_publish(self, approval_id: str, actor: str) -> None:
        intent_id = store.consume_final_and_create_intent(self.conn, approval_id, actor)
        outcome = publish(self.conn, intent_id, self.publisher)
        if outcome == "PUBLISHED":
            self._reply("Publication enregistrée et texte exact archivé. " + SIMULATION_NOTE)
        elif outcome == "FAILED":
            self._reply("Refus documenté : aucune publication. Une nouvelle autorisation sera requise.")
        else:
            self._reply(
                "Résultat incertain : l'envoi a pu aboutir. Compte verrouillé, aucun retry automatique. "
                "Réconciliation explicite requise avant toute nouvelle publication."
            )

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
            "Publication LinkedIn : SIMULATION (phase 2, aucun envoi réel).",
            f"Compte LinkedIn : {self.config.linkedin_account}",
        ]
        draft_id = self._active_draft()
        if draft_id:
            draft = self.conn.execute("SELECT state, current_revision FROM drafts WHERE id = ?", (draft_id,)).fetchone()
            if draft is not None:
                lines.append(f"Brouillon actif : {draft['state']}, révision {draft['current_revision']}")
        lock = self.conn.execute(
            "SELECT state FROM publication_intents WHERE state IN ('CREATED','SENDING','UNKNOWN_OUTCOME') ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        if lock is not None:
            lines.append(f"Verrou de publication actif : {lock['state']}")
        count = self.conn.execute("SELECT COUNT(*) c FROM history_posts").fetchone()["c"]
        lines.append(f"Archive : {count} publication(s) confirmée(s).")
        return "\n".join(lines)