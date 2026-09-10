from pathlib import Path


class LocalFileStorage:
    def __init__(self, root: str = "data/uploads") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    async def save(self, filename: str, content: bytes, *, file_hash: str) -> str:
        safe_name = Path(filename).name
        target = self.root / f"{file_hash[:16]}-{safe_name}"
        target.write_bytes(content)
        return str(target)

    async def delete(self, path: str) -> None:
        target = Path(path)
        if target.exists():
            target.unlink()
