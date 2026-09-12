"""The delivery projection is implemented by DeliveryQueryService.

This module keeps the architectural boundary explicit for callers that should
depend on a shared projection rather than repository-specific field selection.
"""

from app.delivery.queries import DeliveryQueryService

__all__ = ["DeliveryQueryService"]
