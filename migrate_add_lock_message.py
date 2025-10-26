import sqlite3

def add_lock_message_column(db_path, table):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    try:
        c.execute(f"ALTER TABLE {table} ADD COLUMN lock_message TEXT;")
        print(f"Added lock_message to {table} in {db_path}")
    except Exception as e:
        print(f"Could not add lock_message to {table} in {db_path}: {e}")
    conn.commit()
    conn.close()

if __name__ == "__main__":
    dbs = ["instance/gossip.db", "instance/app.db"]
    tables = ["topic", "relationship", "private_chat"]
    for db in dbs:
        for table in tables:
            add_lock_message_column(db, table)
