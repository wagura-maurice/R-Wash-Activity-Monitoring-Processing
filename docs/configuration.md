# Configuration

All credentials and environment-specific settings are managed via a `.env` file in the project root. Copy `.env.example` to `.env` and fill in your values.

## Environment Variables

### Database (SQL Server)

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `DB_SERVER` | Yes | SQL Server hostname and port | `localhost,1433` |
| `DB_DATABASE` | Yes | Database name | `WashMay2026` |
| `DB_USERNAME` | Yes | SQL Server username | `sa` |
| `DB_PASSWORD` | Yes | SQL Server password | — |

### ODK Central API

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `ODK_CENTRAL_URL` | Yes | ODK Central server URL | `https://r-washingtesting.com` |
| `ODK_CENTRAL_EMAIL` | Yes | ODK Central account email | — |
| `ODK_CENTRAL_PASSWORD` | Yes | ODK Central account password | — |

### FTPS Upload (rwash.net)

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `FTP_HOST` | Yes | FTPS server hostname | `ftp.rwash.net` |
| `FTP_PORT` | No | FTPS server port | `21` |
| `FTP_USER` | Yes | FTPS username | — |
| `FTP_PASSWORD` | Yes | FTPS password | — |
| `FTP_REMOTE_DIR` | No | Remote upload directory | `/` |

### Email Notifications (SMTP)

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `MAIL_MAILER` | No | Email transport method | `smtp` |
| `MAIL_HOST` | Yes | SMTP server hostname | — |
| `MAIL_PORT` | Yes | SMTP server port | `2525` |
| `MAIL_USERNAME` | Yes | SMTP username | — |
| `MAIL_PASSWORD` | Yes | SMTP password | — |
| `MAIL_TO` | Yes | Primary recipient email | — |
| `MAIL_CC` | No | CC recipient email | — |
| `MAIL_FROM` | No | Sender email address | `noreply@rwash-monitoring.com` |
| `MAIL_FROM_NAME` | No | Sender display name | `R-WASH Monitoring System` |

**Email Features:**
- Professional R-WASH branding with UNICEF logo
- Status indicators: Success (green), Partial (gold), Failure (red)
- Processing statistics for each stage
- Contact information in footer
- Professional subject lines (no file extensions)

**Example Configuration (Mailtrap Sandbox):**
```env
MAIL_MAILER=smtp
MAIL_HOST=sandbox.smtp.mailtrap.io
MAIL_PORT=2525
MAIL_USERNAME=your_mailtrap_username
MAIL_PASSWORD=your_mailtrap_password
MAIL_TO=recipient@example.com
MAIL_CC=cc_recipient@example.com
```

## Setup

```bash
# Copy the template
cp .env.example .env

# Edit with your credentials
# On Windows:
notepad .env
# On macOS/Linux:
nano .env
```

## Security

- `.env` is listed in `.gitignore` and will never be committed
- `.env.example` contains placeholder values only — safe to commit
- Never share actual credentials in commits, issues, or chat
- Rotate credentials periodically, especially after team member changes

## Dependencies

Install all Python dependencies:

```bash
pip install -r requirements.txt
```

### Key packages

| Package | Purpose |
|---------|---------|
| `pandas` | Data manipulation and Excel parsing |
| `openpyxl` | Excel file reading/writing |
| `pyodbc` | SQL Server ODBC connectivity |
| `python-dotenv` | `.env` file loading and email configuration |
| `requests` | HTTP client for ODK Central API |
| `Pillow` | Image processing (compression, EXIF orientation) |
| `pillow-heif` | HEIC/HEIF image format support |
| `SQLAlchemy` | Database ORM utilities |

### System requirements

- Python 3.10+
- ODBC Driver 17 for SQL Server
- Git
- Network access to:
  - ODK Central server
  - SQL Server
  - `ftp.rwash.net` (for image uploads)

## Directory structure

The pipeline expects these directories under `data/`:

```
data/
├── raw/           # Place ODK Excel exports here (Stage 1 input)
├── consolidated/  # Stage 1 output (auto-created)
├── mapped/        # Stage 4 output (auto-created)
└── images/        # Stage 6-8 image files (auto-created)
```

All subdirectories are auto-created by the scripts as needed. The `data/images/` directory is gitignored to prevent committing downloaded images.
