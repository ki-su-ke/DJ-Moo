import logging

from accounts.models import User
from audit.models import SecurityEvent, SecurityEventType
from rest_framework.request import Request


logger = logging.getLogger(__name__)


class AuditService:
    """Request context を含むセキュリティイベントを記録する。"""

    @staticmethod
    def record_security_event(
        *,
        request: Request,
        user: User,
        event_type: SecurityEventType,
        attempted_organization_slug: str,
        target_resource: str,
        target_resource_id: str,
        remarks: str,
    ) -> None:
        """拒否済み要求の actor・対象・接続情報を監査ログへ保存する。"""
        try:
            SecurityEvent.objects.create(
                user=user,
                event_type=event_type,
                attempted_organization_slug=attempted_organization_slug,
                target_resource=target_resource,
                target_resource_id=target_resource_id,
                ip_address=request.META.get("REMOTE_ADDR") or None,
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
                remarks=remarks,
            )
        except Exception:
            logger.exception(
                "Failed to record security event %s for %s",
                event_type,
                target_resource_id,
            )