from django.urls import path, include
from rest_framework.decorators import api_view
from rest_framework.response import Response

@api_view(['GET'])
def api_root(request):
    return Response({
        'message': 'DJ-MOO API v1',
        'endpoints': {
            'auth': '/api/v1/auth/',
            'tenants': '/api/v1/tenants/',
        }
    })

urlpatterns = [
    path('', api_root),
    path('auth/', include('accounts.urls')),
    path('tenants/', include('tenants.urls')),
]