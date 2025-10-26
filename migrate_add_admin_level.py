import sqlite3

# Try both possible DBs
for DB_PATH in ['instance/app.db', 'instance/gossip.db']:
    print(f"Checking {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("ALTER TABLE user ADD COLUMN admin_level INTEGER DEFAULT 0")
        print(f"Added 'admin_level' column to user table in {DB_PATH}.")
    except sqlite3.OperationalError as e:
        if 'no such table' in str(e):
            print(f"No user table in {DB_PATH}.")
        elif 'duplicate column name' in str(e):
            print(f"Column 'admin_level' already exists in {DB_PATH}.")
        else:
            print(f"Error in {DB_PATH}: {e}")
    conn.commit()
    conn.close()
