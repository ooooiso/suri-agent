-- 初始数据库 Schema
-- 归属：suri_core

CREATE TABLE IF NOT EXISTS plugins (
    plugin_id   TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    version     TEXT NOT NULL,
    type        TEXT NOT NULL,
    path        TEXT NOT NULL,
    status      TEXT DEFAULT 'inactive',
    capabilities TEXT,
    manifest    TEXT,
    last_heartbeat TEXT,
    created_at  TEXT,
    updated_at  TEXT
);

CREATE INDEX IF NOT EXISTS idx_plugins_status ON plugins(status);
CREATE INDEX IF NOT EXISTS idx_plugins_type ON plugins(type);

CREATE TABLE IF NOT EXISTS events (
    event_id    TEXT PRIMARY KEY,
    event_type  TEXT NOT NULL,
    source      TEXT NOT NULL,
    target      TEXT,
    payload     TEXT,
    priority    TEXT NOT NULL,
    timestamp   TEXT NOT NULL,
    consumed    INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_source ON events(source);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_events_consumed ON events(consumed) WHERE consumed = 0;
