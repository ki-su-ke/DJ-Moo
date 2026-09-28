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
from tenants.constants import DEFAULT_ROLE_PERMISSION_KEYS
from tenants.models import Permission


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
		# 削除 API はまだないため、現状の User 削除時の DB カスケードを確認する。
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
