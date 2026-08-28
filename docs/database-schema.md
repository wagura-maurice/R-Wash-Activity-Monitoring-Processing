# Database Schema

## SQL Server Connection

The pipeline connects to Microsoft SQL Server via ODBC (pyodbc).

### Connection parameters

| Variable | Description | Example |
|----------|-------------|---------|
| `DB_SERVER` | SQL Server hostname and port | `localhost,1433` |
| `DB_DATABASE` | Database name | `WashMay2026` |
| `DB_USERNAME` | SQL Server username | `sa` |
| `DB_PASSWORD` | SQL Server password | — |

### Driver

Requires **ODBC Driver 17 for SQL Server** to be installed on the machine running the pipeline.

## Tables

### `ProjectImages`

Primary data table storing activity monitoring image records.

| Column | Type | Description |
|--------|------|-------------|
| `Id` | INT (PK) | Auto-increment primary key |
| `SiteId` | INT (FK) | Foreign key to `CountrySitesAll` |
| `ImageDescription` | NVARCHAR | Description of activity/image |
| `ImagePath` | NVARCHAR | URL to image on rwash.net (e.g. `https://rwash.net/filename.jpg`) |
| `Imagedate` | DATETIME | Activity timestamp |
| `Longitude` | NVARCHAR | GPS longitude (string) |
| `latitude` | NVARCHAR | GPS latitude (string) |
| `ActivityStatus` | NVARCHAR | Current status of the activity |
| `Comments` | NVARCHAR | Additional notes |
| `ProjectDescription` | NVARCHAR | Project context |
| `CompletionPercentage` | INT | Progress indicator (0-100) |
| `CountryId` | INT (FK) | Foreign key to `CountriesAll` |
| `SiteName` | NVARCHAR | Denormalized site name |

### Upsert logic

- **Composite key**: `(ImagePath, SiteId)` determines uniqueness
- **Insert**: New records where no match on composite key
- **Update**: Existing records where composite key matches but other fields differ
- **Skip**: Exact match on all fields — no action taken
- **Idempotent**: Safe to re-run on the same dataset

### `CountrySitesAll`

Reference table for sites (camps/locations).

| Column | Type | Description |
|--------|------|-------------|
| `Id` | INT (PK) | Auto-increment primary key |
| `CountryId` | INT (FK) | Foreign key to `CountriesAll` |
| `SiteName` | NVARCHAR | Name of the site/camp |
| `Longitude` | NVARCHAR | Reference GPS longitude |
| `Latitude` | NVARCHAR | Reference GPS latitude |

### `CountriesAll`

Reference table for countries.

| Column | Type | Description |
|--------|------|-------------|
| `Id` | INT (PK) | Auto-increment primary key |
| `CountryName` | NVARCHAR | Name of the country |

## GPS validation rules

Coordinates are validated against site-specific ranges stored in `003-fix_gps_dynamic.py`:

1. **Range check**: Longitude/latitude must fall within known bounds for the site
2. **Swap detection**: If longitude is in latitude range and vice versa, they are swapped
3. **Fallback**: If GPS is missing or invalid, reference coordinates from `CountrySitesAll` are used
4. **Forward-fill**: Multi-image instances inherit GPS from the first row in the group
