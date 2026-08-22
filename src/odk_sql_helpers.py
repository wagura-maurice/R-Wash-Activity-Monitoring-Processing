import json
from io import BytesIO
from pathlib import Path
import re
import urllib.parse

import pandas as pd
import requests
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import create_engine

# Increase PIL image size limit to handle large images (set to None to disable limit)
Image.MAX_IMAGE_PIXELS = None


IMAGE_FILENAME_PATTERN = re.compile(r"\.(?:jpe?g|png|gif|bmp|webp|heic|heif|tiff?)$", re.IGNORECASE)


def get_session_token(central_url, email, password, timeout=60):
    r = requests.post(
        f"{central_url}/v1/sessions",
        json={"email": email, "password": password},
        timeout=timeout,
    )
    r.raise_for_status()
    return r.json()["token"]


def build_authenticated_session(token):
    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


def list_odata_tables(central_url, token, project_id, form_id, timeout=60, session=None):
    svc = f"{central_url}/v1/projects/{project_id}/forms/{form_id}.svc"
    http = session or build_authenticated_session(token)
    r = http.get(svc, timeout=timeout)
    r.raise_for_status()
    return [item["name"] for item in r.json()["value"]]


def fetch_table(central_url, token, project_id, form_id, table_name, timeout=60, session=None):
    url = f"{central_url}/v1/projects/{project_id}/forms/{form_id}.svc/{table_name}"
    http = session or build_authenticated_session(token)
    r = http.get(url, timeout=timeout)
    r.raise_for_status()
    return pd.DataFrame(r.json().get("value", []))


def fetch_all_form_data(
    central_url,
    email,
    password,
    project_id,
    form_id,
    timeout=60,
    token=None,
    session=None,
    verbose=False,
):
    token = token or get_session_token(central_url, email, password, timeout=timeout)
    session = session or build_authenticated_session(token)
    tables = list_odata_tables(
        central_url,
        token,
        project_id,
        form_id,
        timeout=timeout,
        session=session,
    )
    if verbose:
        print(f"[ODK] Found {len(tables)} OData tables for form {form_id}.", flush=True)

    dfs = {}
    for index, table_name in enumerate(tables, start=1):
        if verbose:
            print(f"[ODK] Fetching table {index}/{len(tables)}: {table_name}", flush=True)
        dfs[table_name] = fetch_table(
            central_url,
            token,
            project_id,
            form_id,
            table_name,
            timeout=timeout,
            session=session,
        )
    return dfs


def create_sql_engine(server, database, username, password, driver="ODBC Driver 18 for SQL Server"):
    quoted = urllib.parse.quote_plus(
        f"Driver={{{driver}}};"
        f"Server={server};"
        f"Database={database};"
        f"UID={username};"
        f"PWD={password};"
        "TrustServerCertificate=yes;"
    )
    return create_engine(f"mssql+pyodbc:///?odbc_connect={quoted}")


def _json_serialize(value):
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value)
    return value


def _as_geopoint(value):
    return isinstance(value, dict) and value.get("type") == "Point"


def _coord_at(value, index):
    if isinstance(value, (list, tuple)) and len(value) > index:
        return value[index]
    return None


def _looks_like_image_filename(value):
    return isinstance(value, str) and bool(IMAGE_FILENAME_PATTERN.search(value.strip()))


class ODKImageDownloader:
    def __init__(
        self,
        central_url,
        token,
        download_root="images",
        session=None,
        timeout=60,
        jpeg_quality=85,
        webp_quality=85,
        png_compress_level=9,
        verbose=False,
        progress_every=25,
    ):
        self.central_url = central_url.rstrip("/")
        self.timeout = timeout
        self.session = session or build_authenticated_session(token)
        self.download_root = Path(download_root).resolve()
        self.download_root.mkdir(parents=True, exist_ok=True)
        self.jpeg_quality = jpeg_quality
        self.webp_quality = webp_quality
        self.png_compress_level = png_compress_level
        self.verbose = verbose
        self.progress_every = max(int(progress_every), 1)
        self.processed_count = 0
        self.downloaded_count = 0
        self.reused_count = 0
        self._known_files = {
            path.name
            for path in self.download_root.iterdir()
            if path.is_file() and path.stat().st_size > 0
        }
        if self.verbose:
            print(
                f"[ODK] Reusing {len(self._known_files)} existing files from {self.download_root}.",
                flush=True,
            )

    def attachment_api_url(self, project_id, form_id, instance_id, filename):
        return (
            f"{self.central_url}/v1/projects/{project_id}"
            f"/forms/{urllib.parse.quote(str(form_id), safe='')}"
            f"/submissions/{urllib.parse.quote(str(instance_id), safe='')}"
            f"/attachments/{urllib.parse.quote(str(filename), safe='')}"
        )

    def local_path(self, filename):
        return self.download_root / Path(str(filename)).name

    def _write_raw_bytes(self, content, target_path):
        temp_path = target_path.with_suffix(f"{target_path.suffix}.part")
        temp_path.write_bytes(content)
        temp_path.replace(target_path)

    def _report_progress(self, force=False):
        if self.verbose and (force or self.processed_count % self.progress_every == 0):
            print(
                "[ODK] Image progress: "
                f"processed={self.processed_count}, "
                f"downloaded={self.downloaded_count}, "
                f"reused={self.reused_count}",
                flush=True,
            )

    def _compress_and_write_image(self, content, target_path):
        suffix = target_path.suffix.lower()

        if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
            self._write_raw_bytes(content, target_path)
            return

        try:
            with Image.open(BytesIO(content)) as image:
                image = ImageOps.exif_transpose(image)
                save_kwargs = {}
                processed_image = image

                if suffix in {".jpg", ".jpeg"}:
                    if image.mode not in {"RGB", "L"}:
                        processed_image = image.convert("RGB")
                    save_kwargs = {
                        "format": "JPEG",
                        "quality": self.jpeg_quality,
                        "optimize": True,
                    }
                elif suffix == ".png":
                    if image.mode not in {"1", "L", "P", "RGB", "RGBA", "LA"}:
                        processed_image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
                    save_kwargs = {
                        "format": "PNG",
                        "optimize": True,
                        "compress_level": self.png_compress_level,
                    }
                else:
                    if image.mode not in {"RGB", "RGBA"}:
                        processed_image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
                    save_kwargs = {
                        "format": "WEBP",
                        "quality": self.webp_quality,
                        "method": 6,
                    }

                temp_path = target_path.with_suffix(f"{target_path.suffix}.part")
                processed_image.save(temp_path, **save_kwargs)
                temp_path.replace(target_path)
        except (OSError, ValueError, UnidentifiedImageError):
            self._write_raw_bytes(content, target_path)

    def download_attachment(self, project_id, form_id, instance_id, filename, table_name=None):
        target_path = self.local_path(filename)

        if (
            target_path.name in self._known_files
            and target_path.is_file()
            and target_path.stat().st_size > 0
        ):
            self.processed_count += 1
            self.reused_count += 1
            self._report_progress()
            return target_path.name

        if target_path.is_file() and target_path.stat().st_size > 0:
            self._known_files.add(target_path.name)
            self.processed_count += 1
            self.reused_count += 1
            self._report_progress()
            return target_path.name

        target_path.parent.mkdir(parents=True, exist_ok=True)

        r = self.session.get(
            self.attachment_api_url(project_id, form_id, instance_id, filename),
            timeout=self.timeout,
        )
        r.raise_for_status()
        self._compress_and_write_image(r.content, target_path)
        self._known_files.add(target_path.name)
        self.processed_count += 1
        self.downloaded_count += 1
        self._report_progress()
        return target_path.name


def add_geopoint_columns(df):
    result = df.copy()

    for column in list(result.columns):
        if result[column].apply(_as_geopoint).any():
            type_column = f"{column}.type"
            coords_column = f"{column}.coordinates"
            accuracy_column = f"{column}.properties.accuracy"

            if type_column not in result.columns:
                result[type_column] = result[column].apply(
                    lambda value: value.get("type") if _as_geopoint(value) else None
                )
            if coords_column not in result.columns:
                result[coords_column] = result[column].apply(
                    lambda value: value.get("coordinates") if _as_geopoint(value) else None
                )
            if accuracy_column not in result.columns:
                result[accuracy_column] = result[column].apply(
                    lambda value: (value.get("properties") or {}).get("accuracy")
                    if _as_geopoint(value)
                    else None
                )

    for coords_column in [column for column in result.columns if column.endswith(".coordinates")]:
        base_name = coords_column[: -len(".coordinates")]
        result[f"{base_name}.longitude"] = result[coords_column].apply(
            lambda value: _coord_at(value, 0)
        )
        result[f"{base_name}.latitude"] = result[coords_column].apply(
            lambda value: _coord_at(value, 1)
        )
        result[f"{base_name}.altitude"] = result[coords_column].apply(
            lambda value: _coord_at(value, 2)
        )

    return result


def serialize_nested_values(df):
    result = df.copy()
    for column in result.columns:
        if result[column].apply(lambda value: isinstance(value, (dict, list, tuple))).any():
            result[column] = result[column].apply(_json_serialize)
    return result


def build_attachment_url(central_url, project_id, form_id, instance_id, filename):
    return (
        f"{central_url.rstrip('/')}"
        f"/#/dl/projects/{project_id}"
        f"/forms/{urllib.parse.quote(str(form_id), safe='')}"
        f"/submissions/{urllib.parse.quote(str(instance_id), safe=':')}"
        f"/attachments/{urllib.parse.quote(str(filename), safe='')}"
    )


def find_image_columns(df):
    return [column for column in df.columns if df[column].apply(_looks_like_image_filename).any()]


def add_image_urls(
    df,
    central_url,
    project_id,
    form_id,
    table_name=None,
    image_downloader=None,
    instance_id_column="__id",
):
    result = df.copy()

    if instance_id_column not in result.columns:
        return result

    image_columns = find_image_columns(result)
    if not image_columns:
        return result

    download_group = table_name or form_id

    for column in image_columns:
        updated_values = []
        for value, instance_id in zip(result[column], result[instance_id_column]):
            if not _looks_like_image_filename(value) or pd.isna(instance_id):
                updated_values.append(value)
            elif image_downloader is not None:
                updated_values.append(
                    image_downloader.download_attachment(
                        project_id,
                        form_id,
                        instance_id,
                        value,
                        download_group,
                    )
                )
            else:
                updated_values.append(
                    build_attachment_url(central_url, project_id, form_id, instance_id, value)
                )
        result[column] = updated_values

    return result


def normalize_record_column(submissions_df, column_name, extra_columns=None):
    records = submissions_df[column_name].apply(lambda value: value if isinstance(value, dict) else {})
    normalized_df = pd.json_normalize(records)

    if extra_columns:
        for extra_column in extra_columns:
            normalized_df[extra_column] = submissions_df[extra_column].reset_index(drop=True)

    normalized_df = add_geopoint_columns(normalized_df)
    return serialize_nested_values(normalized_df)


def normalize_activity_begin(
    submissions_df,
    central_url=None,
    project_id=None,
    form_id=None,
    table_name=None,
    image_downloader=None,
):
    normalized_df = normalize_record_column(submissions_df, "activity_begin", extra_columns=["__id"])

    if central_url and project_id is not None and form_id:
        normalized_df = add_image_urls(
            normalized_df,
            central_url,
            project_id,
            form_id,
            table_name=table_name,
            image_downloader=image_downloader,
        )

    return normalized_df


def normalize_system(submissions_df):
    return normalize_record_column(submissions_df, "__system")


def find_geopoint_columns(df):
    suffixes = (
        ".type",
        ".coordinates",
        ".longitude",
        ".latitude",
        ".altitude",
        ".properties.accuracy",
    )
    return [column for column in df.columns if column.endswith(suffixes)]


def export_form_to_sql(
    central_url,
    email,
    password,
    project_id,
    form_id,
    engine,
    table_name,
    schema="dbo",
    submissions_table="Submissions",
    if_exists="replace",
    download_images=True,
    images_root="images",
    timeout=60,
    verbose=False,
):
    if verbose:
        print(
            f"[ODK] Starting export for table {table_name} from project {project_id} form {form_id}.",
            flush=True,
        )
    token = get_session_token(central_url, email, password, timeout=timeout)
    session = build_authenticated_session(token)
    dfs = fetch_all_form_data(
        central_url,
        email,
        password,
        project_id,
        form_id,
        timeout=timeout,
        token=token,
        session=session,
        verbose=verbose,
    )
    submissions_df = dfs[submissions_table]
    image_downloader = None
    if verbose:
        print(
            f"[ODK] Retrieved submissions table with {len(submissions_df)} rows.",
            flush=True,
        )

    if download_images:
        image_downloader = ODKImageDownloader(
            central_url,
            token,
            download_root=images_root,
            session=session,
            timeout=timeout,
            verbose=verbose,
        )
    elif verbose:
        print("[ODK] Image download disabled.", flush=True)

    if verbose:
        print("[ODK] Normalizing activity data.", flush=True)
    activity_df = normalize_activity_begin(
        submissions_df,
        central_url,
        project_id,
        form_id,
        table_name=table_name,
        image_downloader=image_downloader,
    )
    if verbose and image_downloader is not None:
        image_downloader._report_progress(force=True)
        print(
            "[ODK] Image processing complete: "
            f"processed={image_downloader.processed_count}, "
            f"downloaded={image_downloader.downloaded_count}, "
            f"reused={image_downloader.reused_count}",
            flush=True,
        )
    if verbose:
        print("[ODK] Normalizing system data.", flush=True)
    system_df = normalize_system(submissions_df)

    if verbose:
        print(f"[ODK] Writing {table_name} to SQL.", flush=True)
    activity_df.to_sql(table_name, schema=schema, con=engine, if_exists=if_exists, index=False)
    if verbose:
        print(f"[ODK] Writing {table_name}__system to SQL.", flush=True)
    system_df.to_sql(f"{table_name}__system", schema=schema, con=engine, if_exists=if_exists, index=False)
    if verbose:
        print(f"[ODK] Export complete for {table_name}.", flush=True)

    return {
        "dfs": dfs,
        "submissions_df": submissions_df,
        "activity_df": activity_df,
        "system_df": system_df,
    }
