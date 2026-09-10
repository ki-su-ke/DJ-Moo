import uuid
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        """
        ユーザー作成
        """
        if not email:
            raise ValueError("メールアドレスは必須です")
        
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)

        # パスキーのみで登録する場合は一時的にパスワードを無しに設定できるように考慮
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()

        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        """
        Super User 作成
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    JWT / MFA / パスキー認証に対応する予定なカスタムユーザーモデル
    """
    #
    # id はUUIDとするのがよさそう
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    """ UUID primary key """

    email = models.EmailField(unique=True, verbose_name="メールアドレス")
    """ 認証の識別子としてEmailを使用 """

    is_active = models.BooleanField(default=True, verbose_name="アクティブ")
    """ 有効なユーザーか """

    is_staff = models.BooleanField(default=False, verbose_name="スタッフ権限")
    """ スタッフ権限を持つユーザーか """

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="作成日時")
    """ 作成日時 """

    updated_at = models.DateTimeField(auto_now=True, verbose_name="更新日時")
    """ 更新日時 """

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []  # スーパーユーザー作成時、email以外に必要なフィールド

    class Meta:
        db_table = "users"
        verbose_name = "ユーザー"
        verbose_name_plural = "ユーザー"

    def __str__(self):
        return self.email
