from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase

from audit.models import SecurityEvent, SecurityEventType
from audit.services import AuditService


class AuditServiceTests(TestCase):
	"""監査イベント writer が request と actor の情報を保存することを確認する。"""

	def test_records_actor_target_and_request_metadata(self):
		"""SecurityEvent に actor、対象情報、接続 metadata が記録される。"""
		user = get_user_model().objects.create_user(
			email="audited@example.com",
			password="test-password",
		)
		request = RequestFactory().get(
			"/api/v1/team-a/members/",
			HTTP_USER_AGENT="security-test-agent",
			REMOTE_ADDR="198.51.100.25",
		)

		AuditService.record_security_event(
			request=request,
			user=user,
			event_type=SecurityEventType.TENANT_ESCAPE,
			attempted_organization_slug="team-a",
			target_resource="Membership",
			target_resource_id="membership-123",
			remarks="Membership belongs to another organization.",
		)

		event = SecurityEvent.objects.get()
		self.assertEqual(event.user, user)
		self.assertEqual(event.audit_user_id, user.pk)
		self.assertEqual(event.audit_user_email, user.email)
		self.assertEqual(event.event_type, SecurityEventType.TENANT_ESCAPE)
		self.assertEqual(event.attempted_organization_slug, "team-a")
		self.assertEqual(event.target_resource, "Membership")
		self.assertEqual(event.target_resource_id, "membership-123")
		self.assertEqual(event.ip_address, "198.51.100.25")
		self.assertEqual(event.user_agent, "security-test-agent")
		self.assertEqual(event.remarks, "Membership belongs to another organization.")
