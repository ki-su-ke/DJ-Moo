import uuid
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db import IntegrityError
from django.core.exceptions import MultipleObjectsReturned, ObjectDoesNotExist
from typing import Dict, Tuple

from django.contrib.auth import get_user_model

from tenants.constants import PermissionKey, RoleDefaultName, DEFAULT_ROLE_PERMISSION_KEYS
from tenants.models import (
    Membership, MembershipRole, MembershipScope,
    Organization, Role
)

import logging

logger = logging.getLogger(__name__)


User = get_user_model()


class MembershipService:
    """
    メンバーシップ関連のビジネスロジックを処理するサービスクラス
    """
    @staticmethod
    def _ensure_same_organization(*, membership: Membership, role: Role):
        """
        テナント境界チェック

        MembershipとRoleは同一のOrganizationであることを確認する

        raises: ValidationError - MembershipとRoleが異なるOrganizationに所属している場合
        
        キーワード引数強制： _ensure_same_organization(membership=membership, role=role)
        """
        if membership.organization_id != role.organization_id:
            raise ValidationError("Membership と Role は同じ Organization に所属していなければなりません")
    
    @staticmethod
    def _is_admin_role(role: Role) -> bool:
        """
        管理者Roleかを返す関数

        returns: Trueなら管理者Role、Falseならそれ以外
        """
        return role.name == RoleDefaultName.ADMIN

    @staticmethod
    def _count_active_org_admins(*, organization_id: uuid.UUID) -> int:
        """
        指定されたOrganizationの有効な組織管理者の数を返す関数
        
        args:
            organization_id: OrganizationのID
        
        returns: 有効な組織管理者の数
        """
        return Membership.objects.filter(
            organization_id=organization_id,
            is_org_admin=True,
            is_active=True,
        ).count()
    

    @staticmethod
    def _ensure_last_admin_will_remain(*, membership: Membership):
        """
        最後の管理者が残るようにチェックする関数
        
        args:
            membership: Membershipオブジェクト
        
        raises: ValidationError - 最後の管理者が残らない場合
        """
        if not membership.is_org_admin or not membership.is_active:
            return
        
        remaining_count = Membership.objects.filter(
            organization_id=membership.organization_id,
            is_org_admin=True,
            is_active=True,
        ).exclude(pk=membership.pk).count()

        if remaining_count < 1:
            logger.error("At least one active organization admin must remain.")
            raise ValidationError("管理者権限を持つメンバーが1人以上必要です。")

    
    @staticmethod
    @transaction.atomic
    def create_membership(
        *,
        user: User,
        organization: Organization,
        scope_type: str = MembershipScope.ASSIGNED,
        is_active: bool = True,
        roles: list[Role] | None = None
    ) -> Membership:
        """
        メンバーシップを作成する関数
        
        args:
            user: Userオブジェクト
            organization: Organizationオブジェクト
            scope_type: スコープタイプ
            is_active: アクティブかどうか
            roles: ロールリスト
            
        returns:
            Membershipオブジェクト
        """
        try:
            membership = Membership.objects.create(
                user=user,
                organization=organization,
                scope_type=scope_type,
                is_org_admin=False,
                is_active=is_active,
            )

            if roles:
                for role in roles:
                    MembershipService.assign_role(
                        membership=membership,
                        role=role
                    )

            return membership

        except IntegrityError as e:
            logger.error(f"Failed to create membership: {str(e)}")
            raise ValidationError("メンバーシップの作成に失敗しました。")
        except Exception as e:
            logger.error(f"Unexpected error occurred: {str(e)}", exc_info=True)
            raise

    @staticmethod
    @transaction.atomic
    def assign_role(*, membership: Membership, role: Role) -> MembershipRole:
        """
        メンバーシップにロールを付与する関数
        
        args:
            membership: Membershipオブジェクト
            role: Roleオブジェクト
            
        returns:
            MembershipRoleオブジェクト
        """
        try:
            MembershipService._ensure_same_organization(
                membership=membership,
                role=role,
            )

            membership_role, created = MembershipRole.objects.get_or_create(
                membership=membership,
                role=role,
            )

            if (MembershipService._is_admin_role(role) and
                    not Membership.is_org_admin):
                membership.is_org_admin = True
                membership.save(update_fields=["is_org_admin", "updated_at"])
            
            return membership_role

        except IntegrityError as e:
            logger.error(f"Failed to create MembershipRole. {str(e)}", exc_info=True)
            raise ValidationError("ロールの付与に失敗しました。")
        except MultipleObjectsReturned as e:
            logger.error(f"Multiple MembershipRole found. {str(e)}", exc_info=True)
            raise ValidationError("ロールの付与に失敗しました。")
        except Exception as e:
            logger.error(f"Unexpected error occurred: {str(e)}", exc_info=True)
            raise

    @staticmethod
    @transaction.atomic
    def unassign_role(*, membership: Membership, role: Role):
        """
        メンバーシップからロールを削除する関数
        
        args:
            membership: Membershipオブジェクト
            role: Roleオブジェクト
            
        returns:
            None
        """
        MembershipService._ensure_same_organization(
            membership=membership,
            role=role,
        )

        link = MembershipRole.objects.filter(
                    membership=membership,
                    role=role,
                ).first()
        if not link:
            return

        if MembershipService._is_admin_role(role):
            #
            # is_org_adminが他にもあるかを確認(無いならValidationError送出)
            MembershipService._ensure_last_admin_will_remain(membership=membership)
        
        link.delete()

        if MembershipService._is_admin_role(role) and membership.is_org_admin:
            membership.is_org_admin = False
            membership.save(update_fields=["is_org_admin", "updated_at"])
            

    @staticmethod
    @transaction.atomic
    def replace_roles(*, membership: Membership, roles: list[Role]) -> Membership:
        """
        メンバーシップのロールを一括で置換する関数

        引数で与えられたロールリストに含まれるロールのみがメンバーシップに付与され、
        それ以外のロールは削除される
        
        args:
            membership: Membershipオブジェクト
            roles: Roleオブジェクトのリスト
            
        returns:
            Membership
        """
        try:
            role_ids = set()
            has_admin_role = False

            for role in roles:
                MembershipService._ensure_same_organization(
                    membership=membership,
                    role=role,
                )
                role_ids.add(role.id)
                if MembershipService._is_admin_role(role):
                    #
                    # rolesの中に管理者ロールが含まれているなら、管理者Membershipとするためのフラグ
                    has_admin_role = True
            
            current_roles = list(membership.roles.all())
            current_has_admin = membership.is_org_admin

            if current_has_admin and not has_admin_role:
                #
                # roles置き換えの結果、管理者権限が外れるなら
                # 他に管理者権限を持つMembershipが無いかをチェックする(無いならValidationErrorを送出)
                MembershipService._ensure_last_admin_will_remain(
                                        membership=membership
                                    )
            
            MembershipRole.objects.filter(membership=membership).exclude(
                    role_id__in=role_ids
                ).delete()
            
            existing_role_ids = set(
                MembershipRole.objects.filter(membership=membership).values_list("role_id", flat=True)
            )
            #
            # 引数で指定されたRoleのうち、まだmembershipに紐付けられていないものがあれば
            # 新規に紐付ける
            for role in roles:
                if role.id not in existing_role_ids:
                    MembershipRole.objects.create(
                        membership=membership,
                        role=role,
                    )
            
            membership.is_org_admin = has_admin_role
            membership.save(update_fields=["is_org_admin", "updated_at"])
            return membership

        except IntegrityError as e:
            logger.error(f"Failed to replace roles for membership {membership.id}: {str(e)}", exc_info=True)
            raise ValidationError("ロールの置換に失敗しました。")
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in replace_roles: {str(e)}", exc_info=True)
            raise


    @staticmethod
    @transaction.atomic
    def update_membership(
            *,
            membership: Membership,
            scope_type: str | None = None,
            is_active: bool | None = None
        ) -> Membership:
        """
        メンバーシップを更新する
        
        args:
            membership: 対象のメンバーシップ
            scope_type: スコープタイプ
            is_active: アクティブかどうか
            
        returns:
            更新されたMembershipオブジェクト
        """
        try:
            if scope_type is not None:
                membership.scope_type = scope_type

            if is_active is not None and membership.is_active and not is_active:
                MembershipService._ensure_last_admin_will_remain(membership=membership)
                membership.is_active = False
            elif is_active is not None:
                membership.is_active = is_active
            
            membership.save()
            return membership

        except IntegrityError as e:
            logger.error(f"Failed to update roles for membership {membership.id}: {str(e)}", exc_info=True)
            raise ValidationError("ロールの更新に失敗しました。")
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in update_membership: {str(e)}", exc_info=True)
            raise
    

    @staticmethod
    @transaction.atomic
    def deactivate_membership(*, membership: Membership) -> Membership:
        """
        メンバーシップをdeactivateする

        Args:
            membership: 対象のメンバーシップ

        Returns:
            非活性化されたメンバーシップ

        raises:
            ValidationError / etc
        """
        try:
            if not membership.is_active:
                return membership
            
            MembershipService._ensure_last_admin_will_remain(membership=membership)
            membership.is_active = False
            membership.save(update_fields=["is_active", "updated_at"])
            return membership
        
        except IntegrityError as e:
            logger.error(f"Failed to deactivate membership {membership.id}: {str(e)}", exc_info=True)
            raise ValidationError("メンバーシップの更新に失敗しました。")
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error in deactivate_membership {membership.id}: {str(e)}", exc_info=True)
            raise
    
    @staticmethod
    @transaction.atomic
    def activate_membership(*, membership: Membership) -> Membership:
        """
        メンバーシップをactivateする

        Args:
            membership: 対象のメンバーシップ

        Returns:
            活性化されたメンバーシップ

        raises:
            ValidationError / etc
        """
        try:
            if membership.is_active:
                return membership

            membership.is_active = True
            membership.save(update_fields=["is_active", "updated_at"])
            return membership
        except IntegrityError as e:
            logger.error(f"Failed to activate membership {membership.id}: {str(e)}", exc_info=True)
            raise ValidationError("メンバーシップの更新に失敗しました。")
        except Exception as e:
            logger.error(f"Unexpected error in activate_membership {membership.id}: {str(e)}", exc_info=True)
            raise
    
    @staticmethod
    @transaction.atomic
    def soft_delete_membership(*, membership: Membership):
        """
        メンバーシップを論理削除する
        
        Args:
            membership: 対象のメンバーシップ
        
        raises:
            ValidationError / etc
        """
        try:
            MembershipService._ensure_last_admin_will_remain(membership=membership)
            membership.delete()
        except Exception as e:
            logger.error(f"Failed to soft-delete Membership {membership.id}", exc_info=True)
            raise
