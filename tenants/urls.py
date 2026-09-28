from django.urls import path
from .views import (
    InviteMemberView,
    AcceptInvitationView,
    DeclineInvitationView,
)

app_name = 'tenants'

urlpatterns = [
    # メンバー招待関連
    path('invitations/', InviteMemberView.as_view(), name='invitations'),
    path('invitations/<uuid:token>/accept/', AcceptInvitationView.as_view(), name='accept_invitation'),
    path('invitations/<uuid:token>/decline/', DeclineInvitationView.as_view(), name='decline_invitation'),
]
