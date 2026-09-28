from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient
from unittest.mock import patch

from tenants.models import Membership, MembershipInvitation, Organization, Role


class OrganizationSlugInvitationTests(TestCase):
	def setUp(self):
		self.user = get_user_model().objects.create_user(
			email="admin@example.com",
			password="test-password",
		)
		self.organization = Organization.objects.create(
			name="Organization A",
			slug="organization-a",
		)
		self.other_organization = Organization.objects.create(
			name="Organization B",
			slug="organization-b",
		)
		self.role = Role.objects.create(
			name="Viewer",
			organization=self.organization,
		)
		inviter_membership = Membership.objects.create(
			user=self.user,
			organization=self.organization,
			is_org_admin=True,
		)
		self.invitation = MembershipInvitation.objects.create(
			email="invitee@example.com",
			organization=self.organization,
			role=self.role,
			invited_by=inviter_membership,
		)
		self.client = APIClient()
		self.client.force_authenticate(user=self.user)

	def test_invitation_collection_is_routed_by_organization_slug(self):
		response = self.client.get(
			f"/api/v1/{self.organization.slug}/invitations/"
		)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(len(response.data), 1)

	@patch("tenants.views.invitation_views.send_templated_email", return_value=True)
	def test_invitation_email_links_include_organization_slug(self, send_email):
		response = self.client.post(
			f"/api/v1/{self.organization.slug}/invitations/",
			{"email": "new-invitee@example.com"},
			format="json",
		)

		self.assertEqual(response.status_code, 201)
		email_context = send_email.call_args.kwargs["context"]
		self.assertIn(
			f"/api/v1/{self.organization.slug}/invitations/",
			email_context["accept_url"],
		)
		self.assertIn(
			f"/api/v1/{self.organization.slug}/invitations/",
			email_context["decline_url"],
		)

	def test_invitation_token_cannot_be_used_with_another_organization_slug(self):
		for action in ("accept", "decline"):
			with self.subTest(action=action):
				response = self.client.post(
					f"/api/v1/{self.other_organization.slug}/invitations/"
					f"{self.invitation.token}/{action}/",
					{},
				)

				self.assertEqual(response.status_code, 404)
				self.invitation.refresh_from_db()
				self.assertEqual(self.invitation.status, "pending")