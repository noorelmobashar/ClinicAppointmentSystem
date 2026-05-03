from django.urls import path
from . import views

urlpatterns = [
    path('users/', views.UserListView.as_view(), name='admin-users'),
    path('users/create/', views.UserCreateView.as_view(), name='admin-user-create'),
    path('users/<int:pk>/edit/', views.UserEditView.as_view(), name='admin-user-edit'),
    path('users/<int:pk>/toggle-active/', views.UserToggleActiveView.as_view(), name='admin-user-toggle'),
    path('analytics/export/', views.AnalyticsExportView.as_view(), name='admin-analytics-export'),
]
