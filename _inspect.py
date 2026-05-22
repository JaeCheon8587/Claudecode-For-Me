import sqlite3
db = sqlite3.connect("samples/.codenav/index.sqlite")
db.row_factory = sqlite3.Row

total = db.execute("SELECT COUNT(*) FROM classes").fetchone()[0]
empty = db.execute("SELECT COUNT(*) FROM classes WHERE description=''").fetchone()[0]
stale = db.execute("SELECT COUNT(*) FROM classes WHERE stale=1").fetchone()[0]
print(f"total={total} filled={total-empty} empty={empty} stale={stale}")

print("\n=== filled descriptions ===")
for r in db.execute("SELECT class_name, description, tags_json FROM classes WHERE description != '' ORDER BY class_name").fetchall():
    print(f"  {r['class_name']}: {r['description']}")
    print(f"    tags: {r['tags_json']}")
