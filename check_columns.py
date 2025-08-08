import psycopg2

conn = psycopg2.connect(
    host="devqa-tigerglobal.cluster-cglo4fl4jwye.us-east-1.rds.amazonaws.com",
    port=5432,
    dbname="dev_tigerglobal",
    user="dev_tigerglobal_portal_rw",
    password="ghidrC=^EX*?1OAq"
)

cur = conn.cursor()
cur.execute("""
    SELECT column_name
    FROM information_schema.columns
    WHERE table_schema = 'portal'
      AND table_name = 'chatmessage';
""")
columns = cur.fetchall()
print("Columns in portal.chatmessage:")
for col in columns:
    print("-", col[0])

cur.close()
conn.close()
