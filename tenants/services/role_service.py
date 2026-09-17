from django.core.exceptions import ValidationError
from django.db import transaction
from django.db import IntegrityError
from typing import Dict, Tuple

from django.contrib.auth import get_user_model

from tenants.models import Organization, Permission, Role


User = get_user_model()


class RoleService:
    """
    """
    @staticmethod
    @transaction.atomic
    def create_role(*, organization: Organization, name: str, permissions: list[Permission]) -> Role:
        """
        Roleを作成する

        キーワード引数強制： create_role(organization=org, name=name, permissions=perms_list)
        """
        for permission in permissions:
            if not isinstance(permission, Permission):
                raise ValidationError("All permissions must be Permission instances.") from e
'''
    @staticmethod
    @transaction.atomic
    def create_role(*, organization: Organization, name: str, permissions: list[Permission]) -> Role:
        for permission in permissions:
            if not isinstance(permission, Permission):
                raise ValidationError("All permissions must be Permission instances.")

        role = Role.objects.create(
            organization=organization,
            name=name,
        )
        role.permissions.set(permissions)
        return role

    @staticmethod
    @transaction.atomic
    def update_role_permissions(*, role: Role, permissions: list[Permission]) -> Role:
        for permission in permissions:
            if not isinstance(permission, Permission):
                raise ValidationError("All permissions must be Permission instances.")

        role.permissions.set(permissions)
        return role

    @staticmethod
    @transaction.atomic
    def rename_role(*, role: Role, name: str) -> Role:
        role.name = name
        role.save(update_fields=["name", "updated_at"])
        return role

    @staticmethod
    @transaction.atomic
    def delete_role(*, role: Role):
        role.delete()
'''