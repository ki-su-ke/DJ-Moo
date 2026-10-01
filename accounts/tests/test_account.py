from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken

from accounts.models import (
    EmailVerificationStatus,
    EmailVerificationToken,
    TokenType,
)
from accounts.services import (
    AccountService,
    LastOrganizationAdminError,
)
from tenants.constants import DEFAULT_ROLE_PERMISSION_KEYS
from tenants.models import Permission, Membership, Organization


User = get_user_model()


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AccountWorkflowTests(APITestCase):
    def setUp(self):
        # ログインや各種変更のテストで共通して使うアカウントを用意する。
        self.user = User.objects.create_user(
            email="member@example.com",
            password="old-password-123",
        )

    def test_account_creation(self):
        # OrganizationService が初期 Role に割り当てる Permission を準備する。
        permission_keys = {
            key
            for keys in DEFAULT_ROLE_PERMISSION_KEYS.values()
            for key in keys
        }
        for resource, action in permission_keys:
            Permission.objects.get_or_create(
                resource=resource,
                action=action,
                defaults={"name": f"{resource}.{action}"},
            )

        # 登録リクエストでメール認証用のトークンが作られる。
        response = self.client.post(
            reverse("accounts:register"),
            {"email": "new-member@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        token = EmailVerificationToken.objects.get(email="new-member@example.com")
        self.assertEqual(token.status, EmailVerificationStatus.PENDING)
        self.assertEqual(len(mail.outbox), 1)

        # 認証トークンを使ってユーザーと初期 Organization を作成する。
        response = self.client.post(
            reverse("accounts:complete"),
            {
                "token": str(token.token),
                "password": "new-password-123",
                "password_confirm": "new-password-123",
                "organization_name": "New Organization",
                "organization_slug": "new-organization",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        created_user = User.objects.get(email="new-member@example.com")
        self.assertTrue(created_user.check_password("new-password-123"))
        token.refresh_from_db()
        self.assertEqual(token.status, EmailVerificationStatus.COMPLETED)
        self.assertIn("organization", response.data)
        self.assertNotContains(
            self.client.get(reverse("accounts:verify", kwargs={"token": token.token})),
            "アクセストークン:",
        )

    def test_account_deletion_removes_user_and_associated_tokens(self):
        # Userの物理削除時に、関連するEmailVerificationTokenも削除されることを確認する
        token = EmailVerificationToken.objects.create(
            email=self.user.email,
            token_type=TokenType.PASSWORD_CHANGE,
            user=self.user,
        )

        self.user.delete()

        self.assertFalse(User.objects.filter(pk=self.user.pk).exists())
        self.assertFalse(EmailVerificationToken.objects.filter(pk=token.pk).exists())

    def test_login(self):
        # 正しいメールアドレスとパスワードで JWT が発行される。
        response = self.client.post(
            reverse("accounts:login"),
            {"email": self.user.email, "password": "old-password-123"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_logout(self):
        # ログアウトで Refresh Token がブラックリストに登録される。
        refresh = RefreshToken.for_user(self.user)
        response = self.client.post(
            reverse("accounts:logout"),
            {"refresh": str(refresh)},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            BlacklistedToken.objects.filter(token__jti=refresh["jti"]).exists()
        )

    def test_password_change(self):
        # 認証済みユーザーから変更メールを要求し、メール内トークンで変更を確定する。
        self.client.force_authenticate(user=self.user)
        response = self.client.post(reverse("accounts:change_password_request"))
        self.assertEqual(response.status_code, 200)

        token = EmailVerificationToken.objects.get(
            user=self.user,
            token_type=TokenType.PASSWORD_CHANGE,
            status=EmailVerificationStatus.PENDING,
        )
        response = self.client.post(
            reverse("accounts:change_password", kwargs={"token": token.token}),
            {
                "password": "updated-password-123",
                "password_confirm": "updated-password-123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("updated-password-123"))
        token.refresh_from_db()
        self.assertEqual(token.status, EmailVerificationStatus.COMPLETED)
        self.assertEqual(len(mail.outbox), 1)

    def test_email_change_rejects_invalid_confirmation_links(self):
        for token_type, status, expired in (
            (TokenType.EMAIL_CHANGE, EmailVerificationStatus.PENDING, True),
            (TokenType.EMAIL_CHANGE, EmailVerificationStatus.COMPLETED, False),
            (TokenType.PASSWORD_CHANGE, EmailVerificationStatus.PENDING, False),
        ):
            with self.subTest(token_type=token_type, status=status, expired=expired):
                token = EmailVerificationToken.objects.create(
                    email=self.user.email,
                    user=self.user,
                    new_email="updated@example.com",
                    token_type=token_type,
                    status=status,
                )
                if expired:
                    token.expires_at = timezone.now() - timedelta(minutes=1)
                    token.save(update_fields=["expires_at"])
                response = self.client.get(reverse("accounts:change_email", kwargs={"token": token.token}))
                self.assertContains(response, "無効または期限切れのリンクです。")
                self.user.refresh_from_db()
                self.assertEqual(self.user.email, "member@example.com")

    def test_email_change(self):
        # 認証済みユーザーから変更を要求し、新アドレス宛てのトークンで確定する。
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            reverse("accounts:change_email_request"),
            {"new_email": "updated@example.com"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)

        token = EmailVerificationToken.objects.get(
            user=self.user,
            token_type=TokenType.EMAIL_CHANGE,
            status=EmailVerificationStatus.PENDING,
        )
        self.assertEqual(token.new_email, "updated@example.com")
        confirmation_url = reverse("accounts:change_email", kwargs={"token": token.token})
        confirmation = self.client.get(confirmation_url)
        self.assertEqual(confirmation.status_code, 200)
        self.assertContains(confirmation, "updated@example.com")
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "member@example.com")
        response = self.client.post(
            confirmation_url,
            {},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "updated@example.com")
        token.refresh_from_db()
        self.assertEqual(token.status, EmailVerificationStatus.COMPLETED)
        self.assertEqual(len(mail.outbox), 1)
        self.assertContains(
            self.client.get(confirmation_url),
            "無効または期限切れのリンクです。",
        )
        self.assertEqual(self.client.post(confirmation_url, {}, format="json").status_code, 400)

    def test_deactivate_account(self):
        """
        アカウントの退会処理をテスト
        """
        organization = Organization.objects.create(
            name="Test Organization",
            slug="test-organization",
        )

        other_user = User.objects.create_user(
            email="other@example.com",
            password="other-password-123",
        )
        #
        # 自分のユーザーと他のユーザーのメンバーシップを作成する
        # どちらも管理者権限を持つので正常に退会できるはず
        membership = Membership.objects.create(
            user=self.user,
            organization=organization,
            is_org_admin=True,
            is_active=True,
        )
        Membership.objects.create(
            user=other_user,
            organization=organization,
            is_org_admin=True,
            is_active=True,
        )
        #
        # 自分のアカウントを退会させる
        AccountService.deactivate_account(user=self.user)

        self.user.refresh_from_db()
        membership.refresh_from_db()
        #
        # アカウント退会後の状態を確認(正常系)
        self.assertFalse(self.user.is_active)
        self.assertIsNotNone(self.user.deactivated_at)
        self.assertTrue(self.user.email.startswith("deleted-"))
        self.assertTrue(self.user.has_usable_password() is False)
        self.assertIsNotNone(membership.deleted)

    def test_deactivate_account_rejects_last_organization_admin(self):
        """
        最後の組織管理者がアカウントを退会しようとした場合にエラーが発生することをテスト
        """
        organization = Organization.objects.create(
            name="Only Admin Organization",
            slug="only-admin-organization",
        )
        
        membership = Membership.objects.create(
            user=self.user,
            organization=organization,
            is_org_admin=True,
            is_active=True,
        )

        with self.assertRaises(LastOrganizationAdminError):
            AccountService.deactivate_account(user=self.user)

        self.user.refresh_from_db()
        membership.refresh_from_db()

        self.assertTrue(self.user.is_active)
        self.assertIsNone(self.user.deactivated_at) # 最後の組織管理者が退会できなかったことを確認
        self.assertFalse(self.user.email.startswith("deleted-"))
        self.assertIsNone(membership.deleted)

    def test_staff_deletes_target_account_without_deactivating_self(self):
        staff = User.objects.create_user(
            email="staff@example.com", password="staff-password-123", is_staff=True,
        )
        self.client.force_authenticate(user=staff)

        response = self.client.delete(
            reverse("accounts:delete_account", kwargs={"user_id": self.user.pk}),
            {"confirmation": "DELETE"},
            format="json",
        )

        self.assertEqual(response.status_code, 204, response.data)
        self.user.refresh_from_db()
        staff.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertIsNotNone(self.user.deactivated_at)
        self.assertTrue(staff.is_active)

    def test_non_staff_cannot_delete_another_account(self):
        target = User.objects.create_user(email="target@example.com", password="target-password-123")
        self.client.force_authenticate(user=self.user)

        response = self.client.delete(
            reverse("accounts:delete_account", kwargs={"user_id": target.pk}),
            {"confirmation": "DELETE"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        target.refresh_from_db()
        self.assertTrue(target.is_active)

    def test_staff_cannot_delete_last_organization_admin(self):
        staff = User.objects.create_user(
            email="staff@example.com", password="staff-password-123", is_staff=True,
        )
        organization = Organization.objects.create(name="Protected Organization", slug="protected-organization")
        Membership.objects.create(
            user=self.user, organization=organization, is_org_admin=True, is_active=True,
        )
        self.client.force_authenticate(user=staff)

        response = self.client.delete(
            reverse("accounts:delete_account", kwargs={"user_id": self.user.pk}),
            {"confirmation": "DELETE"},
            format="json",
        )

        self.assertEqual(response.status_code, 409)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)
