from django.shortcuts import render, get_object_or_404
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.request import Request
from django.http import HttpResponse

from accounts.serializers import (
    ChangePasswordRequestSerializer,
    ChangePasswordSerializer,
    ChangeEmailRequestSerializer,
    ChangeEmailSerializer,
    UserProfileSerializer,
    DeleteAccountSerializer,
    DeleteMyAccountSerializer,
)
from accounts.models import (
    EmailVerificationToken, 
    EmailVerificationStatus,
    TokenType
)
from accounts.services import AccountService, LastOrganizationAdminError
from common.utils.emails import send_templated_email

import logging

logger = logging.getLogger(__name__)

User = get_user_model()



class ChangePasswordRequestView(APIView):
    """
    パスワード変更リクエストView
    POST /api/v1/auth/change-password-request/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        """ パスワード変更リクエスト """
        serializer = ChangePasswordRequestSerializer(data={})
        if serializer.is_valid():
            try:
                user = request.user

                # 既存の進行中のトークンを削除
                EmailVerificationToken.objects.filter(
                    user=user,
                    token_type=TokenType.PASSWORD_CHANGE,
                    status=EmailVerificationStatus.PENDING
                ).delete()

                # 新しいトークン作成
                token_obj = EmailVerificationToken.objects.create(
                    email=user.email,
                    token_type=TokenType.PASSWORD_CHANGE,
                    user=user
                )

                # パスワード変更URL生成
                change_url = request.build_absolute_uri(
                    reverse('accounts:change_password', kwargs={'token': token_obj.token})
                )

                # メール送信
                try:
                    subject = 'パスワード変更'
                    template_prefix = 'emails/password_change'
                    context = {
                        'change_url': change_url,
                    }
                    result = send_templated_email(
                        subject=subject,
                        template_prefix=template_prefix,
                        context=context,
                        recipient_list=[user.email],
                    )

                    if result:
                        logger.info(f"Password change email sent to {user.email}")
                        return Response(
                            {"message": "パスワード変更メールを送信しました。"},
                            status=status.HTTP_200_OK
                        )
                    else:
                        logger.error(f"Failed to send password change email to {user.email}")
                        return Response(
                            {"error": "メールの送信に失敗しました。"},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR
                        )
                except Exception as e:
                    logger.error(f"Failed to send password change email: {str(e)}", exc_info=True)
                    return Response(
                        {"error": "メールの送信に失敗しました。"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )

            except Exception as e:
                logger.error(f"Failed to create password change token: {str(e)}", exc_info=True)
                return Response(
                    {"error": "パスワード変更リクエストに失敗しました"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class ChangePasswordView(APIView):
    """
    パスワード変更View
    GET /api/v1/auth/change-password/{token}/  - HTMLフォーム返却
    POST /api/v1/auth/change-password/{token}/ - パスワード変更実行
    """
    permission_classes = []

    def get(self, request: Request, token: str) -> HttpResponse:
        """ パスワード変更フォーム返却 """
        try:
            token_obj = EmailVerificationToken.objects.get(token=token)

            if not token_obj.is_valid():
                if token_obj.status == EmailVerificationStatus.COMPLETED:
                    error_message = "このトークンは既に使用されています。"
                elif token_obj.status == EmailVerificationStatus.EXPIRED:
                    error_message = "トークンの有効期限が切れています。再度リクエストしてください。"
                else:
                    error_message = "無効なトークンです。"
                
                return render(
                    request,
                    'auth/error.html',
                    {'error_message': error_message}
                )

            # 有効なトークンならばパスワード変更フォームを表示
            return render(
                request,
                'auth/change_password.html',
                {
                    'token': token,
                }
            )

        except EmailVerificationToken.DoesNotExist:
            logger.error(f"Invalid token.", exc_info=True)
            return render(
                request,
                'auth/error.html',
                {'error_message': '無効なトークンです。'}
            )
    
    def post(self, request: Request, token: str) -> Response:
        """ パスワード変更実行 """
        serializer = ChangePasswordSerializer(data={'token': token, **request.data})
        if serializer.is_valid():
            try:
                token_obj = EmailVerificationToken.objects.get(token=serializer.validated_data['token'])
                user = token_obj.user
                password = serializer.validated_data['password']

                # パスワード変更
                user.set_password(password)
                user.save()

                # トークンをcompletedに更新
                token_obj.status = EmailVerificationStatus.COMPLETED
                token_obj.save()

                logger.info(f"Password changed for user {user.email}")

                return Response(
                    {"message": "パスワードを変更しました。"},
                    status=status.HTTP_200_OK
                )
            except Exception as e:
                logger.error(f"Failed to change password: {str(e)}", exc_info=True)
                return Response(
                    {"error": "パスワードの変更に失敗しました"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ChangeEmailRequestView(APIView):
    """
    メールアドレス変更リクエストView
    POST /api/v1/auth/change-email-request/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        """ メールアドレス変更リクエスト """

        serializer = ChangeEmailRequestSerializer(
            data=request.data,
            context={'request': request}
        )
        if serializer.is_valid():
            new_email = serializer.validated_data['new_email']

            try:
                user = request.user
                #
                # 既存の進行中のトークンを削除
                EmailVerificationToken.objects.filter(
                    user=user,
                    token_type=TokenType.EMAIL_CHANGE,
                    status=EmailVerificationStatus.PENDING
                ).delete()
                #
                # 新しいトークン作成
                token_obj = EmailVerificationToken.objects.create(
                    email=user.email,
                    token_type=TokenType.EMAIL_CHANGE,
                    user=user,
                    new_email=new_email
                )
                #
                # メールアドレス変更URL生成
                change_url = request.build_absolute_uri(
                    reverse('accounts:change_email', kwargs={'token': token_obj.token})
                )
                #
                # メール送信
                try:
                    subject = 'メールアドレス変更'
                    template_prefix = 'emails/email_change'
                    context = {
                        'current_email': user.email,
                        'new_email': new_email,
                        'change_url': change_url,
                    }
                    result = send_templated_email(
                        subject=subject,
                        template_prefix=template_prefix,
                        context=context,
                        recipient_list=[new_email],
                    )

                    if result:
                        logger.info(f"Email change request sent for {user.email} to {new_email}")
                        return Response(
                            {"message": "メールアドレス変更メールを送信しました。"},
                            status=status.HTTP_200_OK
                        )
                    else:
                        logger.error(f"Failed to send email change email to {new_email}")
                        return Response(
                            {"error": "メールの送信に失敗しました"},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR
                        )
                except Exception as e:
                    logger.error(f"Failed to send email change email: {str(e)}", exc_info=True)
                    return Response(
                        {"error": "メールの送信に失敗しました"},
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR
                    )

            except Exception as e:
                logger.error(f"Failed to create email change token: {str(e)}", exc_info=True)
                return Response(
                    {"error": "メールアドレス変更リクエストに失敗しました"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class ChangeEmailView(APIView):
    """
    メールアドレス変更View
    GET /api/v1/auth/change-email/{token}/ - 確認画面
    POST /api/v1/auth/change-email/{token}/ - 変更確定
    """
    permission_classes = []

    def get(self, request: Request, token: str) -> HttpResponse:
        serializer = ChangeEmailSerializer(data={'token': token})
        if not serializer.is_valid():
            return render(request, 'auth/error.html', {'error_message': '無効または期限切れのリンクです。'})

        token_obj = EmailVerificationToken.objects.select_related('user').get(token=token)
        return render(request, 'auth/email_change.html', {
            'token': token,
            'current_email': token_obj.user.email,
            'new_email': token_obj.new_email,
        })

    def post(self, request: Request, token: str) -> Response:
        """ メールアドレス変更実行 """
        serializer = ChangeEmailSerializer(data={'token': token})
        if serializer.is_valid():
            try:
                token_obj = EmailVerificationToken.objects.get(token=serializer.validated_data['token'])
                user = token_obj.user
                new_email = token_obj.new_email
                #
                # メールアドレス変更
                user.email = new_email
                user.save()
                #
                # トークンをcompletedに更新
                token_obj.status = EmailVerificationStatus.COMPLETED
                token_obj.save()

                logger.info(f"Email changed for user {user.email} to {new_email}")

                return Response(
                    {"message": "メールアドレスを変更しました。"},
                    status=status.HTTP_200_OK
                )

            except Exception as e:
                logger.error(f"Failed to change email: {str(e)}", exc_info=True)
                return Response(
                    {"error": "メールアドレスの変更に失敗しました"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserProfileView(APIView):
    """
    ユーザープロフィールView
    GET /api/v1/auth/me/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        """ ユーザープロフィール取得 """
        try:
            serializer = UserProfileSerializer(request.user)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Failed to get user profile: {str(e)}", exc_info=True)
            return Response(
                {"error": "プロフィールの取得に失敗しました。"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class DeleteMyAccountView(APIView):
    """
    自分自身のアカウントを退会する
    DELETE /api/v1/auth/me/delete/
    """
    permission_classes = [IsAuthenticated]

    def delete(self, request: Request) -> Response:
        serializer = DeleteMyAccountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            AccountService.deactivate_account(user=request.user)
        except LastOrganizationAdminError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_409_CONFLICT,
            )
        except ValidationError as e:
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"Failed to delete account: {str(e)}", exc_info=True)
            return Response(
                {"error": "退会処理に失敗しました。"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {"message": "退会しました。"},
            status=status.HTTP_204_NO_CONTENT,
        )


class DeleteAccountView(APIView):
    """
    staffによる指定ユーザーの退会処理
    DELETE /api/v1/auth/admin/delete-account/<user_id>/
    """
    permission_classes = [IsAdminUser]

    def delete(self, request: Request, user_id) -> Response:
        serializer = DeleteAccountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target_user = get_object_or_404(User, pk=user_id)

        try:
            AccountService.deactivate_account(user=target_user)
        except LastOrganizationAdminError as e:
            return Response({"error": str(e)}, status=status.HTTP_409_CONFLICT)
        except ValidationError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(status=status.HTTP_204_NO_CONTENT)

