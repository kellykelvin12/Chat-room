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
        if not column_exists(conn, 'user', 'is_admin'):
            add_column(conn, 'user', "is_admin INTEGER DEFAULT 0")
        else:
            print('is_admin already exists')
        print('Migration completed')
    except Exception as e:
        print('Migration failed:', e)
    finally:
        conn.close()

if __name__ == '__main__':
    main()