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

cursor.execute("""
    SELECT c.CountryName, COUNT(*) AS NullShowDataCount
    FROM ProjectImages pi
    LEFT JOIN CountriesAll c ON pi.CountryId = c.CountryId
    WHERE pi.ShowData IS NULL
    GROUP BY c.CountryName
    ORDER BY NullShowDataCount DESC
""")
print("NULL ShowData rows by country:")
for row in cursor.fetchall():
    country = row.CountryName if row.CountryName else 'NULL/Unknown'
    print(f"  {country}: {row.NullShowDataCount}")

cursor.close()
conn.close()
