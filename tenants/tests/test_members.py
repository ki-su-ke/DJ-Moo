from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from audit.models import SecurityEvent, SecurityEventType
from tenants.models import Membership, Organization


class OrganizationMemberApiTests(TestCase):
    """組織単位のメンバー一覧・削除 API の権限と境界を検証する。"""

    def setUp(self):
        """Admin、対象メンバー、複数組織への所属を用意する。"""
        user_model = get_user_model()
        self.admin = user_model.objects.create_user(
            email="admin@example.com",
            password="test-password",
        )
        self.member = user_model.objects.create_user(
            email="member@example.com",
            password="test-password",
        )
        self.organization = Organization.objects.create(name="Team A", slug="team-a")
        self.other_organization = Organization.objects.create(name="Team B", slug="team-b")
        Membership.objects.create(
            user=self.admin,
            organization=self.organization,
            is_org_admin=True,
            is_active=True,
        )
        self.member_membership = Membership.objects.create(
            user=self.member,
            organization=self.organization,
            is_active=True,
        )
        self.other_membership = Membership.objects.create(
            user=self.member,
            organization=self.other_organization,
            is_active=True,
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)

    def test_admin_can_list_only_active_members_in_organization(self):
        """Admin の一覧に、その組織の有効メンバーだけが含まれる。"""
        response = self.client.get(f"/api/v1/{self.organization.slug}/members/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {member["email"] for member in response.data["members"]},
            {"admin@example.com", "member@example.com"},
        )

    def test_non_admin_cannot_list_members(self):
        """一般メンバーによる一覧取得を拒否する。"""
        self.client.force_authenticate(user=self.member)

        response = self.client.get(f"/api/v1/{self.organization.slug}/members/")

        self.assertEqual(response.status_code, 403)
        event = SecurityEvent.objects.get()
        self.assertEqual(event.event_type, SecurityEventType.PERMISSION_DENIED)
        self.assertEqual(event.user, self.member)
        self.assertEqual(event.attempted_organization_slug, self.organization.slug)

    def test_admin_removes_member_from_this_organization_only(self):
        """削除対象の組織 Membership だけを論理削除する。"""
        response = self.client.delete(
            f"/api/v1/{self.organization.slug}/members/{self.member_membership.id}/"
        )

        self.assertEqual(response.status_code, 204)
        self.member_membership.refresh_from_db()
        self.other_membership.refresh_from_db()
        self.assertIsNotNone(self.member_membership.deleted)
        self.assertIsNone(self.other_membership.deleted)
        self.assertTrue(self.member.is_active)

    def test_membership_from_another_organization_cannot_be_removed(self):
        """別組織の Membership ID を指定した削除を拒否する。"""
        response = self.client.delete(
            f"/api/v1/{self.organization.slug}/members/{self.other_membership.id}/",
            REMOTE_ADDR="198.51.100.25",
            HTTP_USER_AGENT="membership-boundary-test",
        )

        self.assertEqual(response.status_code, 404)
        self.other_membership.refresh_from_db()
        self.assertIsNone(self.other_membership.deleted)
        event = SecurityEvent.objects.get()
        self.assertEqual(event.event_type, SecurityEventType.TENANT_ESCAPE)
        self.assertEqual(event.user, self.admin)
        self.assertEqual(event.attempted_organization_slug, self.organization.slug)
        self.assertEqual(event.target_resource, "Membership")
        self.assertEqual(event.target_resource_id, str(self.other_membership.id))
        self.assertEqual(event.ip_address, "198.51.100.25")
        self.assertEqual(event.user_agent, "membership-boundary-test")

    def test_unknown_membership_id_is_not_logged_as_tenant_escape(self):
        """存在しない Membership ID は越境イベントに分類しない。"""
        response = self.client.delete(
            f"/api/v1/{self.organization.slug}/members/00000000-0000-0000-0000-000000000001/"
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(
            SecurityEvent.objects.filter(event_type=SecurityEventType.TENANT_ESCAPE).exists()
        )

    def test_admin_cannot_remove_own_membership_through_member_removal(self):
        """メンバー削除 API から実行者自身を外せないことを確認する。"""
        admin_membership = Membership.objects.get(
            user=self.admin,
            organization=self.organization,
        )

        response = self.client.delete(
            f"/api/v1/{self.organization.slug}/members/{admin_membership.id}/"
        )

        self.assertEqual(response.status_code, 400)
        admin_membership.refresh_from_db()
        self.assertIsNone(admin_membership.deleted)