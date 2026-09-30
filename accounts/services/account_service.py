import uuid

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from tenants.models import Membership, Organization

import logging

logger = logging.getLogger(__name__)

"""
アカウントの無効化、退会処理に関するサービス

Userは削除しない(user.delete() は呼ばない)
これにより、以下を保持したまま退会処理を行うことができる

- Productの created_by
- MembershipとProductの関連
- SecurityEventのUser参照
- 組織所属の論理削除履歴

個人情報保護の観点からメールアドレスの匿名化も行う
"""

class LastOrganizationAdminError(ValidationError):
    """退会対象ユーザーが唯一のOrganization管理者である場合のエラー"""

class AccountService:
    """アカウント関連のサービスクラス"""

    @staticmethod
    @transaction.atomic
    def deactivate_account(*, user: User) -> User:
        """
        アカウントを退会させる。

        User自体は物理削除せず、Userを匿名化・無効化し、Membershipを論理削除する。
        """

        if user.deactivated_at is not None:
            return user

        #
        # まずはOrganizationの情報を取得しておく
        memberships = list(
                    Membership.objects.filter(user=user)
                                        .select_related("organization")
                                        .order_by("organization_id")
                )
                
        organization_ids = sorted({
                    membership.organization_id
                    for membership in memberships
                })

        # Organizationを固定順でロックし、同時退会による管理者消失を防ぐ
        # そして先にロックしておきたいので、list()で囲んで即時実行しておく
        _locked_organizations = list(
                                    Organization.objects
                                    .select_for_update()
                                    .filter(id__in=organization_ids)
                                    .order_by("id")
                                )
        #
        # ロック取得後に改めてMembershipを再取得する(念のための同時実行対策)
        memberships = list(
            Membership.objects
            .filter(user=user)
            .select_related("organization")
            .order_by("organization_id")
        )
        #
        # 各Membershipの管理者条件を再確認する
        for membership in memberships:
            if not membership.is_org_admin:
                continue
            if not membership.is_active:
                continue

            remaining_admin_exists = Membership.objects.filter(
                organization_id=membership.organization_id,
                is_org_admin=True,
                is_active=True,
            ).exclude(
                id=membership.id,
            ).exists()

            if not remaining_admin_exists:
                logger.warning(f"User {user.id} is the last admin of Organization {membership.organization_id}")
                #
                # 通常のValidationErrorと区別したいので、専用の例外クラスを使用する
                raise LastOrganizationAdminError(
                    "Organizationには1人以上の管理者が必要です。"
                )
        #
        # すべての管理者チェックを通過した後に、Membershipを論理削除する
        for membership in memberships:
            membership.delete()
        #
        # 同じメールアドレスを再利用できるようにUserを匿名化する
        # 基本的に元のメアドが分からないようにする
        # あくまで匿名化のための措置であり、元のメールアドレスは保持しない
        user.email = f"deleted-{uuid.uuid4()}@invalid.example"
        user.is_active = False
        user.deactivated_at = timezone.now()
        user.set_unusable_password()

        user.save(
            update_fields=[
                "email",
                "is_active",
                "deactivated_at",
                "password",
                "updated_at",
            ]
        )

        return user
