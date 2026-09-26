# 認証関連のView
from django.shortcuts import render
from django.conf import settings
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.core.mail import send_mail
from django.urls import reverse
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.request import Request
from rest_framework.response import Response
from django.http import HttpResponse # DRFであってもrenderで返すなら型ヒントはこっち
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from accounts.serializers import (
    RegisterSerializer,
    CompleteRegistrationSerializer,
    LoginSerializer
)
from accounts.models import EmailVerificationToken, EmailVerificationStatus
from tenants.services import OrganizationService

import logging

logger = logging.getLogger(__name__)

User = get_user_model()



class RegisterView(APIView):
    """
    メールアドレス登録View

    POST /api/auth/register/
    """
    permission_classes = [] # 認証不要

    def post(self, request: Request) -> Response:
        """
        メールアドレス登録
        """
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']

            # トークン作成
            token_obj = EmailVerificationToken.objects.create(email=email)

            # 認証URL生成
            verify_url = request.build_absolute_uri(
                reverse('accounts:verify', kwargs={'token': token_obj.token})
            )

            # メール送信
            try:
                subject = 'メールアドレス認証'
                message = f'以下のURLをクリックして登録を完了してください:\n\n{verify_url}'
                html_message = render_to_string(
                    'emails/verification.html',
                    {'verify_url': verify_url}
                )

                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    html_message=html_message,
                    fail_silently=False
                )

                logger.info(f"Verification email sent to {email}")

                return Response(
                    {"message": "認証メールを送信しました。メールをご確認ください。"},
                    status=status.HTTP_201_CREATED
                )
            except Exception as e:
                logger.error(f"Failed to send email to {email}: {str(e)}")
                return Response(
                    {"error": "メールの送信に失敗しました。後でもう一度お試しください。"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VerifyView(APIView):
    """
    認証URL確認View(HTMLフォーム返却)
    GET /api/auth/verify/{token}/
    """
    permission_classes = [] # 認証不要

    def get(self, request: Request, token: str) -> HttpResponse:
        """
        """
        try:
            token_obj = EmailVerificationToken.objects.get(token=token)

            if not token_obj.is_valid():
                if token_obj.status == EmailVerificationStatus.COMPLETED:
                    error_message = "このトークンは既に使用されています。"
                elif token_obj.status == EmailVerificationStatus.EXPIRED:
                    error_message = "トークンの有効期限が切れています。再度登録してください。"
                else:
                    error_message = "無効なトークンです。"
                
                return render(
                    request,
                    'auth/error.html',
                    {'error_message': error_message}
                )

            # 有効なトークンの場合、登録完了フォームを表示
            return render(
                request,
                'auth/complete_registration.html',
                {
                    'token': token,
                    'email': token_obj.email,
                }
            )
        except EmailVerificationToken.DoesNotExist:
            return render(
                request,
                'auth/error.html',
                {'error_message': '無効なトークンです。'}
            )


class CompleteRegistrationView(APIView):
    """
    登録完了View(パスワード設定 + 組織作成 + JWT発行)

    POST /api/auth/complete/
    """
    permission_classes = []  # 認証不要

    def post(self, request: Request) -> Response:
        serializer = CompleteRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            token = serializer.validated_data['token']
            email = serializer.validated_data['email']
            password = serializer.validated_data['password']
            organization_name = serializer.validated_data['organization_name']
            organization_slug = serializer.validated_data['organization_slug']

            try:
                # トークン取得
                token_obj = EmailVerificationToken.objects.get(token=token)

                # User作成
                user = User.objects.create_user(
                    email=email,
                    password=password
                )
                logger.info(f"User created: {email}")

                # Organization作成
                organization = OrganizationService.create_organization(
                    user=user,
                    name=organization_name,
                    slug=organization_slug
                )
                logger.info(f"Organization created: {organization.slug}")

                # トークンをcompletedに更新
                token_obj.status = EmailVerificationStatus.COMPLETED
                token_obj.save()

                # JWT発行
                refresh = RefreshToken.for_user(user)

                return Response(
                    {
                        'access': str(refresh.access_token),
                        'refresh': str(refresh),
                        'user': {
                            'id': str(user.id),
                            'email': user.email,
                        },
                        'organization': {
                            'id': str(organization.id),
                            'name': organization.name,
                            'slug': organization.slug,
                        }
                    },
                    status=status.HTTP_201_CREATED
                )

            except Exception as e:
                logger.error(f"Failed to complete registration for {email}: {str(e)}")
                return Response(
                    {"error": "登録の完了に失敗しました。後でもう一度お試しください。"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    """
    ログインView(メール+パスワード → JWT発行)
    POST /api/auth/login/
    """
    permission_classes = [] # 認証不要

    def post(self, request: Request) -> Response:
        serializer = LoginSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            user = serializer.validated_data['user']

            # JWT発行
            refresh = RefreshToken.for_user(user)

            logger.info(f"User logged in: {user.email}")
            
            return Response(
                {
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                    'user': {
                        'id': str(user.id),
                        'email': user.email,
                    }
                },
                status=status.HTTP_200_OK
            )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LogoutView(APIView):
    """
    ログアウトView(トークン無効化)
    POST /api/auth/logout/
    """
    permission_classes = []  # 認証不要（トークン検証は後で行う）

    def post(self, request: Request) -> Response:
        try:
            refresh_token = request.data.get('refresh')
            if not refresh_token:
                return Response(
                    {"error": "refresh_token is required"},
                    status=status.HTTP_400_BAD_REQUEST
                )

            token = RefreshToken(refresh_token)
            token.blacklist()

            logger.info("User logged out")

            return Response(
                {"message": "ログアウトしました"},
                status=status.HTTP_200_OK
            )

        except TokenError as e:
            logger.error(f"Token error during logout: {str(e)}")
            return Response(
                {"error": "無効なトークンです"},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error during logout: {str(e)}")
            return Response(
                {"error": "ログアウトに失敗しました"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

