from django.db import models
from safedelete.models import SOFT_DELETE, SafeDeleteModel

from core.models import BaseModel


class Role(BaseModel, SafeDeleteModel):
    """
    Organization ごとの Role。

    1つの Role は複数の Permission を持つ。
    """

    _safedelete_policy = SOFT_DELETE

    name = models.CharField(max_length=100, db_index=True)
    """ Role名 """

    organization = models.ForeignKey(
        "tenants.Organization",
        on_delete=models.CASCADE,
        related_name="roles",
    )
    """
    tenants.Organizationとのリレーション
    """

    permissions = models.ManyToManyField(
        "tenants.Permission",
        related_name="roles",
        blank=True,
    )

    class Meta(BaseModel.Meta):
        db_table = "tenants_roles"
        constraints = [
            models.UniqueConstraint(
                fields=["organization", "name"],
                name="uniq_active_role_name_per_organization",
            ),
        ]
    
    def __str__(self) -> str:
        return f"{self.organization.slug}: {self.name}"
