import sqlite3
import json

DB_CANDIDATES = ['instance/app.db', 'instance/gossip.db']

# Columns to add: (table, column, sql)
COLUMNS = [
    ('topic', "is_locked INTEGER DEFAULT 0"),
    ('topic', "lock_password TEXT"),
    ('topic', "allowed_user_ids TEXT"),
    ('relationship', "is_locked INTEGER DEFAULT 0"),
    ('relationship', "lock_password TEXT"),
    ('relationship', "allowed_user_ids TEXT"),
    ('private_chat', "is_locked INTEGER DEFAULT 0"),
    ('private_chat', "lock_password TEXT"),
    ('private_chat', "allowed_user_ids TEXT"),
]


def add_columns_to_db(db_path):
    print(f"Checking {db_path}")
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    for table, col_sql in COLUMNS:
        col_name = col_sql.split()[0]
        try:
            # try to insert a dummy select to see if column exists
            c.execute(f"SELECT {col_name} FROM {table} LIMIT 1")
            print(f"Column {col_name} already exists on table {table} in {db_path}")
        except sqlite3.OperationalError as e:
            msg = str(e).lower()
            if 'no such column' in msg or 'no such table' in msg:
                try:
                    print(f"Adding column {col_sql} to {table} in {db_path}")
                    c.execute(f"ALTER TABLE {table} ADD COLUMN {col_sql}")
                    conn.commit()
                except sqlite3.OperationalError as e2:
                    print(f"Failed to add column {col_sql} to {table} in {db_path}: {e2}")
            else:
                print(f"Unexpected error selecting {col_name} from {table} in {db_path}: {e}")
    conn.close()


if __name__ == '__main__':
    for db in DB_CANDIDATES:
        add_columns_to_db(db)
