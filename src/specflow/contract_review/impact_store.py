"""Additive discovery records; existing review migration checksums stay frozen."""

IMPACT_DDL = (
    "CREATE TABLE contract_impact_discoveries (id TEXT PRIMARY KEY, project_id TEXT NOT NULL "
    "REFERENCES projects(id), snapshot_id TEXT NOT NULL REFERENCES contract_review_snapshots(id), "
    "status TEXT NOT NULL CHECK(status IN "
    "('queued','running','completed','failed','interrupted')), "
    "version INTEGER NOT NULL, body TEXT NOT NULL, created_at TEXT NOT NULL, "
    "event_seq INTEGER NOT NULL DEFAULT 0, record_bytes INTEGER NOT NULL DEFAULT 0)",
    "CREATE TABLE contract_impact_calls (id TEXT PRIMARY KEY, discovery_id TEXT NOT NULL "
    "REFERENCES contract_impact_discoveries(id), status TEXT NOT NULL, body TEXT NOT NULL)",
    "CREATE INDEX contract_impact_calls_by_discovery ON contract_impact_calls(discovery_id,id)",
    "CREATE TABLE contract_impact_events (id TEXT PRIMARY KEY, discovery_id TEXT NOT NULL "
    "REFERENCES contract_impact_discoveries(id), event_seq INTEGER NOT NULL, "
    "event_type TEXT NOT NULL, "
    "body TEXT NOT NULL, payload TEXT NOT NULL, UNIQUE(discovery_id,event_seq))",
    "CREATE TABLE contract_impact_adoptions (id TEXT PRIMARY KEY, discovery_id TEXT NOT NULL "
    "REFERENCES contract_impact_discoveries(id), review_id TEXT REFERENCES contract_reviews(id), "
    "input_id TEXT REFERENCES contract_review_inputs(id), body TEXT NOT NULL, "
    "created_at TEXT NOT NULL)",
    "ALTER TABLE contract_review_runtime ADD COLUMN slot_discovery_call_id TEXT "
    "REFERENCES contract_impact_calls(id)",
)
