from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('search/', views.search_pairs, name='search_pairs'),
    path('logs/', views.agent_logs, name='agent_logs'),
    path('api/forex/<str:symbol>/', views.ForexDataAPI.as_view(), name='forex_data_api'),
    path('api/logs/', views.AgentLogsAPI.as_view(), name='agent_logs_api'),
    path('api/agent-status/', views.AgentStatusAPI.as_view(), name='agent_status_api'),
    path('api/high-risk-pairs/', views.HighRiskPairsAPI.as_view(), name='high_risk_pairs_api'),
]
