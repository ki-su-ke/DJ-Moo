from django.db import models
from django.core.exceptions import ValidationError

from core.models import BaseModel


class ProductAssignee(BaseModel):
    """
    ProductとMembershipのアサイン関係を管理するモデル
    """
    
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="assignee_links",
    )
    """ Productモデルとのリレーション """
    
    membership = models.ForeignKey(
        "tenants.Membership",
        on_delete=models.CASCADE,
        related_name="product_links",
    )
    """ Membershipモデルとのリレーション """

    class Meta(BaseModel.Meta):
        db_table = "products_product_assignee"
        verbose_name = "Product Assignee"
        verbose_name_plural = "Product Assignees"
        constraints = [
            models.UniqueConstraint(
                fields=["product", "membership"],
                name="uniq_product_assignee",
            ),
        ]
        indexes = [
            models.Index(fields=["product", "membership"]),
            models.Index(fields=["membership"]),
        ]

    def clean(self):
        """
        clean() 内部でテナント境界のバリデーションチェックを行う
        """
        super().clean()

        if (self.product_id and self.membership_id
            and self.product.organization_id != self.membership.organization_id):
            raise ValidationError(
                    "Product and Membership must belong to the same organization."
                )
    
    def save(self, *args, **kwargs):
        """
        """
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.product} -> {self.membership}"
