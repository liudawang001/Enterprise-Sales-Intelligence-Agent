from app.entities.normalizer import (
    AddressNormalizer,
    EnterpriseNameNormalizer,
    PhoneNormalizer,
    WebsiteNormalizer,
)


class EvidenceNormalizer:
    def __init__(self) -> None:
        self.names = EnterpriseNameNormalizer()
        self.addresses = AddressNormalizer()
        self.phones = PhoneNormalizer()
        self.websites = WebsiteNormalizer()

    def normalize(self, field_name: str, value):
        if value is None:
            return None
        if field_name == "legal_name":
            return self.names.normalize(str(value)).normalized
        if field_name in {"address", "registered_address", "office_location"}:
            return self.addresses.normalize(str(value))
        if field_name == "public_phone":
            return self.phones.normalize(str(value))
        if field_name == "website":
            return self.websites.normalize(str(value))
        if isinstance(value, str):
            return value.strip().lower()
        return value
