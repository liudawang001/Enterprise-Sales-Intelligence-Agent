from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlparse

from app.entities.models import NormalizedEnterpriseName


def _nfkc(value: str) -> str:
    return unicodedata.normalize("NFKC", value or "").strip()


class EnterpriseNameNormalizer:
    LEGAL_SUFFIXES = ("股份有限公司", "有限责任公司", "有限公司", "集团公司", "集团")
    BRANCH_MARKERS = ("分公司", "分厂", "分行", "支行")
    OFFICE_MARKERS = ("办事处", "研发中心", "运营中心", "办公点")
    LOCATION_RE = re.compile(
        r"(?:上海|北京|天津|重庆|广州|深圳|杭州|南京|苏州|成都|武汉|西安|浦东|松江)(?:市|区)?"
    )

    def normalize(self, value: str) -> NormalizedEnterpriseName:
        original = _nfkc(value)
        compact = re.sub(r"[\s·,，。()（）\[\]【】]+", "", original).lower()
        branch = next((v for v in self.BRANCH_MARKERS if v in compact), None)
        office = next((v for v in self.OFFICE_MARKERS if v in compact), None)
        suffix = next((v for v in self.LEGAL_SUFFIXES if v in compact), None)
        location_match = self.LOCATION_RE.search(compact)
        base = compact
        for marker in (*self.BRANCH_MARKERS, *self.OFFICE_MARKERS):
            base = base.replace(marker, "")
        location = location_match.group(0) if location_match else None
        if suffix:
            base = base.replace(suffix, "")
        base = self.LOCATION_RE.sub("", base)
        return NormalizedEnterpriseName(
            original=original,
            normalized=compact,
            base_name=base,
            legal_suffix=suffix,
            branch_marker=branch,
            office_marker=office,
            location_marker=location,
        )


class LegalSuffixParser:
    def parse(self, value: str) -> str | None:
        return EnterpriseNameNormalizer().normalize(value).legal_suffix


class AddressNormalizer:
    def normalize(self, value: str | None) -> str | None:
        if not value:
            return None
        value = _nfkc(value).lower()
        value = re.sub(r"[\s,，。]+", "", value).replace("中华人民共和国", "")
        return re.sub(r"(上海市){2,}", "上海市", value)


class PhoneNormalizer:
    def normalize(self, value: str | None) -> str | None:
        if not value:
            return None
        value = _nfkc(value).lower()
        extension = re.search(r"(?:转|分机|ext\.?)[\s:-]*(\d+)", value)
        main = re.split(r"(?:转|分机|ext\.?)", value)[0]
        digits = re.sub(r"\D", "", main)
        if digits.startswith("0086"):
            digits = digits[4:]
        elif digits.startswith("86") and len(digits) > 11:
            digits = digits[2:]
        return f"{digits}x{extension.group(1)}" if extension else digits or None


class WebsiteNormalizer:
    def normalize(self, value: str | None) -> str | None:
        if not value:
            return None
        candidate = _nfkc(value).lower()
        parsed = urlparse(candidate if "://" in candidate else f"https://{candidate}")
        host = (parsed.hostname or "").rstrip(".")
        return host[4:] if host.startswith("www.") else host or None
