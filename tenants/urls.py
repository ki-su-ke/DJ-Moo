from django.urls import path
from .views import (
    InviteMemberView,
    AcceptInvitationView,
    DeclineInvitationView,
    OrganizationMembersView,
)

app_name = 'tenants'

urlpatterns = [
    # メンバー招待関連
    path('invitations/', InviteMemberView.as_view(), name='invitations'),
    path('invitations/<uuid:token>/accept/', AcceptInvitationView.as_view(), name='accept_invitation'),
    path('invitations/<uuid:token>/decline/', DeclineInvitationView.as_view(), name='decline_invitation'),
    path('members/', OrganizationMembersView.as_view(), name='members'),
    path('members/<uuid:membership_id>/', OrganizationMembersView.as_view(), name='member'),
]
