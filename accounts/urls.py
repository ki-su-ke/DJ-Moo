from django.urls import path
from rest_framework_simplejwt.views import (
    TokenRefreshView,
)

from accounts.views import (
    RegisterView,
    VerifyView,
    CompleteRegistrationView,
    LoginView,
    LogoutView,
)

app_name = 'auth'

urlpatterns = [
    # 認証関連
    path('register/', RegisterView.as_view(), name='register'),
    path('verify/<uuid:token>/', VerifyView.as_view(), name='verify'),
    path('complete/', CompleteRegistrationView.as_view(), name='complete'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    
    # SimpleJWT標準エンドポイント
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]

