import uuid
from datetime import timedelta
from django.db import models
from django.utils import timezone
from django.conf import settings


class EmailVerificationStatus(models.TextChoices):
    """ 認証用ステータスを定義 """
    PENDING = "pending", "Pending"
    COMPLETED = "completed", "Completed"
    EXPIRED = "expired", "Expired"


class TokenType(models.TextChoices):
    """
    トークンタイプの定義

    認証用: "registration"  
    パスワード変更用: "password_change"  
    メールアドレス変更用: "email_change"  
    """
    REGISTRATION = "registration", "Registration"
    PASSWORD_CHANGE = "password_change", "Password Change"
    EMAIL_CHANGE = "email_change", "Email Change"



class EmailVerificationToken(models.Model):
    """
    メール認証用トークンモデル

    アカウント追加時、最初の一人はOrganizationのオーナー(Admin)となる想定。
    その場合、パスワード設定画面にてOrganizationも作成するという段取りになるため、
    このようなメール認証用トークンモデルを追加する。  
    ユーザーのパスワード変更、メールアドレス変更の際も利用するように拡張。
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(verbose_name="メールアドレス")
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    token_type = models.CharField(
        max_length=50,
        choices=TokenType.choices,
        default=TokenType.REGISTRATION,
        verbose_name="トークンタイプ"
    )
    """ 認証、パスワード変更、メアド変更を表すトークンタイプ """

    new_email = models.EmailField(null=True, blank=True, verbose_name="新しいメールアドレス")
    """ 変更したいメールアドレス メールアドレス変更の場合のみ使用 """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="verification_tokens",
        null=True,
        blank=True,
        verbose_name="ユーザー"
    )
    """ パスワード変更やメアド変更に利用する どのユーザーに紐付けられているか """

    expires_at = models.DateTimeField(verbose_name="有効期限")
    status = models.CharField(
        max_length=50,
        choices=EmailVerificationStatus.choices,
        default=EmailVerificationStatus.PENDING,
        verbose_name="ステータス"
    )

    # 組織情報(事前入力用、パスワード設定画面で入力を求めて確定させる)
    organization_name = models.CharField(
            max_length=255,
            null=True,
            blank=True,
            verbose_name="組織名"
        )
    
    organization_slug = models.SlugField(
            max_length=100,
            null=True,
            blank=True,
            verbose_name="組織スラッグ"
        )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="作成日時")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新日時")

    class Meta:
        db_table = "accounts_email_verification_token"
        verbose_name = "Email Verification Token"
        verbose_name_plural = "Email Verification Tokens"
        indexes = [
            models.Index(fields=["token"]),
            models.Index(fields=["email", "status"]),
            models.Index(fields=["expires_at"]),
            models.Index(fields=["token_type", "status"]),
        ]
    
    def __str__(self):
        return f"{self.email} - {self.status}"

    def is_valid(self):
        """ トークンが有効かどうかの確認 """
        return (
            self.status == EmailVerificationStatus.PENDING and
            self.expires_at > timezone.now()
        )
    
    def save(self, *args, **kwargs):
        #
        # 保存時にexpires_atが設定されていない場合は24時間後に設定
        if not self.expires_at:
            if self.token_type == TokenType.REGISTRATION:
                self.expires_at = timezone.now() + timedelta(hours=24)
            else:
                self.expires_at = timezone.now() + timedelta(hours=1)
        super().save(*args, **kwargs)

