from django.core.exceptions import ValidationError
from django.db import transaction
from django.db import IntegrityError
from typing import Dict, Tuple

from django.contrib.auth import get_user_model

from tenants.constants import PermissionKey, RoleDefaultName, DEFAULT_ROLE_PERMISSION_KEYS
from tenants.models import (
    Membership, MembershipRole, MembershipScope,
    Organization, Permission, Role
)


User = get_user_model()


class OrganizationService:
    """
    Organizationに関連するロジックを扱うサービスクラス

    Organization 作成時に

    - Organization 作成  
    - デフォルト Role 作成  
    - 作成者 Membership 作成  
    - 作成者に Admin Role 付与  
    - その結果として is_org_admin=True  
    """
    
    @staticmethod
    def _get_permissions_map() -> Dict[Tuple[str, str], Permission]:
        """
        Permission.resource と Permission.action のタプルをキー、
        Permissionインスタンスを値とする辞書を返す
        
        Returns:
            Dict[Tuple[str, str], Permission]: (resource, action) -> Permission のマッピング
        """
        permissions = Permission.objects.all()
        permission_map = {
            (permission.resource, permission.action): permission
            for permission in permissions
        }
        return permission_map

    @staticmethod
    def _validate_default_permissions_exist() -> Dict[Tuple[str, str], Permission]:
        """
        デフォルトロールに必要なPermissionが存在するかチェックする
        
        Returns:
            Dict[Tuple[str, str], Permission]: (resource, action) -> Permission のマッピング
            
        Raises:
            ValidationError: 必要なPermissionが存在しない場合
        """
        permission_map = OrganizationService._get_permissions_map()
        #
        # 必要なpermissionを持っているかチェック
        missing_keys = []
        for _, permission_keys in DEFAULT_ROLE_PERMISSION_KEYS.items():
            for key in permission_keys:
                if key not in permission_map:
                    missing_keys.append(key)
        #
        # 持っていないのなら例外
        if missing_keys:
            missing_text = ", ".join([f"{res}.{act}" for res, act in missing_keys])
            raise ValidationError(f"Required permissions are missing: {missing_text}")

        return permission_map
    
    @staticmethod
    @transaction.atomic
    def create_default_roles(organization: Organization) -> dict[str, Role]:
        """
        Organizationにデフォルトロールを作成する
        """
        permission_map = OrganizationService._validate_default_permissions_exist()
        
        roles = {}
        for role_name, permission_keys in DEFAULT_ROLE_PERMISSION_KEYS.items():
            role = Role.objects.create(
                organization=organization,
                name=role_name,
            )
            role.permissions.set([permission_map[key] for key in permission_keys])
            roles[role_name] = role
        
        return roles
    
    @staticmethod
    @transaction.atomic
    def create_organization(*, user: User, name: str, slug: str) -> Organization:
        """
        Organizationを作成する
        
        Args:
            user: Organizationの作成者
            name: Organization名
            slug: Organizationスラッグ
            
        Returns:
            Organization: 作成されたOrganization
            
        キーワード引数を強制: create_organization(user=user, name="組織名", slug="org-slug")
        """
        try:
            organization = Organization.objects.create(name=name, slug=slug)
        except IntegrityError as e:
            raise ValidationError(f"Organization slug: {slug} が既に使用されています") from e
        except Exception as e:
            raise ValidationError(f"Organizationの作成に失敗しました: {str(e)}") from e

        roles = OrganizationService.create_default_roles(organization)

        try:
            membership = Membership.objects.create(
                user=user,
                organization=organization,
                scope_type=MembershipScope.ALL,
                is_org_admin=False, # Admin Role 付与時に同期してTrueにする
                is_active=True,
            )
        except IntegrityError as e:
            raise ValidationError(f"Membership の作成に失敗しました") from e
        #
        # Membership に Admin Role を付与
        MembershipService.assign_role(
            membership=membership,
            role=roles[RoleDefaultName.ADMIN]
        )

        return organization


