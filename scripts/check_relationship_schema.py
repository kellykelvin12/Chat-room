import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'gossip.db')

def main():
    if not os.path.exists(DB_PATH):
        print('Database not found at', DB_PATH)
        return

    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.execute('PRAGMA table_info(relationship_message)')
        cols = cur.fetchall()
        print('Columns in relationship_message:')
        for c in cols:
            print(c)

        # Attempt the SELECT used by the app (use example relationship id from the error)
        rel_id = 'e74953ce-665e-4560-a739-422bad037e1d'
        print('\nRunning SELECT for relationship_id =', rel_id)
        cur2 = conn.execute('''
            SELECT id, image_path, voice_path, identity_revealed, voice_type
            FROM relationship_message
            WHERE relationship_id = ?
            ORDER BY created_at
        ''', (rel_id,))
        rows = cur2.fetchall()
        print('SELECT returned', len(rows), 'rows')
    except Exception as e:
        print('Error during check:', e)
    finally:
        conn.close()

if __name__ == '__main__':
    main()
