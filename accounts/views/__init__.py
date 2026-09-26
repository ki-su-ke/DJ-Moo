from .auth_views import (
    RegisterView,
    VerifyView,
    CompleteRegistrationView,
    LoginView,
    LogoutView,
)

from .account_views import (
    ChangePasswordRequestView,
    ChangePasswordView,
    ChangeEmailRequestView,
    ChangeEmailView,
    UserProfileView,
)
 
__all__ = [
    'RegisterView',
    'VerifyView',
    'CompleteRegistrationView',
    'LoginView',
    'LogoutView',
    'ChangePasswordRequestView',
    'ChangePasswordView',
    'ChangeEmailRequestView',
    'ChangeEmailView',
    'UserProfileView',
]
