import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()

conn = psycopg2.connect(
    host=os.environ.get("AUTH_DB_HOST", "localhost"),
    port=os.environ.get("AUTH_DB_PORT", "8124"),
    dbname=os.environ.get("AUTH_DB_NAME", "postgres"),
    user=os.environ.get("AUTH_DB_USER", "postgres"),
    password=os.environ.get("AUTH_DB_PASS", "postgres")
)
conn.autocommit = True
cur = conn.cursor()

# Reset admin password to 'password123'
cur.execute(
    "UPDATE users SET password_hash = crypt(%s, gen_salt('bf')) WHERE username = %s",
    ("password123", "admin@domain.com")
)
print(f"Updated {cur.rowcount} row(s) for admin@domain.com")

cur.close()
conn.close()
print("Password reset to: password123")
