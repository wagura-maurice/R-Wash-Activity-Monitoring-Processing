"""
Consolidate multiple ODK Excel exports into a single file.
Also generates an instance summary report.
"""
import pandas as pd
import glob
import os
from datetime import datetime
from collections import Counter

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, 'data', 'raw')
CONSOLIDATED_DIR = os.path.join(BASE_DIR, 'data', 'consolidated')
INSTANCES_DIR = os.path.join(BASE_DIR, 'data', 'instances')

def load_all_raw_files():
    """Load all RWASH Activity Monitoring Excel files."""
    pattern = os.path.join(RAW_DIR, 'RWASH_Activity_Monitoring_Questionnaire__*.xlsx')
    files = glob.glob(pattern)
    
    if not files:
        raise FileNotFoundError(f"No raw Excel files found in {RAW_DIR}")
    
    print(f"Found {len(files)} raw files:")
    for f in sorted(files):
        print(f"  - {os.path.basename(f)}")
    
    return files

def consolidate_files(files):
    """Consolidate all files into a single DataFrame."""
    all_data = []
    
    for file_path in files:
        print(f"\nLoading: {os.path.basename(file_path)}")
        
        try:
            df = pd.read_excel(file_path)
            
            # Add source file metadata
            df['_source_file'] = os.path.basename(file_path)
            
            # Extract instance ID from relevant columns (ODK exports use different formats)
            instance_col = None
            for col in df.columns:
                if 'instance' in col.lower() and 'id' in col.lower():
                    instance_col = col
                    break
            
            if instance_col:
                df['_instance_id'] = df[instance_col]
            else:
                # Create from index if no instance ID found
                df['_instance_id'] = df.index.astype(str).apply(lambda x: f'row_{x}')
            
            all_data.append(df)
            print(f"  Rows: {len(df)}, Columns: {len(df.columns)}")
            
        except Exception as e:
            print(f"  Error loading file: {e}")
            continue
    
    if not all_data:
        raise ValueError("No data loaded from any files")
    
    # Combine all data
    consolidated = pd.concat(all_data, ignore_index=True)
    
    print(f"\n{'='*60}")
    print(f'Total consolidated rows: {len(consolidated)}')
    print(f'Total columns: {len(consolidated.columns)}')
    
    return consolidated

def generate_instance_summary(df):
    """Generate summary statistics per unique instance."""
    if '_instance_id' not in df.columns:
        print("Warning: No _instance_id column found for summary")
        return None
    
    print("\nGenerating instance summary...")
    
    # Group by instance
    summary = []
    for instance_id, group in df.groupby('_instance_id'):
        if pd.isna(instance_id):
            continue
            
        summary.append({
            'instance_id': instance_id,
            'row_count': len(group),
            'countries': ', '.join(group['Country Name'].dropna().unique()) if 'Country Name' in group.columns else 'N/A',
            'sites': ', '.join(group['Site Name'].dropna().unique()) if 'Site Name' in group.columns else 'N/A',
            'first_submission': group['Imagedate'].min() if 'Imagedate' in group.columns else None,
            'last_submission': group['Imagedate'].max() if 'Imagedate' in group.columns else None,
            'source_files': ', '.join(group['_source_file'].unique()) if '_source_file' in group.columns else 'N/A',
        })
    
    summary_df = pd.DataFrame(summary)
    print(f"Unique instances: {len(summary_df)}")
    
    return summary_df

def main():
    print('='*60)
    print('ODK DATA CONSOLIDATION')
    print('='*60)
    
    # Create output directories
    os.makedirs(CONSOLIDATED_DIR, exist_ok=True)
    os.makedirs(INSTANCES_DIR, exist_ok=True)
    
    # Load raw files
    raw_files = load_all_raw_files()
    
    # Consolidate
    consolidated_df = consolidate_files(raw_files)
    
    # Save consolidated data
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    consolidated_file = os.path.join(CONSOLIDATED_DIR, f'consolidated_data_{timestamp}.xlsx')
    consolidated_df.to_excel(consolidated_file, index=False)
    print(f"\n✓ Saved consolidated data: {consolidated_file}")
    
    # Generate and save instance summary
    summary_df = generate_instance_summary(consolidated_df)
    if summary_df is not None:
        summary_file = os.path.join(INSTANCES_DIR, f'instance_summary_{timestamp}.xlsx')
        summary_df.to_excel(summary_file, index=False)
        print(f"✓ Saved instance summary: {summary_file}")
    
    print('\n' + '='*60)
    print('CONSOLIDATION COMPLETE')
    print('='*60)

if __name__ == '__main__':
    main()
