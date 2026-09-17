from django.core.exceptions import ValidationError
from django.db import transaction
from django.db import IntegrityError
from typing import Dict, Tuple

from django.contrib.auth import get_user_model

from tenants.constants import PermissionKey, RoleDefaultName, DEFAULT_ROLE_PERMISSION_KEYS
from tenants.models import (
    Membership, MembershipRole, MembershipScope,
    Organization, Role
)


User = get_user_model()


class MembershipService:
    """
    """
    @staticmethod
    def _ensure_same_organization(*, membership: Membership, role: Role):
        """
        テナント境界チェック

        MembershipとRoleは同一のOrganizationであることを確認する
        
        キーワード引数強制： _ensure_same_organization(membership=membership, role=role)
        """
        pass
'''
    @staticmethod
    def _ensure_same_organization(*, membership: Membership, role: Role):
        if membership.organization_id != role.organization_id:
            raise ValidationError("Membership and Role must belong to the same organization.")

    @staticmethod
    def _is_admin_role(role: Role) -> bool:
        return role.name == ADMIN_ROLE_NAME

    @staticmethod
    def _count_active_org_admins(*, organization_id):
        return Membership.objects.filter(
            organization_id=organization_id,
            is_org_admin=True,
            is_active=True,
        ).count()

    @staticmethod
    def _ensure_last_admin_will_remain(*, membership: Membership):
        if not membership.is_org_admin or not membership.is_active:
            return

        remaining_count = Membership.objects.filter(
            organization_id=membership.organization_id,
            is_org_admin=True,
            is_active=True,
        ).exclude(pk=membership.pk).count()

        if remaining_count < 1:
            raise ValidationError("At least one active organization admin must remain.")

    @staticmethod
    @transaction.atomic
    def create_membership(
        *,
        user,
        organization: Organization,
        scope_type: str = MembershipScope.ASSIGNED,
        is_active: bool = True,
        roles: list[Role] | None = None,
    ) -> Membership:
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
                    role=role,
                )

        return membership

    @staticmethod
    @transaction.atomic
    def assign_role(*, membership: Membership, role: Role) -> MembershipRole:
        MembershipService._ensure_same_organization(
            membership=membership,
            role=role,
        )

        membership_role, created = MembershipRole.objects.get_or_create(
            membership=membership,
            role=role,
        )

        if MembershipService._is_admin_role(role) and not membership.is_org_admin:
            membership.is_org_admin = True
            membership.save(update_fields=["is_org_admin", "updated_at"])

        return membership_role

    @staticmethod
    @transaction.atomic
    def unassign_role(*, membership: Membership, role: Role):
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
            MembershipService._ensure_last_admin_will_remain(membership=membership)

        link.delete()

        if MembershipService._is_admin_role(role) and membership.is_org_admin:
            membership.is_org_admin = False
            membership.save(update_fields=["is_org_admin", "updated_at"])

    @staticmethod
    @transaction.atomic
    def replace_roles(*, membership: Membership, roles: list[Role]) -> Membership:
        role_ids = set()
        has_admin_role = False

        for role in roles:
            MembershipService._ensure_same_organization(
                membership=membership,
                role=role,
            )
            role_ids.add(role.id)
            if MembershipService._is_admin_role(role):
                has_admin_role = True

        current_roles = list(membership.roles.all())
        current_has_admin = membership.is_org_admin

        if current_has_admin and not has_admin_role:
            MembershipService._ensure_last_admin_will_remain(membership=membership)

        MembershipRole.objects.filter(membership=membership).exclude(
            role_id__in=role_ids
        ).delete()

        existing_role_ids = set(
            MembershipRole.objects.filter(membership=membership).values_list("role_id", flat=True)
        )

        for role in roles:
            if role.id not in existing_role_ids:
                MembershipRole.objects.create(
                    membership=membership,
                    role=role,
                )

        membership.is_org_admin = has_admin_role
        membership.save(update_fields=["is_org_admin", "updated_at"])
        return membership

    @staticmethod
    @transaction.atomic
    def update_membership(
        *,
        membership: Membership,
        scope_type: str | None = None,
        is_active: bool | None = None,
    ) -> Membership:
        if scope_type is not None:
            membership.scope_type = scope_type

        if is_active is not None and membership.is_active and not is_active:
            MembershipService._ensure_last_admin_will_remain(membership=membership)
            membership.is_active = False
        elif is_active is not None:
            membership.is_active = is_active

        membership.save()
        return membership

    @staticmethod
    @transaction.atomic
    def deactivate_membership(*, membership: Membership) -> Membership:
        if not membership.is_active:
            return membership

        MembershipService._ensure_last_admin_will_remain(membership=membership)
        membership.is_active = False
        membership.save(update_fields=["is_active", "updated_at"])
        return membership

    @staticmethod
    @transaction.atomic
    def activate_membership(*, membership: Membership) -> Membership:
        if membership.is_active:
            return membership

        membership.is_active = True
        membership.save(update_fields=["is_active", "updated_at"])
        return membership

    @staticmethod
    @transaction.atomic
    def soft_delete_membership(*, membership: Membership):
        MembershipService._ensure_last_admin_will_remain(membership=membership)
        membership.delete()
'''