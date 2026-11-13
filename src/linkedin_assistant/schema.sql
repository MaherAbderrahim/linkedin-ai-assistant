PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS drafts (
    id TEXT PRIMARY KEY,
    state TEXT NOT NULL,
    current_revision INTEGER NOT NULL DEFAULT 0,
    blocked_reason TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS draft_versions (
    draft_id TEXT NOT NULL REFERENCES drafts(id),
    revision INTEGER NOT NULL,
    text TEXT NOT NULL,
    manifest_json TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    approval_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (draft_id, revision)
);

CREATE TABLE IF NOT EXISTS approvals (
    id TEXT PRIMARY KEY,
    draft_id TEXT NOT NULL REFERENCES drafts(id),
    revision INTEGER NOT NULL,
    kind TEXT NOT NULL,
    actor TEXT NOT NULL,
    object_hash TEXT NOT NULL,
    nonce TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    expires_at TEXT,
    consumed_at TEXT
);

CREATE TABLE IF NOT EXISTS publication_intents (
    id TEXT PRIMARY KEY,
    draft_id TEXT NOT NULL REFERENCES drafts(id),
    account TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    state TEXT NOT NULL,
    approval_id TEXT NOT NULL REFERENCES approvals(id),
    receipt_json TEXT,
    history_post_id TEXT,
    error TEXT,
    created_at TEXT NOT NULL,
    sending_at TEXT,
    resolved_at TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS one_active_intent_per_draft
    ON publication_intents(draft_id)
    WHERE state IN ('CREATED', 'SENDING', 'UNKNOWN_OUTCOME');

CREATE UNIQUE INDEX IF NOT EXISTS one_active_intent_per_account
    ON publication_intents(account)
    WHERE state IN ('CREATED', 'SENDING', 'UNKNOWN_OUTCOME');

CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'NEW',
    created_at TEXT NOT NULL,
    processed_at TEXT,
    UNIQUE (source, external_id)
);

CREATE TABLE IF NOT EXISTS preferences (
    id TEXT PRIMARY KEY,
    rule_text TEXT NOT NULL,
    scope TEXT NOT NULL DEFAULT 'global',
    approval_id TEXT REFERENCES approvals(id),
    created_at TEXT NOT NULL,
    revoked_at TEXT
);

CREATE TABLE IF NOT EXISTS quota_usage (
    provider TEXT NOT NULL,
    window TEXT NOT NULL,
    unit TEXT NOT NULL,
    reserved INTEGER NOT NULL DEFAULT 0,
    consumed INTEGER NOT NULL DEFAULT 0,
    cap INTEGER,
    PRIMARY KEY (provider, window, unit)
);

CREATE TABLE IF NOT EXISTS history_posts (
    id TEXT PRIMARY KEY,
    account TEXT NOT NULL,
    current_version INTEGER NOT NULL DEFAULT 1,
    published_at TEXT,
    published_at_precision TEXT,
    published_at_tz TEXT,
    confirmed_at TEXT,
    visibility TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS history_versions (
    id TEXT PRIMARY KEY,
    post_id TEXT NOT NULL REFERENCES history_posts(id),
    version INTEGER NOT NULL,
    text TEXT NOT NULL,
    exact_hash TEXT NOT NULL,
    normalized_hash TEXT NOT NULL,
    norm_version TEXT NOT NULL,
    authorship TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    UNIQUE (post_id, version)
);

CREATE TABLE IF NOT EXISTS history_identifiers (
    id TEXT PRIMARY KEY,
    post_id TEXT NOT NULL REFERENCES history_posts(id),
    namespace TEXT NOT NULL,
    identifier TEXT NOT NULL,
    source_id TEXT,
    UNIQUE (namespace, identifier)
);

CREATE TABLE IF NOT EXISTS history_sources (
    id TEXT PRIMARY KEY,
    post_id TEXT NOT NULL REFERENCES history_posts(id),
    version_id TEXT REFERENCES history_versions(id),
    origin TEXT NOT NULL,
    method TEXT NOT NULL,
    provider TEXT,
    provider_ref TEXT,
    imported_at TEXT NOT NULL,
    fields_json TEXT NOT NULL DEFAULT '{}',
    policy_json TEXT NOT NULL DEFAULT '{}',
    expires_at TEXT
);

CREATE TABLE IF NOT EXISTS import_batches (
    id TEXT PRIMARY KEY,
    origin TEXT NOT NULL,
    batch_hash TEXT NOT NULL UNIQUE,
    schema_version TEXT NOT NULL,
    plan_json TEXT NOT NULL,
    decisions_json TEXT,
    state TEXT NOT NULL,
    created_at TEXT NOT NULL,
    committed_at TEXT
);

CREATE TABLE IF NOT EXISTS style_profile (
    id TEXT PRIMARY KEY,
    profile_json TEXT NOT NULL,
    source_refs_json TEXT NOT NULL,
    coverage TEXT,
    computed_at TEXT NOT NULL,
    valid INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_history_posts_account_date
    ON history_posts(account, published_at);
CREATE INDEX IF NOT EXISTS idx_history_versions_norm
    ON history_versions(normalized_hash);
CREATE INDEX IF NOT EXISTS idx_history_sources_expiry
    ON history_sources(expires_at);
CREATE INDEX IF NOT EXISTS idx_draft_versions_content
    ON draft_versions(content_hash);
