"""
Generate an array of dictionaries from consolidated Excel data,
mapped to ProjectImages database table structure with Country and Site lookups.
"""

import argparse
import pandas as pd
import pyodbc
import os
import glob
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

# Database connection parameters from environment (must be set in .env file)
SERVER = os.getenv('DB_SERVER')
DATABASE = os.getenv('DB_DATABASE')
USERNAME = os.getenv('DB_USERNAME')
PASSWORD = os.getenv('DB_PASSWORD')

def get_db_connection():
    """Get database connection."""
    conn_str = (
        f'DRIVER={{ODBC Driver 17 for SQL Server}};'
        f'SERVER={SERVER};'
        f'DATABASE={DATABASE};'
        f'UID={USERNAME};'
        f'PWD={PASSWORD};'
        f'TrustServerCertificate=yes'
    )
    return pyodbc.connect(conn_str)

def get_country_mapping():
    """Get CountryId mapping from CountriesAll table."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT CountryId, CountryName FROM CountriesAll")
    mapping = {row.CountryName: row.CountryId for row in cursor.fetchall()}
    cursor.close()
    conn.close()
    return mapping

def get_site_mapping():
    """Get SiteId mapping from CountrySitesAll table using (SiteName, CountryId)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT SiteId, SiteName, CountryId FROM CountrySitesAll")
    # Key is (SiteName, CountryId) -> SiteId
    mapping = {}
    for row in cursor.fetchall():
        key = (row.SiteName, row.CountryId)
        mapping[key] = row.SiteId
    cursor.close()
    conn.close()
    return mapping

def get_site_name_to_id_mapping():
    """Get SiteId mapping from CountrySitesAll keyed by SiteName (for GPS fallback)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT SiteId, SiteName FROM CountrySitesAll")
    mapping = {}
    for row in cursor.fetchall():
        mapping[row.SiteName] = row.SiteId
    cursor.close()
    conn.close()
    return mapping

def get_site_gps_ranges(tolerance=1.5):
    """Load GPS reference ranges from CountrySitesAll keyed by SiteId."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT SiteId, SiteName, Longitude, Latitude
        FROM   CountrySitesAll
        WHERE  Longitude IS NOT NULL AND Latitude IS NOT NULL
    """)
    ranges = {}
    for row in cursor.fetchall():
        lon = float(row.Longitude)
        lat = float(row.Latitude)
        ranges[row.SiteId] = {
            'name':    row.SiteName,
            'lon':     lon,
            'lat':     lat,
            'lon_min': lon - tolerance,
            'lon_max': lon + tolerance,
            'lat_min': lat - tolerance,
            'lat_max': lat + tolerance,
        }
    cursor.close()
    conn.close()
    return ranges

def validate_and_fix_gps(site_id, site_name, lon_val, lat_val, site_ranges, site_name_to_id):
    """
    Validate a (Longitude, Latitude) pair against the known site ranges.
    Returns (fixed_lon, fixed_lat, action) where action is one of:
      'ok'       - coordinates are correct, returned as-is
      'swapped'  - values were reversed, returned after swapping
      'bad'      - out of range even after swap, returned as (None, None)
      'no_ref'   - SiteId not in reference table, returned as-is
      'null'     - one or both values missing, no fallback available
      'fallback' - used CountrySitesAll reference coordinates
    """
    # If GPS is NULL but we have site reference, use fallback coordinates
    if lon_val is None or lat_val is None:
        # Try to find site by ID first, then by name
        ref_site_id = site_id
        if ref_site_id is None and site_name in site_name_to_id:
            ref_site_id = site_name_to_id[site_name]
        
        if ref_site_id in site_ranges:
            # Use reference coordinates from CountrySitesAll
            r = site_ranges[ref_site_id]
            return str(r['lon']), str(r['lat']), 'fallback'
        
        return None, None, 'null'

    try:
        lon = float(lon_val)
        lat = float(lat_val)
    except (TypeError, ValueError):
        return None, None, 'bad'

    # Universal rule: longitude must always be the larger number for these sites
    # If swapped by this rule, try range validation on the swapped values first
    if site_id not in site_ranges:
        # No reference — apply Lon > Lat rule only
        if lon < lat:
            return str(lat), str(lon), 'swapped'
        return str(lon_val), str(lat_val), 'no_ref'

    r = site_ranges[site_id]

    lon_ok     = r['lon_min'] <= lon <= r['lon_max']
    lat_ok     = r['lat_min'] <= lat <= r['lat_max']
    lon_as_lat = r['lat_min'] <= lon <= r['lat_max']
    lat_as_lon = r['lon_min'] <= lat <= r['lon_max']

    if lon_ok and lat_ok:
        return str(lon_val), str(lat_val), 'ok'

    if lon_as_lat and lat_as_lon:
        return str(lat_val), str(lon_val), 'swapped'

    # Neither orientation fits — try fallback to site reference
    if site_id in site_ranges:
        r = site_ranges[site_id]
        return str(r['lon']), str(r['lat']), 'fallback_bad'
    if site_name in site_name_to_id:
        ref_site_id = site_name_to_id[site_name]
        if ref_site_id in site_ranges:
            r = site_ranges[ref_site_id]
            return str(r['lon']), str(r['lat']), 'fallback_bad'
    return None, None, 'bad'

def load_consolidated_data(file_path=None):
    """
    Load consolidated Excel file.
    If file_path is provided, load that specific file.
    Otherwise, load the most recent file from data/consolidated/.
    """
    if file_path:
        # Use provided file path
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Specified file not found: {file_path}")
        print(f"Loading specified file: {os.path.basename(file_path)}\n")
        return pd.read_excel(file_path)
    
    # Find most recent consolidated file
    pattern = os.path.join(r"d:\MethLab\ActivityMonitoring\data\consolidated", "consolidated_data_*.xlsx")
    files = glob.glob(pattern)
    
    if not files:
        raise FileNotFoundError("No consolidated Excel file found in data/consolidated/!")
    
    latest_file = max(files, key=os.path.getmtime)
    print(f"Loading latest file: {os.path.basename(latest_file)}\n")
    
    return pd.read_excel(latest_file)

def map_excel_to_db(df, country_mapping, site_mapping, site_ranges, site_name_to_id):
    """
    Map consolidated Excel data to ProjectImages database structure.
    Performs lookups:
    1. CountryName -> CountryId from CountriesAll
    2. (SiteName, CountryId) -> SiteId from CountrySitesAll
    3. GPS validation: detects and corrects swapped Longitude/Latitude, uses fallback from CountrySitesAll

    Returns a list of dictionaries with database column names as keys.
    SiteId is positioned immediately before ImageDescription.
    """
    mapped_data = []
    unmatched_countries = set()
    unmatched_sites = set()
    gps_actions = {'ok': 0, 'swapped': 0, 'bad': 0, 'null': 0, 'no_ref': 0, 'fallback': 0, 'fallback_bad': 0}
    
    for idx, row in df.iterrows():
        # Get raw values from Excel
        country_name = row.get('Country Name', None)
        site_name = row.get('Site Name', None)
        
        # Step 1: Lookup CountryId from CountryName
        country_id = None
        if pd.notna(country_name):
            country_id = country_mapping.get(country_name)
            if country_id is None:
                unmatched_countries.add(country_name)
        
        # Step 2: Lookup SiteId from (SiteName, CountryId)
        site_id = None
        if pd.notna(site_name) and country_id is not None:
            site_key = (site_name, country_id)
            site_id = site_mapping.get(site_key)
            if site_id is None:
                unmatched_sites.add((site_name, country_name, country_id))
        
        # Build the mapped row dictionary
        # IMPORTANT: SiteId is positioned immediately before ImageDescription
        mapped_row = {}
        
        # Id - Set to the instance ID from the Excel data
        instance_id = row.get('_instance_id', None)
        mapped_row['Id'] = instance_id
        
        # SiteId - Positioned BEFORE ImageDescription (as requested)
        mapped_row['SiteId'] = site_id
        
        # ImageDescription
        mapped_row['ImageDescription'] = row.get('Image Description', None)
        if pd.isna(mapped_row['ImageDescription']):
            mapped_row['ImageDescription'] = None
        
        # ImagePath - Transform URLs from odiousodds.xyz to rwash.net
        image_path = row.get('Image Path', None)
        if pd.isna(image_path):
            mapped_row['ImagePath'] = None
        else:
            # Extract just the filename and create new URL
            if isinstance(image_path, str) and '/' in image_path:
                filename = image_path.split('/')[-1].split('?')[0]
                mapped_row['ImagePath'] = f"https://rwash.net/{filename}"
            else:
                mapped_row['ImagePath'] = image_path
        
        # Imagedate - Parse datetime
        image_date = row.get('Image Date', None)
        if pd.notna(image_date):
            if isinstance(image_date, str):
                try:
                    mapped_row['Imagedate'] = pd.to_datetime(image_date)
                except:
                    mapped_row['Imagedate'] = None
            else:
                mapped_row['Imagedate'] = image_date
        else:
            mapped_row['Imagedate'] = None
        
        # Longitude / latitude — validate and fix swapped/bad coordinates
        longitude = row.get('Longitude', None)
        latitude  = row.get('Latitude', None)
        lon_raw = longitude if pd.notna(longitude) else None
        lat_raw = latitude  if pd.notna(latitude)  else None

        fixed_lon, fixed_lat, gps_action = validate_and_fix_gps(
            site_id, site_name, lon_raw, lat_raw, site_ranges, site_name_to_id
        )
        mapped_row['Longitude'] = fixed_lon
        mapped_row['latitude']  = fixed_lat
        gps_actions[gps_action] = gps_actions.get(gps_action, 0) + 1
        
        # SKIP records with NULL SiteId - they cannot be inserted
        if site_id is None:
            continue  # Skip this record entirely
        
        # ActivityStatus - Check both possible column names
        activity_status = None
        if 'Activity Status' in row and pd.notna(row['Activity Status']):
            activity_status = row['Activity Status']
        elif 'Status' in row and pd.notna(row['Status']):
            activity_status = row['Status']
        mapped_row['ActivityStatus'] = activity_status
        
        # Comments
        comments = row.get('Comments', None)
        if pd.isna(comments):
            comments = None
        mapped_row['Comments'] = comments
        
        # ProjectDescription
        mapped_row['ProjectDescription'] = row.get('Project Description', None)
        if pd.isna(mapped_row['ProjectDescription']):
            mapped_row['ProjectDescription'] = None
        
        # CompletionPercentage - Convert from percentage (65.0) to decimal (0.65)
        completion = row.get('Completion Percentage', None)
        if pd.notna(completion):
            try:
                # Divide by 100 to convert percentage to decimal
                mapped_row['CompletionPercentage'] = float(completion) / 100.0
            except (ValueError, TypeError):
                mapped_row['CompletionPercentage'] = None
        else:
            mapped_row['CompletionPercentage'] = None
        
        # CountryId - Use the looked up value
        mapped_row['CountryId'] = country_id
        
        # SiteName
        mapped_row['SiteName'] = site_name if pd.notna(site_name) else None
        
        # Note: ActivityId and ShowData fields are intentionally excluded per requirements
        
        # Add metadata for reference
        mapped_row['_excel_row_index'] = idx
        mapped_row['_instance_id'] = row.get('_instance_id', None)
        mapped_row['_source_file'] = row.get('_source_file', None)
        mapped_row['_country_name'] = country_name if pd.notna(country_name) else None
        mapped_row['_site_name'] = site_name if pd.notna(site_name) else None
        
        mapped_data.append(mapped_row)
    
    # Print unmatched lookups for review
    if unmatched_countries:
        print(f"\n⚠ Warning: Unmatched Countries ({len(unmatched_countries)}):")
        for c in sorted(unmatched_countries):
            print(f"   - '{c}'")
    
    if unmatched_sites:
        print(f"\n⚠ Warning: Unmatched Sites ({len(unmatched_sites)}):")
        for site, country, cid in sorted(unmatched_sites):
            print(f"   - Site: '{site}', Country: '{country}' (ID: {cid})")

    print(f"\nGPS validation summary:")
    print(f"   Correct            : {gps_actions.get('ok', 0)}")
    print(f"   Swapped & fixed    : {gps_actions.get('swapped', 0)}")
    print(f"   Bad / nulled out   : {gps_actions.get('bad', 0)}")
    print(f"   NULL in source     : {gps_actions.get('null', 0)}")
    print(f"   No site reference  : {gps_actions.get('no_ref', 0)}")
    print(f"   Used fallback GPS  : {gps_actions.get('fallback', 0)}")
    
    print(f"\nFiltered out records with NULL SiteId: {len(df) - len(mapped_data)} rows")
    print(f"Final mapped records: {len(mapped_data)}")

    return mapped_data, gps_actions

def filter_primary_rows_only(data):
    """Filter to only include primary rows (those with actual Instance IDs)."""
    return [row for row in data if pd.notna(row.get('_instance_id'))]

def consolidate_instance_data(data):
    """
    For records with the same Instance ID, ensure all non-ImagePath fields
    have the same values (copied from the most complete record in the group).
    Only ImagePath should vary across records of the same instance.
    """
    # Group records by Instance ID
    from collections import defaultdict
    instance_groups = defaultdict(list)
    
    for record in data:
        instance_id = record.get('_instance_id')
        if pd.notna(instance_id):
            instance_groups[instance_id].append(record)
    
    consolidated = []
    
    for instance_id, group in instance_groups.items():
        if len(group) == 1:
            # Single record for this instance, keep as is
            consolidated.append(group[0])
        else:
            # Multiple records for same instance
            # Find the "primary" record - the one with the most non-null values (excluding ImagePath and metadata)
            exclude_fields = {'ImagePath', '_excel_row_index', '_instance_id',
                            '_source_file', '_country_name', '_site_name', 'Id',
                            'Longitude', 'latitude'}  # GPS fields stay with each record
            
            def count_populated_fields(record):
                return sum(1 for k, v in record.items() 
                          if k not in exclude_fields and v is not None)
            
            # Find primary record (most populated)
            primary_record = max(group, key=count_populated_fields)
            
            # Copy non-ImagePath, non-metadata fields from primary to all records in group
            fields_to_copy = {k: v for k, v in primary_record.items() 
                             if k not in exclude_fields and not k.startswith('_')}
            
            for record in group:
                # Copy all fields except ImagePath and metadata
                for field, value in fields_to_copy.items():
                    if field in record:
                        record[field] = value
                consolidated.append(record)
    
    return consolidated

def save_as_json(data, filename, include_nulls=True):
    """Save the mapped data as JSON file."""
    # Fields to exclude from output
    excluded_fields = {'ActivityId', 'ShowData'}
    
    clean_data = []
    for row in data:
        if include_nulls:
            # Keep all fields except metadata and excluded fields
            clean_row = {k: v for k, v in row.items() 
                        if not k.startswith('_') and k not in excluded_fields}
        else:
            # Remove None values and excluded fields
            clean_row = {k: v for k, v in row.items() 
                         if not k.startswith('_') and v is not None and k not in excluded_fields}
        clean_data.append(clean_row)
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(clean_data, f, indent=2, default=str)
    
    print(f"✓ Saved JSON to: {filename}")
    print(f"   Records: {len(clean_data)}")

def generate_manifest(data, filename, timestamp, gps_actions):
    """Generate a manifest/summary file in Markdown format for the mapped data."""
    from collections import Counter
    
    # Calculate statistics
    total = len(data)
    by_country = Counter(r.get('CountryId') for r in data if r.get('CountryId'))
    by_site = Counter((r.get('SiteId'), r.get('SiteName')) for r in data if r.get('SiteId'))
    
    # GPS stats
    has_gps = sum(1 for r in data if r.get('Longitude') and r.get('latitude'))
    null_gps = total - has_gps
    
    # Find sites missing GPS reference (causing null_gps)
    null_gps_sites = Counter((r.get('SiteId'), r.get('SiteName')) 
                            for r in data if not (r.get('Longitude') and r.get('latitude')))
    
    # Country name mapping for display
    country_names = {1: 'Ethiopia', 2: 'Sudan', 3: 'Somalia', 4: 'Uganda'}
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("# Mapped Data Manifest\n\n")
        
        f.write(f"**Generated:** `{timestamp}`\n\n")
        f.write(f"**Total Records:** {total}\n\n")
        
        f.write("## Country Breakdown\n\n")
        f.write("| Country | Records |\n")
        f.write("|---------|--------:|\n")
        for cid in sorted(by_country.keys()):
            cname = country_names.get(cid, f'CountryId_{cid}')
            f.write(f"| {cname} | {by_country[cid]:,} |\n")
        f.write(f"| **TOTAL** | **{total:,}** |\n\n")
        
        f.write("## Site Breakdown\n\n")
        f.write("| SiteId | Site Name | Records |\n")
        f.write("|--------|-----------|--------:|\n")
        for (sid, sname), cnt in sorted(by_site.items(), key=lambda x: x[1], reverse=True):
            f.write(f"| {sid} | {sname} | {cnt:,} |\n")
        f.write(f"| | **TOTAL** | **{total:,}** |\n\n")
        
        f.write("## GPS Statistics\n\n")
        f.write("| Metric | Count |\n")
        f.write("|--------|------:|\n")
        f.write(f"| Records with GPS | {has_gps:,} |\n")
        f.write(f"| Records without GPS | {null_gps:,} |\n")
        f.write(f"| Original GPS (ok) | {gps_actions.get('ok', 0):,} |\n")
        f.write(f"| Swapped & fixed | {gps_actions.get('swapped', 0):,} |\n")
        f.write(f"| Used fallback GPS | {gps_actions.get('fallback', 0) + gps_actions.get('fallback_bad', 0):,} |\n")
        f.write(f"| Bad / nulled out | {gps_actions.get('bad', 0):,} |\n\n")
        
        if null_gps_sites:
            f.write("## Sites Missing GPS Reference\n\n")
            f.write("> Add GPS coordinates to CountrySitesAll for these sites\n\n")
            f.write("| SiteId | Site Name | Records | Status |\n")
            f.write("|--------|-----------|--------:|--------|\n")
            for (sid, sname), cnt in sorted(null_gps_sites.items()):
                f.write(f"| {sid} | {sname} | {cnt:,} | ⚠️ NEEDS GPS |\n")
            f.write("\n")
    
    print(f"✓ Saved manifest to: {filename}")

def parse_args():
    parser = argparse.ArgumentParser(
        description='Generate mapped ProjectImages array from consolidated Excel data.'
    )
    parser.add_argument(
        '--file',
        default=None,
        help='Path to consolidated Excel file (default: latest consolidated_data_*.xlsx in data/consolidated/)'
    )
    return parser.parse_args()


def main():
    args = parse_args()

    print("="*70)
    print("GENERATING ARRAY WITH PROJECTIMAGES KEYS")
    print("  - Country lookup from CountriesAll")
    print("  - Site lookup from CountrySitesAll (using CountryId + SiteName)")
    print("  - SiteId positioned before ImageDescription")
    print("  - Processing ALL countries")
    print("="*70)
    
    # Get country mapping
    print("\n[1] Loading country mapping from CountriesAll table...")
    country_mapping = get_country_mapping()
    print(f"   Found {len(country_mapping)} countries:")
    for name, cid in sorted(country_mapping.items(), key=lambda x: x[1]):
        print(f"     {cid}: {name}")
    
    # Get site mapping
    print("\n[2] Loading site mapping from CountrySitesAll table...")
    site_mapping = get_site_mapping()
    print(f"   Found {len(site_mapping)} site mappings")

    # Show sample site mappings
    print("   Sample mappings (SiteName, CountryId) -> SiteId:")
    samples = list(site_mapping.items())[:5]
    for (site, cid), sid in samples:
        print(f"     ('{site}', {cid}) -> {sid}")
    if len(site_mapping) > 5:
        print(f"     ... and {len(site_mapping) - 5} more")

    # Get GPS reference ranges
    print("\n[2b] Loading GPS reference ranges from CountrySitesAll...")
    site_ranges = get_site_gps_ranges(tolerance=1.5)
    print(f"   Loaded ranges for {len(site_ranges)} site(s):")
    for sid, r in sorted(site_ranges.items()):
        print(f"     SiteId {sid} ({r['name']}): "
              f"Lon [{r['lon_min']:.4f}, {r['lon_max']:.4f}]  "
              f"Lat [{r['lat_min']:.4f}, {r['lat_max']:.4f}]")
    
    # Get site name to ID mapping for GPS fallback
    site_name_to_id = get_site_name_to_id_mapping()
    print(f"   Loaded {len(site_name_to_id)} site name mappings for GPS fallback")
    
    # Load consolidated data
    print("\n[3] Loading consolidated Excel data...")
    df = load_consolidated_data(args.file)
    print(f"   Total rows in Excel: {len(df)}")

    # Forward-fill blank cells within each instance
    # (Multi-image instances only have metadata on the first row)
    print("\n[3a] Forward-filling blank cells within instances...")
    if '_instance_id' in df.columns:
        # First, forward-fill the _instance_id itself (for linked rows without explicit ID)
        df['_instance_id'] = df['_instance_id'].ffill()
        
        # Now group by instance and forward fill metadata columns (including GPS)
        # All rows in an instance should inherit from the first row except ImagePath
        df['Country Name'] = df.groupby('_instance_id')['Country Name'].ffill()
        df['Site Name'] = df.groupby('_instance_id')['Site Name'].ffill()
        df['Longitude'] = df.groupby('_instance_id')['Longitude'].ffill()
        df['Latitude'] = df.groupby('_instance_id')['Latitude'].ffill()
        
        filled_country = df['Country Name'].notna().sum()
        filled_site = df['Site Name'].notna().sum()
        filled_lon = df['Longitude'].notna().sum()
        filled_lat = df['Latitude'].notna().sum()
        print(f"   After forward-fill: Country={filled_country}, Site={filled_site}, Longitude={filled_lon}, Latitude={filled_lat}")
    else:
        print("   WARNING: _instance_id column not found — forward-fill skipped")

    # No country filtering - process all data

    # DIAGNOSTIC: Show Excel columns and sample values
    print("\n   DIAGNOSTIC - Excel Columns and Sample Values:")
    print("   " + "-"*60)
    target_cols = ['Activity Status', 'Status', 'Comments', 'Completion Percentage', 
                   'Image Description', 'Image Path', 'Country Name', 'Site Name']
    for col in target_cols:
        if col in df.columns:
            sample = df[col].dropna().iloc[0] if not df[col].dropna().empty else "(all null)"
            print(f"   {col:<25} = {str(sample)[:35]}")
        else:
            print(f"   {col:<25} = (COLUMN NOT FOUND)")
    print("   " + "-"*60)
    
    # Map to database structure with lookups
    print("\n[4] Mapping Excel columns to ProjectImages structure...")
    print("   Performing CountryName -> CountryId lookup...")
    print("   Performing (SiteName, CountryId) -> SiteId lookup...")
    mapped_data, gps_actions = map_excel_to_db(df, country_mapping, site_mapping, site_ranges, site_name_to_id)
    
    # Filter to primary rows only
    print("\n[5] Filtering to primary data rows only...")
    primary_data = filter_primary_rows_only(mapped_data)
    print(f"   Total mapped rows: {len(mapped_data)}")
    print(f"   Primary rows (with Instance IDs): {len(primary_data)}")
    
    # Consolidate same-instance records - copy data from primary row to linked rows
    print("\n[6] Consolidating same-instance records...")
    print("   Copying non-ImagePath fields from primary row to linked rows...")
    primary_data = consolidate_instance_data(primary_data)
    print(f"   Consolidated records: {len(primary_data)}")
    
    # Show sample - find records with actual data
    print("\n" + "="*70)
    print("SAMPLE OUTPUT (Records with ActivityStatus, Comments, CompletionPercentage)")
    print("="*70)
    
    # Find records that have at least one of these fields populated
    sample_records = []
    for record in primary_data:
        if (record.get('ActivityStatus') is not None or 
            record.get('Comments') is not None or 
            record.get('CompletionPercentage') is not None):
            sample_records.append(record)
        if len(sample_records) >= 3:
            break
    
    # If no records with data found, fall back to first 3
    if not sample_records:
        sample_records = primary_data[:3]
    
    for i, record in enumerate(sample_records):
        print(f"\n--- Record {i+1} ---")
        # Get fields excluding metadata
        db_fields = {k: v for k, v in record.items() if not k.startswith('_')}
        
        # Show fields in order (excluding ActivityId and ShowData per requirements)
        field_order = ['Id', 'SiteId', 'ImageDescription', 'ImagePath', 'Imagedate', 
                       'Longitude', 'latitude', 'ActivityStatus', 'Comments', 
                       'ProjectDescription', 'CompletionPercentage', 'CountryId', 
                       'SiteName']
        
        for key in field_order:
            if key in db_fields:
                value = db_fields[key]
                display_value = str(value)[:60] if value is not None else "None"
                print(f"  {key:<25} = {display_value}")
        
        # Show metadata
        print(f"  --- Metadata ---")
        print(f"  _country_name            = {record.get('_country_name')}")
        print(f"  _site_name               = {record.get('_site_name')}")
        print(f"  _instance_id             = {str(record.get('_instance_id'))[:40]}...")
    
    # Verify SiteId is positioned before ImageDescription
    print("\n" + "="*70)
    print("VERIFICATION: Field Order Check")
    print("="*70)
    if primary_data:
        first_record_keys = list(primary_data[0].keys())
        # Find positions
        siteid_pos = first_record_keys.index('SiteId') if 'SiteId' in first_record_keys else -1
        imagedesc_pos = first_record_keys.index('ImageDescription') if 'ImageDescription' in first_record_keys else -1
        
        print(f"   SiteId position: {siteid_pos}")
        print(f"   ImageDescription position: {imagedesc_pos}")
        
        if siteid_pos >= 0 and imagedesc_pos >= 0 and siteid_pos < imagedesc_pos:
            print("   ✓ SiteId is correctly positioned BEFORE ImageDescription")
        else:
            print("   ✗ Warning: SiteId may not be in the correct position")
    
    # Generate timestamp for filename
    from datetime import datetime
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # Save to JSON file
    print("\n" + "="*70)
    print("SAVING OUTPUT")
    print("="*70)

    base_dir = r"d:\MethLab\ActivityMonitoring\data\mapped"
    os.makedirs(base_dir, exist_ok=True)

    # Save with timestamp in filename (no 'all', no 'v2', no country suffix)
    output_file = os.path.join(base_dir, f"mapped_data_{timestamp}.json")
    save_as_json(mapped_data, output_file)

    # Generate manifest/summary file
    manifest_file = os.path.join(base_dir, f"mapped_data_{timestamp}_manifest.md")
    generate_manifest(mapped_data, manifest_file, timestamp, gps_actions)

    # Return the array for programmatic use
    print(f"\n{'='*70}")
    print("ARRAY READY FOR USE")
    print(f"{'='*70}")
    print(f"\nThe array is available as 'mapped_data' with {len(mapped_data)} records")
    print(f"Manifest saved to: {manifest_file}")

    return mapped_data

if __name__ == "__main__":
    mapped_data = main()  # noqa: F841
