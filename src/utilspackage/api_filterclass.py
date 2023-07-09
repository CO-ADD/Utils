"""
Used by all Api filter view as base view
"""
from rest_framework import generics
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.pagination import PageNumberPagination
from rest_framework.authentication import SessionAuthentication
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework import permissions


class CustomPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 1000


class API_FilteredListView(generics.ListAPIView):
    queryset = None
    serializer_class = None
    model_fields = None
    order_by = None
    pagination_class = CustomPagination
    authentication_classes = [JWTAuthentication, SessionAuthentication]
    permission_classes = [permissions.IsAuthenticated]

   

    def get_serializer_context(self):
        context = super().get_serializer_context()
        return context
