from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from accounts.views import (
    RegisterView,
    VerifyView,
    CompleteRegistrationView,
    LoginView,
    LogoutView,
    ChangePasswordRequestView,
    ChangePasswordView,
    ChangeEmailRequestView,
    ChangeEmailView,
    UserProfileView,
    DeleteMyAccountView,
    DeleteAccountView,
)

# app_name = 'auth'
app_name = 'accounts'

urlpatterns = [
    # 認証関連
    path('register/', RegisterView.as_view(), name='register'),
    path('verify/<uuid:token>/', VerifyView.as_view(), name='verify'),
    path('complete/', CompleteRegistrationView.as_view(), name='complete'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),

    # カウント管理関連
    path('change-password-request/', ChangePasswordRequestView.as_view(), name='change_password_request'),
    path('change-password/<uuid:token>/', ChangePasswordView.as_view(), name='change_password'),
    path('change-email-request/', ChangeEmailRequestView.as_view(), name='change_email_request'),
    path('change-email/<uuid:token>/', ChangeEmailView.as_view(), name='change_email'),
    path('me/', UserProfileView.as_view(), name='user_profile'),
    path('me/delete/', DeleteMyAccountView.as_view(), name='delete_my_account'),
    path('admin/delete-account/<uuid:user_id>/', DeleteAccountView.as_view(), name='delete_account'),
    
    # SimpleJWT標準エンドポイント
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]

