# R-WASH Activity Monitoring Questionnaire Processing

## Project Overview

This project provides an automated data pipeline for ingesting, cleaning, and loading activity monitoring questionnaire data from ODK Central into a Microsoft SQL Server database. The processed data feeds the R-WASH Power BI reporting dashboard, enabling real-time monitoring of WASH (Water, Sanitation, and Hygiene) activities across refugee camps in Ethiopia, Sudan, and Somalia.

## System Architecture

The data pipeline connects five core systems in sequence:

```
┌─────────────────┐    ┌───────────────────────┐    ┌──────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   ODK Central   │───▶│  R-WASH Laravel     │───▶│   Data Pipeline  │───▶│   SQL Server    │───▶│   Power BI      │
│(Data Collection)│    │  (Data Transformer)   │    │  (This Project)  │    │  (Data Storage) │    │  (Dashboard)    │
└─────────────────┘    └───────────────────────┘    └──────────────────┘    └─────────────────┘    └─────────────────┘
         │                        │                         │                      │                      │
         ▼                        ▼                         ▼                      ▼                      ▼
   Mobile Data              Excel Exports             Python Scripts         ProjectImages         Real-time
   Collectors              (raw downloads)             Pandas/PyODBC          Table                 Reporting
```

### Integration Points

| System | Role | Integration Method |
|--------|------|-------------------|
| **ODK Central** | Mobile data collection platform | Field data capture via mobile devices |
| **R-WASH Laravel Dashboard** | Data transformer / export hub | Downloads raw Excel from ODK Central, provides exports |
| **Data Pipeline** (This Project) | ETL processing | Ingests Excel, validates, maps, loads to database |
| **Microsoft SQL Server** | Primary data warehouse | Direct ODBC connection |
| **Power BI** | Reporting and visualization | Connects to SQL Server views |

## Data Pipeline

The pipeline processes data through 5 sequential stages, managed by numbered Python scripts:

### Stage 1: Data Consolidation (`001-consolidate_odk_data.py`)

- **Input**: Multiple raw Excel exports from ODK Central (`data/raw/`)
- **Process**: 
  - Merges separate Excel files into single dataset
  - Generates unique instance IDs for multi-image submissions
  - Creates instance summary report
- **Output**: `data/consolidated/consolidated_data_*.xlsx`

### Stage 2: Site Registration (`002-add_missing_sites.py`)

- **Purpose**: Add new sites to `CountrySitesAll` reference table
- **Input**: Site names discovered in data but missing from database
- **Output**: Updated `CountrySitesAll` with GPS coordinates

### Stage 3: GPS Validation (`003-fix_gps_dynamic.py`)

- **Purpose**: Correct swapped coordinates using site-specific GPS ranges
- **Logic**: Compares recorded GPS against known site boundaries
- **Output**: Corrected coordinates in database

### Stage 4: Data Mapping (`004-generate_import_array.py`)

- **Input**: Consolidated Excel file
- **Transformations**:
  - Country name → CountryId lookup
  - Site name + CountryId → SiteId lookup
  - GPS validation and fallback (uses reference coordinates if missing)
  - Forward-fill instance metadata across multi-image rows
  - Generate mapped JSON with database schema alignment
- **Output**: 
  - `data/mapped/mapped_data_*.json`
  - `data/mapped/mapped_data_*_manifest.md`

### Stage 5: Database Insertion (`005-insert_to_project_images.py`)

- **Input**: Mapped JSON data
- **Logic**: 
  - Upsert records (insert new, update existing)
  - Duplicate detection by `(ImagePath, SiteId)` composite key
  - Skips only if exact match exists
- **Output**: Populated `ProjectImages` table in SQL Server

## Project Structure

```
ActivityMonitoring/
├── data/
│   ├── raw/                    # ODK Excel exports
│   ├── consolidated/           # Stage 1 output
│   └── mapped/                 # Stage 4 output (JSON + manifests)
├── src/
│   ├── 001-consolidate_odk_data.py
│   ├── 002-add_missing_sites.py
│   ├── 003-fix_gps_dynamic.py
│   ├── 004-generate_import_array.py
│   └── 005-insert_to_project_images.py
├── .env                        # Database credentials (not in git)
├── .env.example                # Template for credentials
├── .gitignore                  # Excludes .env and data files
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

## Quick Start

### Prerequisites

- Python 3.10+
- Microsoft SQL Server (with ODBC Driver 17)
- Git

### Installation

```bash
# Clone repository
git clone <repository-url>
cd ActivityMonitoring

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your database credentials
```

### Configuration

Create `.env` file in project root:

```env
DB_SERVER=localhost,1433
DB_DATABASE=WashMay2026
DB_USERNAME=your_username
DB_PASSWORD=your_password
```

### Running the Pipeline

Execute scripts in order:

```bash
# Stage 1: Consolidate raw ODK exports
python src/001-consolidate_odk_data.py

# Stage 2: Add any missing sites (if needed)
python src/002-add_missing_sites.py

# Stage 3: Fix GPS coordinates (if needed)
python src/003-fix_gps_dynamic.py

# Stage 4: Map to database structure
python src/004-generate_import_array.py
# Or specify custom file:
# python src/004-generate_import_array.py --file path/to/custom.xlsx

# Stage 5: Insert into database
python src/005-insert_to_project_images.py
# Or specify custom JSON:
# python src/005-insert_to_project_images.py --file path/to/custom.json
```

## Data Schema

### Source Data (ODK Export)

Key columns from ODK Excel exports:
- `Country Name`, `Site Name` - Location identifiers
- `Longitude`, `Latitude` - GPS coordinates
- `Activity Status`, `Completion Percentage` - Progress metrics
- `Comments`, `Image Description` - Text data
- `Image Path` - Reference to stored images
- `Image Date` - Timestamp

### Target Database Table: `ProjectImages`

| Column | Type | Description |
|--------|------|-------------|
| Id | INT (PK) | Auto-increment primary key |
| SiteId | INT | Foreign key to CountrySitesAll |
| ImageDescription | NVARCHAR | Description of activity/image |
| ImagePath | NVARCHAR | URL/path to image |
| Imagedate | DATETIME | Activity timestamp |
| Longitude | NVARCHAR | GPS longitude |
| latitude | NVARCHAR | GPS latitude |
| ActivityStatus | NVARCHAR | Current status |
| Comments | NVARCHAR | Additional notes |
| ProjectDescription | NVARCHAR | Project context |
| CompletionPercentage | INT | Progress indicator |
| CountryId | INT | Foreign key to CountriesAll |
| SiteName | NVARCHAR | Denormalized site name |

## Key Features

### GPS Data Integrity

- **Validation**: Coordinates checked against site-specific GPS ranges
- **Swap Detection**: Automatically corrects longitude/latitude swaps
- **Fallback**: Uses reference GPS from `CountrySitesAll` when source data missing
- **Forward-fill**: Multi-image instances inherit GPS from first row

### Duplicate Handling

- **Composite Key**: Uniqueness enforced on `(ImagePath, SiteId)`
- **Upsert Logic**: Updates existing records, inserts new ones
- **Idempotent**: Safe to re-run on same dataset

### Audit Trail

Each pipeline run generates:
- **JSON Output**: Machine-readable mapped data
- **Markdown Manifest**: Human-readable summary with:
  - Country/site breakdowns
  - GPS statistics (original, fallback, bad)
  - Sites missing GPS reference

## Troubleshooting

### No consolidated files found

Ensure ODK Excel exports are placed in `data/raw/` before running Stage 1.

### GPS fallback high count

Expected for multi-image instances where only first row has GPS. Forward-fill logic handles this. If count is unexpectedly high, check that GPS coordinates exist in `CountrySitesAll` for all active sites.

### Database connection errors

Verify:
1. `.env` file exists with correct credentials
2. SQL Server is running and accessible
3. ODBC Driver 17 for SQL Server is installed

## License

Internal use only - R-WASH Project

## Contact

For technical issues or feature requests, contact the R-WASH data team.
