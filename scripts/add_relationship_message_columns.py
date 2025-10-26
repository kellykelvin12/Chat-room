import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'gossip.db')

def column_exists(conn, table, column):
    cur = conn.execute(f"PRAGMA table_info({table})")
    cols = [row[1] for row in cur.fetchall()]
    return column in cols

def add_column(conn, table, column_def):
    print(f"Adding column: {column_def}")
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column_def}")
    conn.commit()

def main():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)

    try:
        # image_path
        if not column_exists(conn, 'relationship_message', 'image_path'):
            add_column(conn, 'relationship_message', "image_path TEXT")
        else:
            print('image_path already exists')

        # voice_path
        if not column_exists(conn, 'relationship_message', 'voice_path'):
            add_column(conn, 'relationship_message', "voice_path TEXT")
        else:
            print('voice_path already exists')

        # identity_revealed (store as INTEGER 0/1)
        if not column_exists(conn, 'relationship_message', 'identity_revealed'):
            add_column(conn, 'relationship_message', "identity_revealed INTEGER DEFAULT 0")
        else:
            print('identity_revealed already exists')

        # voice_type
        if not column_exists(conn, 'relationship_message', 'voice_type'):
            add_column(conn, 'relationship_message', "voice_type TEXT DEFAULT 'normal'")
        else:
            print('voice_type already exists')

        print('Migration completed')

    except Exception as e:
        print('Migration failed:', e)
    finally:
        conn.close()

if __name__ == '__main__':
    main()
