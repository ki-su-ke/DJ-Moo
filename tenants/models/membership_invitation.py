import uuid
from datetime import timedelta
from django.db import models
from django.utils import timezone
from safedelete.models import SOFT_DELETE, SafeDeleteModel

from core.models import BaseModel


class InvitationStatus(models.TextChoices):
    """ Membership招待モデルに使用する、statusの定義 """
    PENDING = "pending", "Pending"
    ACCEPTED = "accepted", "Accepted"
    DECLINED = "declined", "Declined"
    EXPIRED = "expired", "Expired"


class MembershipInvitation(SafeDeleteModel, BaseModel):
    """
    メンバーシップ招待モデル

    権限のあるアカウントから、招待したいユーザーのメールアドレスを登録し、
    そのユーザーに招待メールを送信する操作に使用するモデルクラス
    """
    _safedelete_policy = SOFT_DELETE

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(verbose_name="招待先メールアドレス")
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, verbose_name="招待トークン")

    organization = models.ForeignKey(
        "tenants.Organization",
        on_delete=models.CASCADE,
        related_name="Invitations",
        verbose_name="組織"
    )

    role = models.ForeignKey(
        "tenants.Role",
        on_delete=models.CASCADE,
        related_name="invitations",
        verbose_name="権限"
    )

    invited_by = models.ForeignKey(
        "tenants.Membership",
        on_delete=models.CASCADE,
        related_name="sent_invitations",
        verbose_name="招待者"
    )

    status = models.CharField(
        max_length=50,
        choices=InvitationStatus.choices,
        default=InvitationStatus.PENDING,
        verbose_name="ステータス"
    )

    expires_at = models.DateTimeField(verbose_name="有効期限")

    class Meta(BaseModel.Meta):
        db_table = "tenants_membership_invitation"
        verbose_name = "Membership Invitation"
        verbose_name_plural = "Membership Invitations"
        indexes = [
            models.Index(fields=["token"]),
            models.Index(fields=["email", "status"]),
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["expires_at"]),
        ]

    def __str__(self):
        return f"{self.email} -> {self.organization.name} ({self.status})"

    def is_valid(self):
        """ 招待が有効かどうかを確認 """
        return (
            self.status == InvitationStatus.PENDING and
            self.expires_at > timezone.now()
        )

    def is_expired(self):
        """ 招待が期限切れかどうかを確認 """
        return self.expires_at < timezone.now()
    
    def save(self, *args, **kwargs):
        #
        # 保存時にexpires_atが設定されていない場合は7日後に設定
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)
