"""File storage abstraction — local filesystem or S3-compatible object storage.

Phase 2: report PDFs (the durable artifact that must survive container
restarts) are written through this layer. The driver is selected by
STORAGE_BACKEND:

- "local" (default): files under LOCAL_UPLOAD_DIR, served by the existing
  /uploads static mount. Zero dependencies, works on every free tier.
- "s3": any S3-compatible API — AWS S3, Cloudflare R2 (10 GB free tier),
  Backblaze B2, MinIO — via the standard boto3 client configured with a
  custom endpoint URL. Only the R2 account id / access key / secret change;
  no code difference between providers.

Selection is env-driven (Rule 5 of the project brief); nothing is hardcoded.
"""

import os
from typing import Optional, Protocol


class StorageDriver(Protocol):
    """Contract every storage backend fulfils."""

    def save(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        """Persist bytes under key; returns a public-ish identifier (URL or path)."""
        ...

    def open_bytes(self, identifier: str) -> bytes:
        """Read back the bytes stored under identifier."""
        ...

    def exists(self, identifier: str) -> bool:
        ...


class LocalDriver:
    """Filesystem driver rooted at LOCAL_UPLOAD_DIR (default backend/uploads)."""

    def __init__(self, root: str):
        self.root = os.path.abspath(root)
        os.makedirs(self.root, exist_ok=True)

    def _resolve(self, key: str) -> str:
        # Keys are joined safely: absolute paths and ../ are neutralized by
        # anchoring to the root directory.
        path = os.path.abspath(os.path.join(self.root, key.lstrip("/\\")))
        if not path.startswith(self.root + os.sep) and path != self.root:
            raise ValueError(f"Invalid storage key: {key!r}")
        return path

    def save(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        path = self._resolve(key)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        return path

    def open_bytes(self, identifier: str) -> bytes:
        with open(self._resolve(identifier), "rb") as f:
            return f.read()

    def exists(self, identifier: str) -> bool:
        return os.path.exists(self._resolve(identifier))


class S3Driver:
    """S3-compatible driver (AWS S3 / Cloudflare R2 / Backblaze B2 / MinIO).

    Uses boto3 with explicit endpoint_url so the SAME driver talks to R2's
    S3-compatible API. Credentials come exclusively from env vars — never
    hardcoded (Rule 5 of the project brief).
    """

    def __init__(self, bucket: str, endpoint_url: Optional[str] = None):
        import boto3  # deferred: only imported when the s3 driver is selected
        from botocore.config import Config

        self.bucket = bucket
        self.endpoint_url = endpoint_url or None
        self._client = boto3.client(
            "s3",
            endpoint_url=self.endpoint_url,
            aws_access_key_id=os.environ.get("S3_ACCESS_KEY_ID", ""),
            aws_secret_access_key=os.environ.get("S3_SECRET_ACCESS_KEY", ""),
            region_name=os.environ.get("S3_REGION", "auto"),
            config=Config(signature_version="s3v4"),
        )

    def save(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        self._client.put_object(
            Bucket=self.bucket, Key=key, Body=data, ContentType=content_type
        )
        if self.endpoint_url:
            # R2-style public URL: <endpoint>/<bucket>/<key>
            return f"{self.endpoint_url.rstrip('/')}/{self.bucket}/{key}"
        return f"s3://{self.bucket}/{key}"

    def open_bytes(self, identifier: str) -> bytes:
        key = self._key_from_identifier(identifier)
        resp = self._client.get_object(Bucket=self.bucket, Key=key)
        return resp["Body"].read()

    def exists(self, identifier: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self._client.head_object(Bucket=self.bucket, Key=self._key_from_identifier(identifier))
            return True
        except ClientError:
            return False

    def _key_from_identifier(self, identifier: str) -> str:
        if identifier.startswith(f"s3://{self.bucket}/"):
            return identifier[len(f"s3://{self.bucket}/"):]
        if self.endpoint_url and identifier.startswith(self.endpoint_url):
            return identifier[len(self.endpoint_url):].lstrip("/").split("/", 1)[-1]
        return identifier.lstrip("/\\")


_driver: Optional[StorageDriver] = None


def get_storage() -> StorageDriver:
    """Singleton driver chosen by STORAGE_BACKEND (local | s3)."""
    global _driver
    if _driver is not None:
        return _driver
    from app.config import settings

    backend = (settings.STORAGE_BACKEND or "local").strip().lower()
    if backend == "s3":
        bucket = os.environ.get("S3_BUCKET") or settings.SUPABASE_BUCKET
        _driver = S3Driver(
            bucket=bucket,
            endpoint_url=os.environ.get("S3_ENDPOINT_URL") or None,
        )
    else:
        backend_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        root = settings.LOCAL_UPLOAD_DIR
        if not os.path.isabs(root):
            root = os.path.join(backend_root, root)
        _driver = LocalDriver(root)
    return _driver


def reset_storage() -> None:
    """Testing hook: clear the cached driver so env changes take effect."""
    global _driver
    _driver = None
