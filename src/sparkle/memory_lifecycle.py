"""Memory lifecycle migration and immutable application-level version history."""

def initialize(db):
    columns = {r['name'] for r in db.execute('PRAGMA table_info(memories)')}
    if 'expires_at' not in columns:
        db.execute('ALTER TABLE memories ADD COLUMN expires_at REAL')
    if 'revoked' not in columns:
        db.execute('ALTER TABLE memories ADD COLUMN revoked INTEGER NOT NULL DEFAULT 0 CHECK(revoked IN (0,1))')
    db.execute('''CREATE TABLE IF NOT EXISTS memory_versions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, memory_id INTEGER NOT NULL,
        action TEXT NOT NULL, snapshot TEXT NOT NULL,
        recorded_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')))''')
    db.execute('CREATE INDEX IF NOT EXISTS memory_versions_record ON memory_versions(memory_id,id)')
    fields = ('id', 'category', 'memory_key', 'value', 'importance', 'metadata',
              'archived', 'expires_at', 'revoked', 'created_at', 'updated_at')
    def snapshot(prefix):
        return 'json_object(' + ','.join(f"'{field}',{prefix}{field}" for field in fields) + ')'
    db.execute(f'''INSERT INTO memory_versions(memory_id,action,snapshot)
        SELECT id,'migration_baseline',{snapshot('memories.')} FROM memories
        WHERE NOT EXISTS(SELECT 1 FROM memory_versions v WHERE v.memory_id=memories.id)''')
    db.execute(f'''CREATE TRIGGER IF NOT EXISTS memory_version_insert AFTER INSERT ON memories BEGIN
        INSERT INTO memory_versions(memory_id,action,snapshot) VALUES(NEW.id,'created',{snapshot('NEW.')}); END''')
    db.execute(f'''CREATE TRIGGER IF NOT EXISTS memory_version_update AFTER UPDATE ON memories BEGIN
        INSERT INTO memory_versions(memory_id,action,snapshot) VALUES(NEW.id,
            CASE WHEN NEW.revoked!=OLD.revoked THEN 'revoked'
                 WHEN NEW.expires_at IS NOT OLD.expires_at THEN 'retention_changed'
                 WHEN NEW.archived!=OLD.archived THEN CASE WHEN NEW.archived=1 THEN 'archived' ELSE 'restored' END
                 ELSE 'superseded' END,{snapshot('NEW.')}); END''')
    db.execute(f'''CREATE TRIGGER IF NOT EXISTS memory_version_delete BEFORE DELETE ON memories BEGIN
        INSERT INTO memory_versions(memory_id,action,snapshot) VALUES(OLD.id,'deleted',{snapshot('OLD.')}); END''')
    for operation in ('UPDATE','DELETE'):
        db.execute(f'''CREATE TRIGGER IF NOT EXISTS memory_versions_no_{operation.lower()}
            BEFORE {operation} ON memory_versions BEGIN
            SELECT RAISE(ABORT,'Memory version history is append-only'); END''')
