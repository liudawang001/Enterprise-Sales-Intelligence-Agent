from typing import ClassVar

from pydantic import BaseModel, Field


class Region(BaseModel):
    name: str
    adcode: str | None = None
    provider_codes: dict[str, str] = Field(default_factory=dict)


class RegionResolver:
    _KNOWN: ClassVar[dict[str, Region]] = {
        "上海松江": Region(name="上海松江", adcode="310117"),
        "松江": Region(name="上海松江", adcode="310117"),
        "上海浦东": Region(name="上海浦东", adcode="310115"),
        "浦东": Region(name="上海浦东", adcode="310115"),
    }

    def resolve(self, value: str) -> Region:
        normalized = value.strip().replace("区", "")
        return self._KNOWN.get(normalized, Region(name=value.strip()))
