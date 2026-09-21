from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.contrib.auth import authenticate
from django.utils import timezone
import logging

from accounts.models import EmailVerificationToken, EmailVerificationStatus
from tenants.models import Organization
from tenants.services import OrganizationService

logger = logging.getLogger(__name__)

User = get_user_model()


class RegisterSerializer(serializers.Serializer):
    """
    Email登録用Serializer
    """
    email = serializers.EmailField(required=True)

    def validate_email(self, value: str):
        """ Emailのバリデーション """
        #
        # 既存ユーザーチェック
        if User.objects.filter(email=value).exists():
            logger.error(f"Email {value} is already registered.")
            raise serializers.ValidationError("このメールアドレスは既に登録されています。")
        
        # 進行中の認証チェック
        if EmailVerificationToken.objects.filter(
                email=value,
                status=EmailVerificationStatus.PENDING,
                expires_at__gt=timezone.now()
            ).exists():
            logger.error(f"Email {value} is already pending verification.")
            raise serializers.ValidationError("このメールアドレスは認証待ちです。メールをご確認ください。")
        
        return value
    

class CompleteRegistrationSerializer(serializers.Serializer):
    """
    登録完了用Serializer(パスワード設定＋組織作成)
    """
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
    organization_name = serializers.CharField(required=True, max_length=255)
    organization_slug = serializers.SlugField(required=True, max_length=100)

    def validate_token(self, value: str) -> str:
        """ トークンのバリデーション """
        try:
            token_obj = EmailVerificationToken.objects.get(token=value)
        except EmailVerificationToken.DoesNotExist:
            logger.error(f"Token {value} does not exist.")
            raise serializers.ValidationError("無効なトークンです。")
        
        if not token_obj.is_valid():
            if token_obj.status == EmailVerificationStatus.COMPLETED:
                logger.error(f"Token {value} is already completed.")
                raise serializers.ValidationError("このトークンは既に使用されています。")
            elif token_obj.status == EmailVerificationStatus.EXPIRED:
                logger.error(f"Token {value} is expired.")
                raise serializers.ValidationError("トークンの有効期限が切れています。再度登録してください。")
            else:
                logger.error(f"Token {value} is invalid.")
                raise serializers.ValidationError("無効なトークンです。")

        return value
    
    def validate_organization_slug(self, value: str) -> str:
        """ 組織スラッグのバリデーション """
        if Organization.objects.filter(slug=value).exists():
            logger.error(f"Organization slug {value} is already exists.")
            raise serializers.ValidationError("このスラッグは既に使用されています。別のスラッグを指定してください。")

        return value
    
    def validate(self, attrs):
        """ 追加のバリデーション """
        # ここに追加のバリデーションロジックを記述
        
        # パスワード一致チェック
        if attrs['password'] != attrs['password_confirm']:
            # logger.error(f"Password and password_confirm do not match.")
            raise serializers.ValidationError({"password_confirm": "パスワードが一致しません。"})
        
        # password_confirm は不要なので削除
        attrs.pop('password_confirm')

        token = attrs['token']

        try:
            token_obj = EmailVerificationToken.objects.get(token=token)
        except EmailVerificationToken.DoesNotExist:
            # logger.error(f"Token {token} does not exist.")
            raise serializers.ValidationError("無効なトークンです。")
        
        if not token_obj.is_valid():
            # logger.error(f"Token {token} is not valid.")
            raise serializers.ValidationError("トークンが無効になりました。再度登録してください。")
        
        attrs['email'] = token_obj.email

        return attrs


class LoginSerializer(serializers.Serializer):
    """
    ログイン用Serializer
    """
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )

    def validate(self, attrs):
        """ 認証バリデーション """
        email = attrs.get('email')
        password = attrs.get('password')
        
        user = authenticate(
            request=self.context.get('request'),
            username=email,
            password=password
        )

        if user is None:
            # logger.error(f"User with email {email} does not exist.")
            raise serializers.ValidationError("メールアドレスまたはパスワードが間違っています。")
        
        if not user.is_active:
            # logger.error(f"User {email} is not active.")
            raise serializers.ValidationError("このアカウントは無効になっています。")
        
        attrs['user'] = user
        return attrs
