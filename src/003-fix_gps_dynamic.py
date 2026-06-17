"""
Dynamic GPS Fix for ProjectImages Table
========================================
Fully dynamic — reads site reference coordinates directly from CountrySitesAll,
detects swapped/bad rows at runtime (no hardcoded IDs), and applies:

  Step 1 — Swap rows where Longitude and Latitude are confirmed reversed
            (stored value fits the opposite column's expected range).
  Step 2 — Swap any remaining rows where Longitude < Latitude (universal rule).
  Step 3 — NULL out rows whose coordinates are genuinely out of range for their
            site and cannot be fixed by swapping.
  Step 4 — Fill remaining NULL GPS rows using CountrySitesAll default coordinates.
  Step 5 — Fill NULL GPS for sites not in CountrySitesAll using coords observed
            in existing rows for the same SiteName.
"""

import pyodbc
import sys
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

# Database connection from environment (must be set in .env file)
SERVER   = os.getenv('DB_SERVER')
DATABASE = os.getenv('DB_DATABASE')
USERNAME = os.getenv('DB_USERNAME')
PASSWORD = os.getenv('DB_PASSWORD')

TOLERANCE = 1.5   # degrees of tolerance around each site's reference coordinate

def get_connection():
    conn_str = (
        f'DRIVER={{ODBC Driver 17 for SQL Server}};SERVER={SERVER};DATABASE={DATABASE};'
        f'UID={USERNAME};PWD={PASSWORD};TrustServerCertificate=yes'
    )
    conn = pyodbc.connect(conn_str, timeout=30)
    conn.autocommit = False
    return conn

def section(title):
    print(f"\n{'='*70}")
    print(f"  {title}")
    print(f"{'='*70}")

# ──────────────────────────────────────────────────────────────────────────────
# STEP 1: Load reference ranges from CountrySitesAll
# ──────────────────────────────────────────────────────────────────────────────
def load_site_ranges(cursor):
    cursor.execute("""
        SELECT SiteId, SiteName, CountryId, Longitude, Latitude
        FROM   CountrySitesAll
        WHERE  Longitude IS NOT NULL AND Latitude IS NOT NULL
        ORDER  BY SiteId
    """)
    sites = {}
    for r in cursor.fetchall():
        lon = float(r.Longitude)
        lat = float(r.Latitude)
        sites[r.SiteId] = {
            'name':       r.SiteName,
            'country_id': r.CountryId,
            'lon':        lon,
            'lat':        lat,
            'lon_min':    lon - TOLERANCE,
            'lon_max':    lon + TOLERANCE,
            'lat_min':    lat - TOLERANCE,
            'lat_max':    lat + TOLERANCE,
        }
    return sites

# ──────────────────────────────────────────────────────────────────────────────
# STEP 2: Classify each GPS row
# ──────────────────────────────────────────────────────────────────────────────
def classify(site_ranges, site_id, lon_val, lat_val):
    if site_id not in site_ranges:
        return 'no_ref'
    r = site_ranges[site_id]
    try:
        lon = float(lon_val)
        lat = float(lat_val)
    except (TypeError, ValueError):
        return 'non_numeric'

    lon_ok     = r['lon_min'] <= lon <= r['lon_max']
    lat_ok     = r['lat_min'] <= lat <= r['lat_max']
    lon_as_lat = r['lat_min'] <= lon <= r['lat_max']
    lat_as_lon = r['lon_min'] <= lat <= r['lon_max']

    if lon_ok and lat_ok:
        return 'ok'
    if lon_as_lat and lat_as_lon:
        return 'swapped'
    return 'bad'

# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────
def main():
    print("=" * 70)
    print(f"  DYNAMIC GPS FIX — {DATABASE}")
    print("=" * 70)

    conn = get_connection()
    cursor = conn.cursor()
    print("Connected.\n")

    # ── Load site references ──────────────────────────────────────────────────
    site_ranges = load_site_ranges(cursor)
    print("Reference coords from CountrySitesAll:")
    print(f"  {'SiteId':>6}  {'SiteName':<14}  {'Lon':>12}  {'Lat':>10}  Range ±{TOLERANCE}°")
    print(f"  {'-'*60}")
    for sid, r in sorted(site_ranges.items()):
        print(f"  {sid:>6}  {str(r['name']):<14}  {r['lon']:>12.6f}  {r['lat']:>10.6f}")

    # ── Fetch all rows with GPS data ──────────────────────────────────────────
    cursor.execute("""
        SELECT Id, SiteId, SiteName, CountryId, Longitude, latitude
        FROM   ProjectImages
        WHERE  Longitude IS NOT NULL AND latitude IS NOT NULL
    """)
    gps_rows = cursor.fetchall()
    print(f"\nRows with GPS data: {len(gps_rows)}")

    # ── Classify ──────────────────────────────────────────────────────────────
    swapped_ids = []
    bad_ids     = []
    ok_count    = 0
    no_ref      = []

    for row in gps_rows:
        status = classify(site_ranges, row.SiteId, row.Longitude, row.latitude)
        if status == 'ok':
            ok_count += 1
        elif status == 'swapped':
            swapped_ids.append(row.Id)
        elif status == 'bad':
            bad_ids.append(row.Id)
        else:
            no_ref.append(row)

    print(f"  Correct       : {ok_count}")
    print(f"  Swapped       : {len(swapped_ids)}")
    print(f"  Bad/out-range : {len(bad_ids)}")
    print(f"  No site ref   : {len(no_ref)}")

    # ═══════════════════════════════════════════════════════════════════════════
    # STEP A — Swap confirmed swapped rows
    # ═══════════════════════════════════════════════════════════════════════════
    section("STEP A — Swap confirmed swapped rows")
    if swapped_ids:
        placeholders = ','.join('?' * len(swapped_ids))
        cursor.execute(f"""
            UPDATE ProjectImages
            SET    Longitude = latitude,
                   latitude  = Longitude
            WHERE  Id IN ({placeholders})
        """, swapped_ids)
        print(f"  Swapped {cursor.rowcount} rows.")
    else:
        print("  Nothing to swap.")

    # ═══════════════════════════════════════════════════════════════════════════
    # STEP B — Swap any rows still where Longitude < Latitude
    # ═══════════════════════════════════════════════════════════════════════════
    section("STEP B — Swap remaining rows where Longitude < Latitude")
    cursor.execute("""
        SELECT Id FROM ProjectImages
        WHERE  Longitude IS NOT NULL AND latitude IS NOT NULL
          AND  TRY_CAST(Longitude AS float) < TRY_CAST(latitude AS float)
    """)
    lon_lt_lat = [r.Id for r in cursor.fetchall()]
    if lon_lt_lat:
        placeholders = ','.join('?' * len(lon_lt_lat))
        cursor.execute(f"""
            UPDATE ProjectImages
            SET    Longitude = latitude,
                   latitude  = Longitude
            WHERE  Id IN ({placeholders})
        """, lon_lt_lat)
        print(f"  Swapped {cursor.rowcount} additional rows (Lon < Lat rule).")
    else:
        print("  No rows with Longitude < Latitude — clean.")

    # ═══════════════════════════════════════════════════════════════════════════
    # STEP C — Re-classify bad rows; re-check if swap after step A fixed them
    #          Any still-bad rows get nulled
    # ═══════════════════════════════════════════════════════════════════════════
    section("STEP C — NULL out genuinely bad GPS rows")
    if bad_ids:
        # Re-fetch to check if any were fixed by the swaps above
        placeholders = ','.join('?' * len(bad_ids))
        cursor.execute(
            f"SELECT Id, SiteId, Longitude, latitude FROM ProjectImages WHERE Id IN ({placeholders})",
            bad_ids
        )
        still_bad = []
        for row in cursor.fetchall():
            status = classify(site_ranges, row.SiteId, row.Longitude, row.latitude)
            if status not in ('ok',):
                still_bad.append(row.Id)

        if still_bad:
            placeholders2 = ','.join('?' * len(still_bad))
            cursor.execute(
                f"UPDATE ProjectImages SET Longitude = NULL, latitude = NULL "
                f"WHERE Id IN ({placeholders2})",
                still_bad
            )
            print(f"  Nulled {cursor.rowcount} genuinely bad GPS rows: {still_bad}")
        else:
            print("  All previously bad rows were corrected by the swap — nothing to null.")
    else:
        print("  No bad rows identified.")

    # ═══════════════════════════════════════════════════════════════════════════
    # STEP D — Fill NULL GPS using CountrySitesAll defaults
    # ═══════════════════════════════════════════════════════════════════════════
    section("STEP D — Fill NULL GPS from CountrySitesAll defaults")
    cursor.execute("""
        SELECT SiteId, SiteName, Longitude, Latitude
        FROM   CountrySitesAll
        WHERE  Longitude IS NOT NULL AND Latitude IS NOT NULL
    """)
    refs = cursor.fetchall()

    total_filled_d = 0
    for ref in refs:
        cursor.execute("""
            UPDATE ProjectImages
            SET    Longitude = ?,
                   latitude  = ?
            WHERE  SiteId = ?
              AND  (Longitude IS NULL OR latitude IS NULL)
        """, (str(ref.Longitude), str(ref.Latitude), ref.SiteId))
        if cursor.rowcount:
            print(f"  SiteId {ref.SiteId} ({ref.SiteName}): filled {cursor.rowcount} row(s) "
                  f"with Lon={ref.Longitude}, Lat={ref.Latitude}")
            total_filled_d += cursor.rowcount

    if total_filled_d == 0:
        print("  No NULL GPS rows matched CountrySitesAll sites.")
    else:
        print(f"  Total filled: {total_filled_d}")

    # ═══════════════════════════════════════════════════════════════════════════
    # STEP E — Fill NULL GPS for sites not in CountrySitesAll
    #          Use median coords from existing non-null rows for same SiteName
    # ═══════════════════════════════════════════════════════════════════════════
    section("STEP E — Fill NULL GPS for unknown sites using observed coords")

    # Find SiteNames that still have NULLs
    cursor.execute("""
        SELECT DISTINCT SiteName
        FROM   ProjectImages
        WHERE  (Longitude IS NULL OR latitude IS NULL)
          AND  SiteName IS NOT NULL
    """)
    null_site_names = [r.SiteName for r in cursor.fetchall()]

    total_filled_e = 0
    for sname in null_site_names:
        # Get median-ish coords from existing non-null rows for this SiteName
        cursor.execute("""
            SELECT TOP 1
                   AVG(TRY_CAST(Longitude AS float)) OVER () as AvgLon,
                   AVG(TRY_CAST(latitude  AS float)) OVER () as AvgLat
            FROM   ProjectImages
            WHERE  SiteName   = ?
              AND  Longitude IS NOT NULL
              AND  latitude  IS NOT NULL
              AND  TRY_CAST(Longitude AS float) > TRY_CAST(latitude AS float)
        """, sname)
        row = cursor.fetchone()
        if row and row.AvgLon is not None:
            avg_lon = round(row.AvgLon, 7)
            avg_lat = round(row.AvgLat, 7)
            cursor.execute("""
                UPDATE ProjectImages
                SET    Longitude = ?,
                       latitude  = ?
                WHERE  SiteName = ?
                  AND  (Longitude IS NULL OR latitude IS NULL)
            """, (str(avg_lon), str(avg_lat), sname))
            print(f"  '{sname}': filled {cursor.rowcount} row(s) with "
                  f"averaged Lon={avg_lon}, Lat={avg_lat}")
            total_filled_e += cursor.rowcount
        else:
            print(f"  '{sname}': no existing coords to derive from — still NULL")

    if total_filled_e == 0 and not null_site_names:
        print("  No unknown-site NULL rows found.")

    # ═══════════════════════════════════════════════════════════════════════════
    # FINAL VERIFICATION
    # ═══════════════════════════════════════════════════════════════════════════
    section("FINAL VERIFICATION")

    cursor.execute("""
        SELECT COUNT(*) FROM ProjectImages
        WHERE TRY_CAST(Longitude AS float) < TRY_CAST(latitude AS float)
    """)
    lon_lt_lat_final = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM ProjectImages WHERE Longitude IS NULL OR latitude IS NULL")
    null_final = cursor.fetchone()[0]

    cursor.execute("""
        SELECT SiteId, SiteName, COUNT(*) as Rows,
               MIN(TRY_CAST(Longitude AS float)) as MinLon,
               MAX(TRY_CAST(Longitude AS float)) as MaxLon,
               MIN(TRY_CAST(latitude  AS float)) as MinLat,
               MAX(TRY_CAST(latitude  AS float)) as MaxLat
        FROM   ProjectImages
        WHERE  Longitude IS NOT NULL AND latitude IS NOT NULL
        GROUP  BY SiteId, SiteName
        ORDER  BY SiteId
    """)
    site_summary = cursor.fetchall()

    print(f"  Rows with Longitude < Latitude : {lon_lt_lat_final}  {'OK' if lon_lt_lat_final == 0 else 'ISSUES REMAIN'}")
    print(f"  Rows with NULL GPS             : {null_final}  {'OK' if null_final == 0 else 'SOME STILL NULL'}")
    print()
    fmt = lambda v: f"{v:>10.4f}" if v is not None else f"{'NULL':>10}"
    sid_fmt = lambda v: str(v) if v is not None else 'NULL'
    print(f"  {'SiteId':>6}  {'SiteName':<14}  {'Rows':>5}  {'MinLon':>10}  {'MaxLon':>10}  {'MinLat':>10}  {'MaxLat':>10}")
    print(f"  {'-'*72}")
    for r in site_summary:
        print(f"  {sid_fmt(r.SiteId):>6}  {str(r.SiteName) if r.SiteName else 'NULL':<14}  "
              f"{r.Rows:>5}  {fmt(r.MinLon)}  {fmt(r.MaxLon)}  {fmt(r.MinLat)}  {fmt(r.MaxLat)}")

    conn.commit()
    print(f"\n  COMMITTED all changes.")
    conn.close()
    print("=" * 70)

if __name__ == "__main__":
    main()
