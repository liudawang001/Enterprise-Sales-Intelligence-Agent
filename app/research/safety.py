from __future__ import annotations

import ipaddress
import re
import socket
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True)
class UrlSafetyVerdict:
    allowed: bool
    reason: str = ""


class UrlSafetyValidator:
    async def validate(self, url: str) -> UrlSafetyVerdict:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return UrlSafetyVerdict(False, "Only public HTTP(S) URLs are allowed")
        if parsed.hostname.lower() == "localhost":
            return UrlSafetyVerdict(False, "Local hosts are blocked")
        try:
            addresses = {
                item[4][0]
                for item in socket.getaddrinfo(parsed.hostname, parsed.port or 443)
            }
        except socket.gaierror:
            return UrlSafetyVerdict(False, "Host cannot be resolved")
        for address in addresses:
            ip = ipaddress.ip_address(address)
            if not ip.is_global:
                return UrlSafetyVerdict(
                    False,
                    "Private, loopback, link-local and reserved addresses are blocked",
                )
        return UrlSafetyVerdict(True)

    async def validate_redirects(self, urls: list[str]) -> UrlSafetyVerdict:
        for url in urls:
            verdict = await self.validate(url)
            if not verdict.allowed:
                return verdict
        return UrlSafetyVerdict(True)


def filter_public_contacts(text: str) -> tuple[list[str], list[str]]:
    phones = re.findall(r"(?<!\d)(?:0\d{2,3}-?\d{7,8}|400-?\d{3}-?\d{4})(?!\d)", text)
    emails = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
    personal_domains = {
        "gmail.com",
        "qq.com",
        "163.com",
        "126.com",
        "outlook.com",
        "hotmail.com",
    }
    emails = [
        value
        for value in emails
        if value.rsplit("@", 1)[-1].lower() not in personal_domains
    ]
    return list(dict.fromkeys(phones)), list(dict.fromkeys(emails))
