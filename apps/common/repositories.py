"""Async primitives shared by repositories that access Django ORM models."""

from __future__ import annotations

from typing import Any

from django.db import models


class BaseRepository[ModelType: models.Model]:
    """Common async ORM operations for a single model type."""

    def __init__(self, model: type[ModelType]) -> None:
        self.model = model

    async def aget_or_none(self, **filters: Any) -> ModelType | None:
        """Return a model matching filters, or ``None`` when it does not exist."""
        try:
            return await self.model.objects.aget(**filters)
        except self.model.DoesNotExist:
            return None

    async def acreate(self, **fields: Any) -> ModelType:
        """Create and persist a model using Django's async ORM API."""
        return await self.model.objects.acreate(**fields)
