from django.db import models
from core.models import BaseModel


class Permission(BaseModel):
    """
    システム共通の Permission マスタ。

    例:
        resource = "product"
        action = "view"
    => codename = "product.view"
    """
    
    resource = models.CharField(max_length=100)
    """ どのリソースに対するPermissionか 例）'product' """

    action = models.CharField(max_length=100)
    """
    どのアクションに対するPermissionか
    例）'view', 'create', 'update', 'delete', 'view_deleted', 'restore' など
    """

    name = models.CharField(max_length=255)
    """ Permission の名前 """

    class Meta(BaseModel.Meta):
        db_table = "tenants_permissions"
        verbose_name = "Permission"
        verbose_name_plural = "Permissions"
        constraints = [
            models.UniqueConstraint(
                fields=["resource", "action"],
                name="uniq_permission_resource_action",
            ),
        ]
        indexes = [
            models.Index(fields=["resource", "action"]),
            models.Index(fields=["resource"]),
        ]

    @property
    def codename(self) -> str:
        return f"{self.resource}.{self.action}"
    
    def __str__(self) -> str:
        return self.codename
