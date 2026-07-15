import pyodbc

conn_str = (
    'DRIVER={ODBC Driver 17 for SQL Server};'
    'SERVER=localhost,1433;'
    'DATABASE=WashMay2026;'
    'UID=sa;'
    'PWD=Qwerty123!;'
    'TrustServerCertificate=yes'
)

conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

print("Updating ShowData for existing instances in ProjectImages...\n")

cursor.execute("""
    SELECT Id, ActivityId
    FROM ProjectImages
    WHERE ActivityId IS NOT NULL
    ORDER BY ActivityId, Id
""")
rows = cursor.fetchall()
print(f"Total rows with ActivityId: {len(rows)}")

instance_seen = {}
updated_to_0 = 0
updated_to_1 = 0

for row in rows:
    idx = instance_seen.get(row.ActivityId, 0)
    showdata = 0 if idx == 0 else 1
    cursor.execute(
        "UPDATE ProjectImages SET ShowData = ? WHERE Id = ?",
        (showdata, row.Id)
    )
    if showdata == 0:
        updated_to_0 += 1
    else:
        updated_to_1 += 1
    instance_seen[row.ActivityId] = idx + 1

conn.commit()

print(f"\nUpdate complete:")
print(f"  ShowData = 0 (visible, first per instance):  {updated_to_0}")
print(f"  ShowData = 1 (hidden, repeating rows):       {updated_to_1}")
print(f"  Total rows updated:                          {updated_to_0 + updated_to_1}")

cursor.close()
conn.close()
