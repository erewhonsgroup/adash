PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pcs (
  id TEXT PRIMARY KEY,
  hostname TEXT NOT NULL,
  role TEXT NOT NULL DEFAULT 'satellite'
);

CREATE TABLE IF NOT EXISTS projects (
  id TEXT NOT NULL,
  pc TEXT NOT NULL,
  title TEXT NOT NULL DEFAULT '',
  path TEXT NOT NULL DEFAULT '',
  command TEXT NOT NULL DEFAULT '',
  groups_json TEXT NOT NULL DEFAULT '[]',
  family TEXT NOT NULL DEFAULT '',
  purpose TEXT NOT NULL DEFAULT '',
  source TEXT NOT NULL DEFAULT 'manual',
  exists_on_disk INTEGER NOT NULL DEFAULT 0,
  is_git INTEGER NOT NULL DEFAULT 0,
  git_branch TEXT NOT NULL DEFAULT '',
  git_dirty TEXT NOT NULL DEFAULT '',
  origin TEXT NOT NULL DEFAULT '',
  state TEXT NOT NULL DEFAULT 'idle',
  task TEXT NOT NULL DEFAULT '',
  note TEXT NOT NULL DEFAULT '',
  blocker TEXT NOT NULL DEFAULT '',
  evidence TEXT NOT NULL DEFAULT '',
  verification TEXT NOT NULL DEFAULT '',
  updated_at TEXT NOT NULL DEFAULT '',
  last_launch TEXT NOT NULL DEFAULT '',
  attention_score INTEGER NOT NULL DEFAULT 100,
  attention TEXT NOT NULL DEFAULT 'idle',
  reason TEXT NOT NULL DEFAULT '',
  ingested_at TEXT NOT NULL DEFAULT '',
  PRIMARY KEY (id, pc)
);

CREATE INDEX IF NOT EXISTS idx_projects_attention ON projects (attention_score, pc, id);
CREATE INDEX IF NOT EXISTS idx_projects_state ON projects (state, pc);
CREATE INDEX IF NOT EXISTS idx_projects_path ON projects (path);

CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  time TEXT NOT NULL,
  project_id TEXT NOT NULL,
  pc TEXT NOT NULL DEFAULT '',
  event_type TEXT NOT NULL DEFAULT '',
  state TEXT NOT NULL DEFAULT '',
  previous_state TEXT NOT NULL DEFAULT '',
  task TEXT NOT NULL DEFAULT '',
  note TEXT NOT NULL DEFAULT '',
  source TEXT NOT NULL DEFAULT '',
  payload_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_events_project ON events (project_id, pc, time);
CREATE INDEX IF NOT EXISTS idx_events_time ON events (time);
