import sqlite3
import os

db_path = os.path.join(os.getcwd(), 'test.db')
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Create test user table with DEFAULT '' for potentially NULL fields
cur.execute('''CREATE TABLE IF NOT EXISTS "user" (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    username TEXT NOT NULL,
    email TEXT NOT NULL,
    email_password TEXT NOT NULL DEFAULT '',
    instagram_username TEXT NOT NULL DEFAULT '',
    instagram_password TEXT NOT NULL DEFAULT '',
    phone_number TEXT NOT NULL DEFAULT '',
    stream TEXT NOT NULL DEFAULT ''
)''')

# Create trigger
cur.execute('''CREATE TRIGGER IF NOT EXISTS user_fill_nulls_after_insert 
AFTER INSERT ON "user"
BEGIN
  UPDATE "user" SET stream = COALESCE(NEW.stream,'') WHERE id = NEW.id;
  UPDATE "user" SET email_password = COALESCE(NEW.email_password,'') WHERE id = NEW.id;
  UPDATE "user" SET instagram_username = COALESCE(NEW.instagram_username,'') WHERE id = NEW.id;
  UPDATE "user" SET instagram_password = COALESCE(NEW.instagram_password,'') WHERE id = NEW.id;
  UPDATE "user" SET phone_number = COALESCE(NEW.phone_number,'') WHERE id = NEW.id;
END;''')

# Test insert
cur.execute('''INSERT INTO "user" (id, name, username, email) 
VALUES ('test1', 'Test User', 'testuser', 'test@test.com')''')

# Verify trigger worked
cur.execute('SELECT * FROM "user" WHERE id = ?', ('test1',))
row = cur.fetchone()
print("Test insert result:", row)

conn.commit()
print("Table and trigger created successfully")
conn.close()