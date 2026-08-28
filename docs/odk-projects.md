# ODK Central Projects

The image download script (`006-download_images.py`) is configured with a registry of ODK Central projects. Each project maps a human-readable name to a `(project_id, form_id)` pair.

## Configured Projects

| Name | Project ID | Form ID | Description |
|------|-----------|---------|-------------|
| `SomaliaGarowe` | 21 | `RWASH_Activity_20250730` | Somalia - Garowe |
| `SomaliaDollow` | 20 | `RWASH_Activity_20250730` | Somalia - Dollow |
| `EthiopiaV3` | 36 | `RWASH_Activity_20250924` | Ethiopia (latest version) |
| `EthiopiaV2` | 26 | `RWASH_Activity_20250831` | Ethiopia (v2) |
| `SudanActivityMonitoringV2` | 37 | `R-WASH Activity Monitoring Questionnaire - Sudan - v2` | Sudan (v2) |
| `Ethiopia` | 5 | `RWASH_Activity_20240815` | Ethiopia (original) |
| `Somalia` | 8 | `RWASH_Activity_20240924` | Somalia (original) |
| `Sudan` | 14 | `R-WASH Activity Monitoring Questionnaire - Sudan - Translated` | Sudan (translated) |
| `SomaliaDollowV3` | 42 | `RWASH_Activity_20260405` | Somalia - Dollow (latest version) |

## Managing projects

### Listing available projects

```bash
python src/006-download_images.py --list
```

### Downloading specific projects

```bash
python src/006-download_images.py SomaliaGarowe EthiopiaV3
```

### Adding a new project

Edit the `PROJECTS` dictionary in `src/006-download_images.py`:

```python
PROJECTS = {
    ...
    "NewProjectName": (project_id, "form_id_string"),
}
```

The `project_id` is an integer and the `form_id` is the XML form ID string as configured in ODK Central.

## ODK Central API

### Authentication

The pipeline uses session token authentication:

1. `get_session_token(url, email, password)` → returns a bearer token
2. `build_authenticated_session(token)` → returns a `requests.Session` with auth headers

### Data fetching

`fetch_all_form_data()` retrieves OData tables for a given project/form. The main table is `Submissions`, which contains all submission records including image attachment filenames.

### Attachment download

Attachments are downloaded via the ODK Central API endpoint:

```
GET /v1/projects/{project_id}/forms/{form_id}/submissions/{instance_id}/attachments/{filename}
```

The `ODKImageDownloader` class handles:
- Checking if a file already exists locally (skip if so)
- Downloading the attachment bytes
- Decompressing and re-compressing with EXIF orientation correction
- Saving to `data/images/`
