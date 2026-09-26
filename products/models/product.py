from django.db import models
from django.core.exceptions import ValidationError
from safedelete.models import SOFT_DELETE, SafeDeleteModel

from core.models import BaseModel
from tenants.models.membership import MembershipScope


class ProductStatus(models.TextChoices):
    """ Product.status に使用するTextChoices """
    DRAFT = "draft", "Draft"
    ACTIVE = "active", "Active"
    ARCHIVED = "archived", "Archived"


class ProductQuerySet(models.QuerySet):
    """
    Productにテナント境界やScopeを適用するためのQuerySet
    """

    def for_membership(self, membership):
        """
        渡されたMembershipに対応するProductを返す。
        テナント境界とScopeを適用する。
        superuserである場合のみテナント境界を無視して取得する。

        Args:
            membership: 対象のMembership
            
        Returns:
            ProductQuerySet: テナント境界とScopeを適用したQuerySet
        """
        qs = self.filter(organization=membership.organization)

        if membership.user.is_superuser:
            return qs

        if membership.scope_type == MembershipScope.ASSIGNED:
            qs = qs.filter(assignee_links__membership=membership)

        return qs.distinct()


class Product(SafeDeleteModel, BaseModel):
    """
    Organization 配下の業務データ。
    """
    
    _safedelete_policy = SOFT_DELETE

    organization = models.ForeignKey(
        "tenants.Organization",
        on_delete=models.CASCADE,
        related_name="products",
    )
    """ Organizationとのリレーション """

    name = models.CharField(max_length=255)
    """ Product名 """

    description = models.TextField(blank=True)
    """ description """

    status = models.CharField(
        max_length=50,
        choices=ProductStatus.choices,
        default=ProductStatus.DRAFT,
    )
    """ Productの状態 ProductStatusに定義された値を利用する """

    is_active = models.BooleanField(
        default=True,
        help_text=(
            "運用上の利用可否フラグ。"
            "status が業務状態を表すのに対し、"
            "こちらは将来的な一時停止・公開停止などの用途を想定する。"
        ),
    )
    """ 運用上のProduct利用可否フラグ """

    assignees = models.ManyToManyField(
        "tenants.Membership",
        through="products.ProductAssignee",
        related_name="assigned_products",
        blank=True,
    )
    """
    Productの担当者

    1Productに1担当者なんてことはないと思うのでManyToManyによる管理とする
    但し担当者とはいうけれど、Membershipによる管理とする
    """

    created_by = models.ForeignKey(
        "tenants.Membership",
        on_delete=models.PROTECT,
        related_name="created_products",
    )
    """
    Productの作成者(Membership)

    Productを削除したとはいえMembershipを削除するわけにはいかないのでon_deleteはPROTECT
    """

    objects = ProductQuerySet.as_manager()

    class Meta(BaseModel.Meta):
        db_table = "products_product"
        indexes = [
            models.Index(fields=["organization"]),
            models.Index(fields=["organization", "created_at"]),
            models.Index(fields=["organization", "name"]),
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["organization", "is_active"]),
        ]
        #
        # !! 予防的Index ということで、残すかどうかは後で検討しよう

    def __str__(self) -> str:
        return self.name
    
    def clean(self):
        """
        clean() 同一テナントで作られたProductなのかのチェックも行う
        """
        super().clean()

        if self.created_by_id and self.organization_id:
            if self.created_by.organization_id != self.organization_id:
                raise ValidationError({
                    "created_by": "created_by must belong to the same organization."
                })

    def save(self, *args, **kwargs):
        """
        save()のオーバーライド

        内部でclean()を呼び出してテナント境界のバリデーションチェック、
        新規作成データならProductAssigneeの作成も行う
        """
        is_create = self._state.adding
        self.full_clean()
        super().save(*args, **kwargs)
        #
        # 新規作成ならばProductAssigneeをセット
        if is_create and self.created_by.scope_type == MembershipScope.ASSIGNED:
            from products.models.product_assignee import ProductAssignee

            ProductAssignee.objects.get_or_create(
                product=self,
                membership=self.created_by,
            )

