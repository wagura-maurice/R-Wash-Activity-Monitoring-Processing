"""
Add Qansaxley and Kabasa to CountrySitesAll table.
Coordinates from previous OSM lookup and existing DB data.
"""
import pyodbc
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

# Database connection from environment (must be set in .env file)
SERVER = os.getenv('DB_SERVER')
DATABASE = os.getenv('DB_DATABASE')
USERNAME = os.getenv('DB_USERNAME')
PASSWORD = os.getenv('DB_PASSWORD')

conn_str = (
    f'DRIVER={{ODBC Driver 17 for SQL Server}};'
    f'SERVER={SERVER};'
    f'DATABASE={DATABASE};'
    f'UID={USERNAME};'
    f'PWD={PASSWORD};'
    f'TrustServerCertificate=yes'
)

# Site data to add
new_sites = [
    {
        'site_name': 'Qansaxley',
        'country_id': 3,  # Somalia
        'longitude': 45.0089000,
        'latitude': 2.5854774
    },
    {
        'site_name': 'Kabasa',
        'country_id': 3,  # Somalia
        'longitude': 42.0933313,
        'latitude': 4.167342
    }
]

print('=' * 60)
print('ADDING MISSING SITES TO CountrySitesAll')
print('=' * 60)

conn = pyodbc.connect(conn_str)
cursor = conn.cursor()

# Check existing sites first
print('\n[1] Checking existing sites...')
cursor.execute("SELECT SiteId, SiteName, CountryId FROM CountrySitesAll WHERE SiteName IN ('Qansaxley', 'Kabasa')")
existing = cursor.fetchall()
if existing:
    print(f'   Found existing sites:')
    for row in existing:
        print(f'     SiteId {row.SiteId}: {row.SiteName} (CountryId={row.CountryId})')
else:
    print('   No existing Qansaxley or Kabasa found')

# Insert new sites
print('\n[2] Inserting new sites...')
inserted = []
for site in new_sites:
    # Check if already exists for this country
    cursor.execute("SELECT COUNT(*) FROM CountrySitesAll WHERE SiteName=? AND CountryId=?",
                   (site['site_name'], site['country_id']))
    if cursor.fetchone()[0] > 0:
        print(f'   ⚠ {site["site_name"]} already exists for CountryId={site["country_id"]}')
        continue
    
    cursor.execute("""
        INSERT INTO CountrySitesAll (SiteName, CountryId, Longitude, Latitude)
        VALUES (?, ?, ?, ?)
    """, (site['site_name'], site['country_id'], site['longitude'], site['latitude']))
    
    # Get the new SiteId
    cursor.execute("SELECT @@IDENTITY")
    new_id = cursor.fetchone()[0]
    inserted.append((new_id, site['site_name']))
    print(f'   ✓ Inserted {site["site_name"]}: SiteId={new_id}, Lon={site["longitude"]}, Lat={site["latitude"]}')

conn.commit()

# Verify
print('\n[3] Verification...')
cursor.execute("SELECT SiteId, SiteName, CountryId, Longitude, Latitude FROM CountrySitesAll WHERE SiteName IN ('Qansaxley', 'Kabasa')")
for row in cursor.fetchall():
    print(f'   SiteId {row.SiteId}: {row.SiteName} (Country={row.CountryId}, Lon={row.Longitude}, Lat={row.Latitude})')

cursor.close()
conn.close()

print('\n' + '=' * 60)
if inserted:
    print(f'Successfully added {len(inserted)} sites.')
    print('You can now regenerate the Somalia JSON or proceed with insertion.')
else:
    print('No new sites added (may already exist).')
print('=' * 60)
