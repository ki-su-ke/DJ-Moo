from django.core.exceptions import ValidationError
from django.db import transaction
from django.db import IntegrityError
from typing import Dict, Tuple

from django.contrib.auth import get_user_model

from tenants.models import Organization, Permission, Role

import logging

logger = logging.getLogger(__name__)

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
                logger.error("All permissions must be Permission instances.")
                raise ValidationError("不正なPermissionが渡されました。")
        
        try:
            role = Role.objects.create(organization=organization, name=name)
            role.permissions.set(permissions)
            return role
        except IntegrityError as e:
            logger.error(f"Failed to create Role: {str(e)}", exc_info=True)
            raise ValidationError("Roleの作成に失敗しました。")
        except Exception as e:
            logger.error(f"Unexpected error occurred: {str(e)}", exc_info=True)
            raise ValidationError(f"予期しないエラーです。")

    
    @staticmethod
    @transaction.atomic
    def update_role_permissions(*, role: Role, permissions: list[Permission]) -> Role:
        """
        Roleを更新する

        キーワード引数強制： update_role_permissions(role=role, permissions=perms_list)
        """
        for permission in permissions:
            if not isinstance(permission, Permission):
                logger.error("All permissions must be Permission instances.")
                raise ValidationError("不正なPermissionが渡されました。")
        
        try:
            role.permissions.set(permissions)
            return role
        except IntegrityError as e:
            logger.error(f"Failed to update Role: {str(e)}", exc_info=True)
            raise ValidationError(f"Roleの更新に失敗しました。")
        except Exception as e:
            logger.error(f"Unexpected error occurred: {str(e)}", exc_info=True)
            raise ValidationError("予期せぬエラーです。")
    
    @staticmethod
    @transaction.atomic
    def rename_role(*, role: Role, name: str) -> Role:
        """
        Role名変更

        キーワード引数強制： rename_role(role=role, name=name)
        """
        try:
            role.name = name
            role.save(update_fields=["name", "updated_at"])
            return role
        except IntegrityError as e:
            logger.error(f"Failed to rename Role: {str(e)}", exc_info=True)
            raise ValidationError(f"Roleのrenameに失敗しました。")
        except Exception as e:
            logger.error(f"Unexpected error occurred: {str(e)}", exc_info=True)
            raise ValidationError(f"予期せぬエラーです。")
    
    @staticmethod
    @transaction.atomic
    def delete_role(*, role: Role):
        """
        Role の削除

        キーワード引数強制: delete_role(role=role)
        """
        try:
            role.delete()
        except IntegrityError as e:
            logger.error(f"Failed to delete Role: {str(e)}", exc_info=True)
            raise ValidationError(f"Roleの削除に失敗しました。")
        except Exception as e:
            logger.error(f"Unexpected error occurred: {str(e)}", exc_info=True)
            raise ValidationError("予期せぬエラーです。")
