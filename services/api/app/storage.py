from pathlib import Path

from app.config import get_settings


class LocalPrivateStorage:
    def __init__(self, root: str | Path | None = None):
        configured_root = root or get_settings().material_storage_root
        self.root = Path(configured_root).resolve()

    def write(self, storage_key: str, content: bytes) -> None:
        path = self._safe_path(storage_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def read(self, storage_key: str) -> bytes:
        return self._safe_path(storage_key).read_bytes()

    def _safe_path(self, storage_key: str) -> Path:
        path = (self.root / storage_key).resolve()
        if path != self.root and self.root not in path.parents:
            raise ValueError("Invalid storage key")
        return path
