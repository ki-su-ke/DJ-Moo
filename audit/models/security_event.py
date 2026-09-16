from django.conf import settings
from django.db import models

from core.models import BaseModel


class SecurityEventType(models.TextChoices):
    TENANT_ESCAPE = "tenant_escape", "テナント境界違反試行"
    PERMISSION_DENIED = "permission_denied", "権限不足アクセス試行"
    DELETED_DATA_ACCESS = "deleted_data_access", "論理削除済みデータアクセス試行"


class SecurityEvent(BaseModel):
    """
    セキュリティイベントログ

    テナント境界違反、権限不足アクセス、論理削除済みデータアクセスなどのセキュリティ関連のイベントを記録する
    
    今回は特に「テナント境界違反」に絞って利用していく
    """
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="security_events",
    )
    """ どのユーザーか """

    audit_user_id = models.UUIDField(editable=False, blank=True, null=True)
    """ 監査用: 削除後も追跡可能なID """

    audit_user_email = models.EmailField(blank=True)
    """ 監査用: 削除後も追跡・特定可能なようにemailも保持しておく """

    ip_address = models.GenericIPAddressField(blank=True, null=True)
    """ 該当ユーザーの IP Address """

    event_type = models.CharField(
        max_length=50,
        choices=SecurityEventType.choices,
    )
    """ イベントタイプ SecurityEventTypeで定義された値をとる """

    attempted_organization_slug = models.SlugField(max_length=100, blank=True)
    """ テナント境界越えを試行した、対象となるテナントスラッグ """

    target_resource = models.CharField(max_length=100, blank=True)
    """ 対象となるリソース """

    target_resource_id = models.CharField(max_length=100, blank=True)
    """ 対象となるリソースID """

    user_agent = models.TextField(blank=True)
    """ ユーザーエージェント """

    remarks = models.TextField(blank=True, help_text="追記事項、補足説明、判定理由など")
    """ 追記・特記事項、補足説明など必要があれば 自由入力枠 """

    '''
    このモデルはテーマを絞ったセキュリティ監視ログ用のモデルとして利用するものなので、
    ・履歴として使えるように単純にリレーションを組まない(対象リソースなどが削除されても追跡可能な情報を残す)
    ・User情報に関しては、利便性と誤認防止の観点から、リレーションしたフィールドと履歴用フィールドを両方残す
    ようにした
    '''

    class Meta(BaseModel.Meta):
        db_table = "audit_security_event"
        verbose_name = "Security Event"
        verbose_name_plural = "Security Events"
        indexes = [
            models.Index(fields=["audit_user_email"]),
            models.Index(fields=["user", "event_type", "created_at"]),
            models.Index(fields=["ip_address", "event_type", "created_at"]),
            models.Index(fields=["attempted_organization_slug", "created_at"]),
        ]

    def save(self, *args, **kwargs):
        if self.user:
            self.audit_user_id = self.user.id
            self.audit_user_email = self.user.email
        super().save(*args, **kwargs)
    
    def __str__(self) -> str:
        return f"{self.event_type} @ {self.attempted_organization_slug}"
