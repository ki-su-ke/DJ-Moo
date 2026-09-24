import uuid
from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone

from tenants.models import (
    MembershipInvitation, InvitationStatus, Role
)
# from tenants.constants import RoleDefaultName

import logging

logger = logging.getLogger(__name__)

User = get_user_model()



class InviteMemberSerializer(serializers.Serializer):
    """ メンバー招待用Serializer """
    email = serializers.EmailField(required=True)
    role_id = serializers.UUIDField(required=False, allow_null=True)

    def validate_email(self, value: str) -> str:
        """ メールアドレスのバリデーション """
        #
        # 既存の招待待ちチェック
        if MembershipInvitation.objects.filter(
                email=value,
                status=InvitationStatus.PENDING,
                expires_at__gt=timezone.now()
            ).exists():
            raise serializers.ValidationError("このメールアドレスは既に招待待ちです。")
        
        return value

    def validate_role_id(self, value: uuid.UUID | None) -> uuid.UUID | None:
        """ 権限のバリデーション """
        if value is None:
            return None

        try:
            role = Role.objects.get(id=value)
            return role.id
        except Role.DoesNotExist as e:
            logger.error(f"Invalid Role ID: {value} {str(e)}", exc_info=True)
            raise serializers.ValidationError("無効なIDです。")


class AcceptInvitationSerializer(serializers.Serializer):
    """
    招待承認用Serializer
    """
    token = serializers.UUIDField(required=True)

    def validate_token(self, value: str) -> str:
        """ トークンのバリデーション """
        try:
            invitation = MembershipInvitation.objects.get(token=value)
        except MembershipInvitation.DoesNotExist as e:
            logger.error(f"Invalid Invitation Token: {value} {str(e)}", exc_info=True)
            raise serializers.ValidationError("無効な招待トークンです。")
        
        if not invitation.is_valid():
            if invitation.status == InvitationStatus.ACCEPTED:
                raise serializers.ValidationError("この招待は既に承認されています。")
            elif invitation.status == InvitationStatus.DECLINED:
                raise serializers.ValidationError("この招待は既に拒否されています。")
            elif invitation.status == InvitationStatus.EXPIRED:
                raise serializers.ValidationError("招待の有効期限が切れています。")
            else:
                raise serializers.ValidationError("無効な招待トークンです。")
        
        return value


class DeclineInvitationSerializer(serializers.Serializer):
    """
    招待拒否用Serializer
    """
    token = serializers.UUIDField(required=True)

    def validate_token(self, value: str) -> str:
        """ トークンのバリデーション """
        try:
            invitation = MembershipInvitation.objects.get(token=value)
        except MembershipInvitation.DoesNotExist:
            raise serializers.ValidationError("無効な招待トークンです。")

        if invitation.status != InvitationStatus.PENDING:
            raise serializers.ValidationError("この招待は既に処理されています。")

        return value


class InvitationSerializer(serializers.ModelSerializer):
    """
    招待一覧用Serializer
    """
    role_name = serializers.CharField(source='role.name', read_only=True)
    invited_by_email = serializers.CharField(source='invited_by.user.email', read_only=True)
    organization_name = serializers.CharField(source='organization.name', read_only=True)

    class Meta:
        model = MembershipInvitation
        fields = [
            'id',
            'email',
            'role_name',
            'role_id',
            'invited_by_email',
            'organization_name',
            'status',
            'expires_at',
            'created_at',
        ]
        read_only_fields = ['id', 'status', 'expires_at', 'created_at']
