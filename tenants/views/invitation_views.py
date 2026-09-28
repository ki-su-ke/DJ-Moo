# from django.shortcuts import render
# from django.conf import settings
from django.contrib.auth import get_user_model
# from django.template.loader import render_to_string
# from django.core.mail import send_mail
from django.urls import reverse
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
# from django.http import HttpResponse

from tenants.serializers import (
    InviteMemberSerializer,
    AcceptInvitationSerializer,
    DeclineInvitationSerializer,
    InvitationSerializer
)
from tenants.models import (
    MembershipInvitation, InvitationStatus,
    Membership, Organization, Role
)
from tenants.constants import RoleDefaultName
from common.utils.emails import send_templated_email

import logging

logger = logging.getLogger(__name__)

User = get_user_model()


# Create your views here.

class InviteMemberView(APIView):
    """
    メンバー招待View
    POST /api/v1/{organization_slug}/invitations/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, organization_slug: str) -> Response:
        """組織の招待一覧を取得する"""
        try:
            organization = Organization.objects.get(slug=organization_slug)
            membership = request.user.memberships.filter(
                organization=organization,
                is_org_admin=True,
                is_active=True,
            ).first()

            if not membership:
                return Response(
                    {"error": "組織管理者のみが閲覧できます"},
                    status=status.HTTP_403_FORBIDDEN,
                )

            invitations = MembershipInvitation.objects.filter(
                organization=organization,
            ).order_by('-created_at')
            serializer = InvitationSerializer(invitations, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Organization.DoesNotExist:
            return Response(
                {"error": "組織情報を取得できませんでした。"},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            logger.error(f"Failed to list invitations: {str(e)}", exc_info=True)
            return Response(
                {"error": "招待一覧の取得に失敗しました"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def post(self, request: Request, organization_slug: str) -> Response:
        """ メンバーを招待する """
        serializer = InviteMemberSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            role_id = serializer.validated_data.get('role_id')

            try:
                organization = Organization.objects.get(slug=organization_slug)

                # 招待者のMembershipを取得
                inviter_membership = request.user.memberships.filter(
                                            organization=organization,
                                            is_org_admin=True,
                                            is_active=True
                                        ).first()
                
                if not inviter_membership:
                    return Response(
                        {"error": "組織管理者のみが招待できます。"},
                        status=status.HTTP_403_FORBIDDEN
                    )
                
                #
                # 権限が指定されていない場合はデフォルト権限(Viewer)を使用
                if role_id is None:
                    role = Role.objects.get(
                        organization=organization,
                        name=RoleDefaultName.VIEWER
                    )
                else:
                    role = Role.objects.get(id=role_id, organization=organization)
                
                # 招待を作成
                invitation = MembershipInvitation.objects.create(
                    email=email,
                    organization=organization,
                    role=role,
                    invited_by=inviter_membership
                )

                # 招待URL生成
                accept_url = request.build_absolute_uri(
                    reverse('tenants:accept_invitation', kwargs={
                        'organization_slug': organization.slug,
                        'token': invitation.token,
                    })
                )
                decline_url = request.build_absolute_uri(
                    reverse('tenants:decline_invitation', kwargs={
                        'organization_slug': organization.slug,
                        'token': invitation.token,
                    })
                )

                # メール送信
                try:
                    subject = f'{organization.name} からの招待'
                    # message = f'以下のURLをクリックして招待に応答してください:\n\n承認: {accept_url}\n拒否: {decline_url}'
                    template_prefix = 'emails/invitation' # emailテンプレートのプレフィックスとしてパス/ファイル名部分を渡す
                    context = {
                        'organization_name': organization.name,
                        'accept_url': accept_url,
                        'decline_url': decline_url
                    }
                    emails = [email,]
                    result = send_templated_email(
                                subject=subject,
                                template_prefix=template_prefix,
                                context=context,
                                recipient_list=emails,
                            )
                    if result:
                        logger.info(f"Invitation sent to {email} for organization {organization.name}")

                        return Response(
                                    {"message": "招待メールを送信しました"},
                                    status=status.HTTP_201_CREATED
                                )
                    else:
                        # 送信失敗時の処理
                        logger.error(f"Failed to send invitation email to {email}")
                        return Response(
                                    {"error": "メールの送信に失敗しました"},
                                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                                )
                except Exception as e:
                    logger.error(f"Failed to send invitation email to {email}", exc_info=True)
                    return Response(
                                {"error": "メールの送信に失敗しました"},
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR
                            )
            except Organization.DoesNotExist:
                logger.error(f"Organization not found.", exc_info=True)
                return Response(
                            {"error": "組織情報を取得できませんでした。"},
                            status=status.HTTP_404_NOT_FOUND
                        )
            except Role.DoesNotExist as e:
                logger.error(f"Role not found: {str(e)}", exc_info=True)
                return Response(
                            {"error": "権限を取得できませんでした。"},
                            status=status.HTTP_404_NOT_FOUND
                        )
            except Exception as e:
                logger.error(f"Failed to create invitation for {email}: {str(e)}", exc_info=True)
                return Response(
                            {"error": "招待の作成に失敗しました"},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR
                        )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
class AcceptInvitationView(APIView):
    """
    招待承認View
    POST /api/v1/{organization_slug}/invitations/{token}/accept/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, organization_slug: str, token: str) -> Response:
        """ 招待を承認する """
        serializer = AcceptInvitationSerializer(data={'token': token})
        if serializer.is_valid():
            try:
                invitation = MembershipInvitation.objects.get(
                    token=token,
                    organization__slug=organization_slug,
                )

                # 既存ユーザーチェック
                user = request.user
                #
                # 既に同じOrganizationに所属しているかチェック
                if Membership.objects.filter(
                            user=user,
                            organization=invitation.organization
                        ).exists():
                    return Response(
                        {"error": "既にこの組織に所属しています"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                #
                # Membershipを作成
                membership = Membership.objects.create(
                    user=user,
                    organization=invitation.organization,
                    scope_type='all',
                    is_org_admin=False, # 招待なので最初はFalse
                    is_active=True
                )
                #
                # 権限を付与
                membership.roles.add(invitation.role)
                #
                # 招待をacceptedに更新
                invitation.status = InvitationStatus.ACCEPTED
                invitation.save()

                logger.info(f"User {user.email} accepted invitation to {invitation.organization.name}")
                
                return Response(
                    {"message": "招待を承認しました"},
                    status=status.HTTP_200_OK
                )
            except MembershipInvitation.DoesNotExist:
                return Response(
                    {"error": "招待が見つかりません。"},
                    status=status.HTTP_404_NOT_FOUND
                )
            except Exception as e:
                logger.error(f"Failed to accept invitation: {str(e)}", exc_info=True)
                return Response(
                    {"error": "招待の承認に失敗しました"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )


        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
class DeclineInvitationView(APIView):
    """
    招待拒否View
    POST /api/v1/{organization_slug}/invitations/{token}/decline/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request, organization_slug: str, token: str) -> Response:
        """ 招待を拒否する """
        serializer = DeclineInvitationSerializer(data={'token': token})
        if serializer.is_valid():
            try:
                invitation = MembershipInvitation.objects.get(
                    token=token,
                    organization__slug=organization_slug,
                )
                #
                # 招待をdeclinedに更新
                invitation.status = InvitationStatus.DECLINED
                invitation.save()

                logger.info(f"Invitation for {invitation.email} declined")

                return Response(
                    {"message": "招待を拒否しました"},
                    status=status.HTTP_200_OK
                )
            except MembershipInvitation.DoesNotExist:
                return Response(
                    {"error": "招待が見つかりません。"},
                    status=status.HTTP_404_NOT_FOUND
                )
            except Exception as e:
                logger.error(f"Failed to decline invitation: {str(e)}", exc_info=True)
                return Response(
                    {"error": "招待の拒否に失敗しました"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
