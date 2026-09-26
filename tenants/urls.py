from django.urls import path
from .views import (
    InviteMemberView,
    AcceptInvitationView,
    DeclineInvitationView,
    ListInvitationsView,
)

app_name = 'tenants'

urlpatterns = [
    # メンバー招待関連
    path('organizations/<uuid:org_id>/invite/', InviteMemberView.as_view(), name='invite_member'),
    path('organizations/<uuid:org_id>/invitations/', ListInvitationsView.as_view(), name='list_invitations'),
    path('invitations/<uuid:token>/accept/', AcceptInvitationView.as_view(), name='accept_invitation'),
    path('invitations/<uuid:token>/decline/', DeclineInvitationView.as_view(), name='decline_invitation'),
]
