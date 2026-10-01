from uuid import UUID

from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from audit.models import SecurityEventType
from audit.services import AuditService
from tenants.models import Membership, Organization
from tenants.services import MembershipService


class OrganizationMembersView(APIView):
    """組織管理者向けのメンバー一覧・組織からの削除 API。"""

    permission_classes = [IsAuthenticated]

    def get_admin_membership(self, *, request: Request, organization: Organization) -> Membership | None:
        """指定組織で操作権限を持つ有効な Admin Membership を取得する。"""
        return Membership.objects.filter(
            user=request.user,
            organization=organization,
            is_org_admin=True,
            is_active=True,
        ).first()

    def get(self, request: Request, organization_slug: str) -> Response:
        """組織 Admin に限り、有効な所属メンバーの一覧を返す。"""
        organization = get_object_or_404(Organization, slug=organization_slug)
        if not self.get_admin_membership(request=request, organization=organization):
            AuditService.record_security_event(
                request=request,
                user=request.user,
                event_type=SecurityEventType.PERMISSION_DENIED,
                attempted_organization_slug=organization.slug,
                target_resource="Organization",
                target_resource_id=str(organization.pk),
                remarks="Non-admin requested the organization member list.",
            )
            return Response(
                {"error": "組織管理者のみがメンバーを閲覧できます。"},
                status=status.HTTP_403_FORBIDDEN,
            )

        memberships = Membership.objects.filter(
            organization=organization,
            is_active=True,
        ).select_related("user").order_by("user__email")
        return Response({
            "members": [
                {
                    "id": str(membership.id),
                    "user_id": str(membership.user_id),
                    "email": membership.user.email,
                    "is_org_admin": membership.is_org_admin,
                }
                for membership in memberships
            ]
        })

    def delete(self, request: Request, organization_slug: str, membership_id: UUID) -> Response:
        """指定された所属だけを論理削除し、ユーザーアカウントは維持する。"""
        organization = get_object_or_404(Organization, slug=organization_slug)
        if not self.get_admin_membership(request=request, organization=organization):
            AuditService.record_security_event(
                request=request,
                user=request.user,
                event_type=SecurityEventType.PERMISSION_DENIED,
                attempted_organization_slug=organization.slug,
                target_resource="Organization",
                target_resource_id=str(organization.pk),
                remarks="Non-admin requested organization member removal.",
            )
            return Response(
                {"error": "組織管理者のみがメンバーを削除できます。"},
                status=status.HTTP_403_FORBIDDEN,
            )

        membership = Membership.objects.filter(
            pk=membership_id,
            organization=organization,
            is_active=True,
        ).select_related("user").first()
        if membership is None:
            cross_organization_membership = Membership.objects.filter(
                pk=membership_id,
                is_active=True,
            ).exclude(organization=organization).first()
            if cross_organization_membership:
                AuditService.record_security_event(
                    request=request,
                    user=request.user,
                    event_type=SecurityEventType.TENANT_ESCAPE,
                    attempted_organization_slug=organization.slug,
                    target_resource="Membership",
                    target_resource_id=str(membership_id),
                    remarks="Membership belongs to another organization.",
                )
            raise Http404

        if membership.user_id == request.user.pk:
            return Response(
                {"error": "自分自身はこの操作では削除できません。"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            MembershipService.soft_delete_membership(membership=membership)
        except ValidationError as error:
            return Response({"error": str(error)}, status=status.HTTP_409_CONFLICT)

        return Response(status=status.HTTP_204_NO_CONTENT)