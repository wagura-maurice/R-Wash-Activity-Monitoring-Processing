"""
Insert data from mapped JSON into ProjectImages table.
Checks for duplicates by (ImagePath, SiteId) combination.
"""

import argparse
import json
import pyodbc
import os
import glob
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Database connection parameters from environment (must be set in .env file)
SERVER = os.getenv('DB_SERVER')
DATABASE = os.getenv('DB_DATABASE')
USERNAME = os.getenv('DB_USERNAME')
PASSWORD = os.getenv('DB_PASSWORD')

def get_connection():
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

def load_json_data(filename):
    """Load data from JSON file."""
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)

def _get_instance_id(record):
    """Return the activity/instance identifier for a record."""
    for key in ('Id', 'activity_id', '_instance_id'):
        val = record.get(key)
        if val is not None:
            return val
    return None

def assign_showdata(data):
    """
    Assign ShowData flag within each instance group.

    Records are grouped by their activity/instance identifier. The first
    record in each group keeps its existing ShowData value (or None if
    absent), and each subsequent (repeating) record is assigned 1.
    """
    instance_seen = {}
    for record in data:
        instance_id = _get_instance_id(record)
        if instance_id is None:
            continue
        idx = instance_seen.get(instance_id, 0)
        if idx > 0:
            record['ShowData'] = 1
        instance_seen[instance_id] = idx + 1
    return data

def upsert_record(cursor, record):
    """
    Insert or update a record in ProjectImages table.
    If (ImagePath, SiteId) exists, update all other columns.
    Otherwise, insert a new record.
    Returns ('inserted', rowcount) or ('updated', rowcount).
    """
    image_path = record.get('ImagePath')
    site_id = record.get('SiteId')
    instance_id = _get_instance_id(record)
    showdata = record.get('ShowData')
    
    if image_path is None or site_id is None:
        return ('error', 0)
    
    # Check if record exists
    cursor.execute(
        "SELECT COUNT(*) FROM ProjectImages WHERE ImagePath = ? AND SiteId = ?",
        (image_path, site_id)
    )
    exists = cursor.fetchone()[0] > 0
    
    # Convert string dates to datetime objects if needed
    image_date = record.get('Imagedate')
    if isinstance(image_date, str):
        try:
            image_date = datetime.strptime(image_date, '%Y-%m-%d %H:%M:%S')
        except:
            image_date = None
    
    if exists:
        # UPDATE existing record
        sql = """
        UPDATE ProjectImages SET
            ActivityId = ?,
            ShowData = ?,
            ImageDescription = ?,
            Imagedate = ?,
            Longitude = ?,
            latitude = ?,
            ActivityStatus = ?,
            Comments = ?,
            ProjectDescription = ?,
            CompletionPercentage = ?,
            CountryId = ?,
            SiteName = ?
        WHERE ImagePath = ? AND SiteId = ?
        """
        values = [
            instance_id,
            showdata,
            record.get('ImageDescription'),
            image_date,
            record.get('Longitude'),
            record.get('latitude'),
            record.get('ActivityStatus'),
            record.get('Comments'),
            record.get('ProjectDescription'),
            record.get('CompletionPercentage'),
            record.get('CountryId'),
            record.get('SiteName'),
            image_path,
            site_id
        ]
        cursor.execute(sql, values)
        return ('updated', cursor.rowcount)
    else:
        # INSERT new record
        sql = """
        INSERT INTO ProjectImages (
            SiteId, ActivityId, ShowData, ImageDescription, ImagePath, Imagedate,
            Longitude, latitude, ActivityStatus, Comments,
            ProjectDescription, CompletionPercentage, CountryId,
            SiteName
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        values = [
            site_id,
            instance_id,
            showdata,
            record.get('ImageDescription'),
            image_path,
            image_date,
            record.get('Longitude'),
            record.get('latitude'),
            record.get('ActivityStatus'),
            record.get('Comments'),
            record.get('ProjectDescription'),
            record.get('CompletionPercentage'),
            record.get('CountryId'),
            record.get('SiteName')
        ]
        cursor.execute(sql, values)
        return ('inserted', cursor.rowcount)

def main():
    parser = argparse.ArgumentParser(description='Insert ProjectImages data from a JSON file.')
    parser.add_argument(
        '--file',
        default=None,
        help='Path to the JSON file to insert (default: latest mapped_data_*.json in data/mapped/)'
    )
    args = parser.parse_args()

    print("="*70)
    print("INSERTING DATA INTO ProjectImages TABLE")
    print("="*70)
    
    # Load JSON data
    json_file = args.file
    if json_file is None:
        # Find latest mapped data file
        pattern = os.path.join(BASE_DIR, "data", "mapped", "mapped_data_*.json")
        files = glob.glob(pattern)
        if not files:
            print("ERROR: No mapped_data_*.json files found in data/mapped/")
            return
        json_file = max(files, key=os.path.getmtime)
    
    print(f"\n[1] Loading data from: {os.path.basename(json_file)}")
    data = load_json_data(json_file)
    print(f"   Records to insert: {len(data)}")
    
    # Connect to database
    print("\n[2] Connecting to database...")
    conn = get_connection()
    cursor = conn.cursor()
    print("   Connected successfully")
    
    # Check current row count
    cursor.execute("SELECT COUNT(*) FROM ProjectImages")
    current_count = cursor.fetchone()[0]
    print(f"\n[3] Current ProjectImages row count: {current_count}")
    
    # Assign ShowData flag within each instance group
    print("\n[3a] Assigning ShowData flag to repeating instance records...")
    data = assign_showdata(data)
    flagged_count = sum(1 for r in data if r.get('ShowData') == 1)
    print(f"   Flagged {flagged_count} repeating records with ShowData=1")
    
    # Upsert records
    print("\n[4] Upserting records...")
    print("   Inserting new records, updating existing ones...")
    inserted_count = 0
    updated_count = 0
    error_count = 0
    errors = []
    
    for i, record in enumerate(data, 1):
        try:
            action, rowcount = upsert_record(cursor, record)
            
            if action == 'inserted':
                inserted_count += 1
            elif action == 'updated':
                updated_count += 1
                if updated_count <= 5:
                    image_path = record.get('ImagePath', 'None')
                    site_id = record.get('SiteId')
                    print(f"   Updated (SiteId {site_id}): {image_path[:50] if image_path else 'None'}...")
            else:
                error_count += 1
            
            # Commit every 100 records
            if i % 100 == 0:
                conn.commit()
                print(f"   Progress: {i}/{len(data)} records processed...")
                
        except Exception as e:
            error_count += 1
            errors.append({
                'index': i,
                'id': record.get('Id', 'N/A'),
                'error': str(e)
            })
            if error_count <= 5:
                print(f"   Error on record {i}: {e}")
    
    # Final commit
    conn.commit()
    
    # Verify new count
    cursor.execute("SELECT COUNT(*) FROM ProjectImages")
    new_count = cursor.fetchone()[0]
    inserted = new_count - current_count
    
    print(f"\n[5] Upsert complete!")
    print(f"   Inserted (new): {inserted_count}")
    print(f"   Updated (existing): {updated_count}")
    print(f"   Errors: {error_count}")
    print(f"   Total rows in table: {new_count} (net change: {new_count - current_count:+d})")
    
    if errors:
        print(f"\n[6] Error summary:")
        for err in errors[:10]:
            print(f"   Record {err['index']} (Id: {err['id'][:30]}...): {err['error']}")
        if len(errors) > 10:
            print(f"   ... and {len(errors) - 10} more errors")
    
    cursor.close()
    conn.close()
    print("\n[7] Connection closed")
    print("="*70)

if __name__ == "__main__":
    main()
