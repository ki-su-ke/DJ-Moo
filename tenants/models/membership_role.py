from django.db import models
from django.core.exceptions import ValidationError

from core.models import BaseModel



class MembershipRole(BaseModel):
    """
    MembershipとRoleの中間テーブル

    Membership と Role の関係を MembershipRole で表し、
    この中間モデルで Membership と Role の Organization 一致を保証する。
    (テナント境界の厳守: Membership.organization == Role.organization)
    """
    
    membership = models.ForeignKey(
        "tenants.Membership",
        on_delete=models.CASCADE,
        related_name="role_links",
    )
    """ Membershipモデルとのリレーション """

    role = models.ForeignKey(
        "tenants.Role",
        on_delete=models.CASCADE,
        related_name="membership_links",
    )
    """ Roleモデルとのリレーション """

    class Meta(BaseModel.Meta):
        db_table = "tenants_membership_role"
        verbose_name = "Membership Role"
        verbose_name_plural = "Membership Roles"
        constraints = [
            models.UniqueConstraint(
                fields=["membership", "role"],
                name="uniq_membership_role",
            ),
        ]
        indexes = [
            models.Index(fields=["membership", "role"]),
            models.Index(fields=["role"]),
        ]
    
    def clean(self):
        """
        テナント境界の検証

        Djangoのclean()が呼ばれるタイミングでテナント境界の検証を行う
        具体的には、membershipとroleが同じorganizationに属しているかを検証する
        """
        super().clean()

        if (
            self.membership_id
            and self.role_id
            and self.membership.organization_id != self.role.organization_id
            ):
            raise ValidationError("Membership and Role must belong to the same organization.")

    def save(self, *args, **kwargs):
        """
        save()時に full_clean() を呼ぶことで、確実に clean() が呼ばれる
        """
        self.full_clean()
        return super().save(*args, **kwargs)
    
    def __str__(self) -> str:
        return f"{self.membership} -> {self.role}"
