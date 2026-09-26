from django.conf import settings
from django.db import models, transaction
from django.core.exceptions import ValidationError

from safedelete.models import SOFT_DELETE, SafeDeleteModel

from core.models import BaseModel
from tenants.models.permission import Permission


class MembershipScope(models.TextChoices):
    """ Membership Model で利用するScopeの定義 """
    ALL = "all", "All"
    ASSIGNED = "assigned", "Assigned"
    

class Membership(SafeDeleteModel, BaseModel):
    """
    Membership Model
    User は Membership に所属し、Membership は Organization に所属する。
    Membership は MembershipRole を通して Role と紐付き、Role が保持している Permission と紐付く。

    すなわち、「User と Organization の所属関係」、「権限付与の主体は User ではなく Membership」
    という関係を表す中間テーブルとして。
    """

    _safedelete_policy = SOFT_DELETE

    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    """ このMembershipに所属するUser """

    organization = models.ForeignKey(
        "tenants.Organization",
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    """ このMembershipが所属するOrganization """

    roles = models.ManyToManyField(
        "tenants.Role",
        through="tenants.MembershipRole",
        related_name="memberships",
        blank=True,
    )
    """ このMembershipに付与されたRole """

    scope_type = models.CharField(
        max_length=50,
        choices=MembershipScope.choices,
        default=MembershipScope.ASSIGNED,
    )
    """ このMembershipのスコープタイプ """

    is_org_admin = models.BooleanField(default=False)
    """
    このMembershipが所属しているOrganizationの組織管理者かどうか  

    is_org_admin=True は以下の操作を許可する。これは Permission 体系とは別の独立したフラグとする。
    - Membership の招待・削除
    - Organization 設定の変更
    - Role の作成・編集・削除  

    Organization 内の `is_org_admin=True` の Membership は必ず1人以上存在することを強制する。
    最後の1人を削除・無効化しようとした場合はエラーとする。  

    is_org_admin フラグについては、以下の三層による保護とする。
    - clean()
    - delete() / 論理削除時保護
    - service / serializer / admin 側保護  

    モデル側は「最後の砦」として、clean() / delete() で保護する。
    """

    is_active = models.BooleanField(
        default=True,
        help_text=(
            "所属の一時停止用フラグ。"
            "論理削除とは別に、将来的な休止・承認待ち・一時無効化などの"
            "運用を想定して保持する。"
        ),
    )
    """ このMembershipがアクティブかどうかを表すフラグ """

    class Meta(BaseModel.Meta):
        db_table = "tenants_membership"
        verbose_name = "Membership"
        verbose_name_plural = "Memberships"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "organization"],
                name="uniq_membership_user_organization",
            ),
        ]
        indexes = [
            models.Index(fields=["organization", "user"]),
            models.Index(fields=["organization", "is_org_admin"]),
            models.Index(fields=["organization", "is_active"]),
        ]
    
    def __str__(self) -> str:
        return f"{self.user}@{self.organization.slug}"

    def clean(self):
        super().clean()
        self._validate_last_org_admin_on_update()

    def _validate_last_org_admin_on_update(self):
        """
        Membership.is_org_admin がOrganization単位で0になってしまうことを防ぐ。

        三層保護の一部としてのモデル側保護。
        本命は service / serializer / admin 側だが、
        モデル単体でも最後の組織管理者を外す更新を最低限防ぐ。
        """
        if not self.pk:
            return
        
        old = Membership.all_objects.filter(pk=self.pk).first()
        if old is None:
            return
        
        if old.is_org_admin and not self.is_org_admin:
            remaining_admins = Membership.objects.filter(
                organization_id=self.organization_id,
                is_org_admin=True,
                is_active=True,
            ).exclude(pk=self.pk)

            if not remaining_admins.exists():
                raise ValidationError("At least one active organization admin is required.")
    
    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    @transaction.atomic
    def delete(self, force_policy=None, **kwargs):
        if self.is_org_admin and self.is_active:
            remaining_admins = Membership.objects.filter(
                organization_id=self.organization_id,
                is_org_admin=True,
                is_active=True,
            ).exclude(pk=self.pk)

            if not remaining_admins.exists():
                raise ValidationError("The last active organization admin cannot be deleted.")

        return super().delete(force_policy=force_policy, **kwargs)
    
    @property
    def effective_permissions(self):
        """
        このMembershipが実際に持っているすべてのPermissionを取得する
        """
        return (
            Permission.objects.filter(
                roles__membership_links__membership=self,
                roles__deleted__isnull=True,
            ).distinct()
        )
