from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone

from accounts.models import (
    EmailVerificationToken, 
    EmailVerificationStatus,
    TokenType
)
from tenants.models import Membership
# from tenants.models import Organization

import logging

logger = logging.getLogger(__name__)

User = get_user_model()



class ChangePasswordRequestSerializer(serializers.Serializer):
    """ パスワード変更リクエスト用Serializer """

    def validate(self, attrs):
        """ 認証済みユーザーであることを確認(view側で行うため空実装) """
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    """ パスワード変更用Serializer """

    token = serializers.UUIDField(required=True)

    password = serializers.CharField(
        required=True,
        min_length=8,
        write_only=True,
        style={'input_type': 'password'}
    )

    password_confirm = serializers.CharField(
        required=True,
        min_length=8,
        write_only=True,
        style={'input_type': 'password'}
    )

    def validate_token(self, value):
        """ トークンのバリデーション """
        try:
            token_obj = EmailVerificationToken.objects.get(token=value)
        except EmailVerificationToken.DoesNotExist:
            logger.error(f"Token not found.", exc_info=True)
            raise serializers.ValidationError("無効なトークンです。")

        if not token_obj.is_valid():
            if token_obj.status == EmailVerificationStatus.COMPLETED:
                # logger.error("This token has already been used.")
                raise serializers.ValidationError("このトークンは既に使用されています。")
            elif token_obj.status == EmailVerificationStatus.EXPIRED:
                # logger.error("This token is expired.")
                raise serializers.ValidationError("トークンの有効期限が切れています。再度リクエストしてください。")
            else:
                # logger.error("Invalid token.")
                raise serializers.ValidationError("無効なトークンです。")

        if token_obj.token_type != TokenType.PASSWORD_CHANGE:
            logger.error("This token type is not for password change.")
            raise serializers.ValidationError("パスワード変更用のトークンではありません。")

        return value

    def validate(self, attrs):
        """ 追加のバリデーション """
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password_confirm": "パスワードが一致しません。"})
        
        # password_confirm は不要なので削除
        attrs.pop('password_confirm')

        return attrs


class ChangeEmailRequestSerializer(serializers.Serializer):
    """ メールアドレス変更リクエスト用Serializer """
    new_email = serializers.EmailField(required=True)

    def validate_new_email(self, value):
        """ メールアドレス変更のためのバリデーション """
        #
        # 既存ユーザーチェック
        if User.objects.filter(email=value).exists():
            # logger.error("This email has already been used.")
            raise serializers.ValidationError("このメールアドレスは既に使用されています。")
        #
        # 同じメールアドレスだった場合は変更処理を続行する必要はない
        if self.context.get('request') and self.context['request'].user.email == value:
            raise serializers.ValidationError("現在のメールアドレスと同じです。")

        return value


class ChangeEmailSerializer(serializers.Serializer):
    """ メールアドレス変更用Serializer """

    token = serializers.UUIDField(required=True)

    def validate_token(self, value: str) -> str:
        """ トークンのバリデーション """
        try:
            token_obj = EmailVerificationToken.objects.get(token=value)
        except EmailVerificationToken.DoesNotExist as e:
            logger.error(f"Invalid token. {str(e)}", exc_info=True)
            raise serializers.ValidationError("無効なトークンです。")
        
        if not token_obj.is_valid():
            if token_obj.status == EmailVerificationStatus.COMPLETED:
                raise serializers.ValidationError("このトークンは既に使用されています。")
            elif token_obj.status == EmailVerificationStatus.EXPIRED:
                raise serializers.ValidationError("トークンの有効期限が切れています。再度リクエストしてください。")
            else:
                raise serializers.ValidationError("無効なトークンです。")
        
        if token_obj.token_type != TokenType.EMAIL_CHANGE:
            raise serializers.ValidationError("メールアドレス変更用のトークンではありません。")
        
        return value


class UserProfileSerializer(serializers.ModelSerializer):
    """ ユーザープロフィール用Serializer """

    memberships = serializers.SerializerMethodField()
    """
    所属している組織  
    表示項目の管理、割り当てられてるRoleの表示などもあるので MethodField
    """

    class Meta:
        model = User
        fields = [
            'id',
            'email',
            'is_active',
            'created_at',
            'updated_at',
            'memberships',
        ]
        read_only_fields = ['id', 'email', 'is_active', 'created_at', 'updated_at']

    def get_memberships(self, obj):
        """ 所属組織情報を取得 """
        memberships = Membership.objects.filter(
            user=obj,
            is_active=True
        ).select_related('organization').prefetch_related('roles')

        return [
            {
                'id': str(membership.id),
                'organization': {
                    'id': str(membership.organization.id),
                    'name': membership.organization.name,
                    'slug': membership.organization.slug,
                },
                'roles': [
                    {
                        'id': str(role.id),
                        'name': role.name,
                    }
                    for role in membership.roles.all()
                ],
                'is_org_admin': membership.is_org_admin,
                'scope_type': membership.scope_type,
            }
            for membership in memberships
        ]
