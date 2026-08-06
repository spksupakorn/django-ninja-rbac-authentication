"""Persistent audit records."""

from __future__ import annotations

from django.db import models


class AuditLog(models.Model):
    """An immutable record of a security event or administrative mutation."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    action = models.CharField(max_length=64)
    actor_id = models.BigIntegerField(null=True, blank=True)
    actor_email = models.EmailField(null=True, blank=True)
    target_type = models.CharField(max_length=64, null=True, blank=True)
    target_id = models.CharField(max_length=255, null=True, blank=True)
    outcome = models.CharField(max_length=16, default="success")
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=512, null=True, blank=True)
    metadata = models.JSONField(default=dict)

    class Meta:
        indexes = [
            models.Index(fields=["actor_id", "created_at"], name="audit_actor_created_idx"),
            models.Index(fields=["action", "created_at"], name="audit_action_created_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.action} ({self.outcome}) at {self.created_at:%Y-%m-%d %H:%M:%S}"
