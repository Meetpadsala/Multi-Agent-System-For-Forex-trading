from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Password reset URLs
    path('password-reset/', 
         auth_views.PasswordResetView.as_view(template_name='trading/password_reset.html',
                                             success_url='done/'),
         name='password_reset'),
    path('password-reset/done/', 
         auth_views.PasswordResetDoneView.as_view(template_name='trading/password_reset_done.html'),
         name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(template_name='trading/password_reset_confirm.html'),
         name='password_reset_confirm'),
    path('password-reset-complete/',
         auth_views.PasswordResetCompleteView.as_view(template_name='trading/password_reset_complete.html'),
         name='password_reset_complete'),
    
    path('dashboard/', views.dashboard, name='dashboard'),
    path('search/', views.search_pairs, name='search_pairs'),
    path('logs/', views.agent_logs, name='agent_logs'),
    path('api/forex/<str:symbol>/', views.ForexDataAPI.as_view(), name='forex_data_api'),
    path('api/logs/', views.AgentLogsAPI.as_view(), name='agent_logs_api'),
    path('api/agent-status/', views.AgentStatusAPI.as_view(), name='agent_status_api'),
    path('api/high-risk-pairs/', views.HighRiskPairsAPI.as_view(), name='high_risk_pairs_api'),
    # New Time & Filter API endpoints
    path('api/live-data/', views.LiveDataAPI.as_view(), name='live_data_api'),
    path('api/history-data/', views.HistoryDataAPI.as_view(), name='history_data_api'),
    path('api/chart-data/', views.ChartDataAPI.as_view(), name='chart_data_api'),
    
    # Custom Admin Panel URLs - using 'admin-panel/' to avoid conflict with Django admin
    path('admin-panel/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-panel/agents/', views.admin_agents, name='admin_agents'),
    path('admin-panel/agents/create/', views.admin_create_agent, name='admin_create_agent'),
    path('admin-panel/agents/update/<int:pk>/', views.admin_update_agent, name='admin_update_agent'),
    path('admin-panel/agents/delete/<int:pk>/', views.admin_delete_agent, name='admin_delete_agent'),
    path('admin-panel/agents/toggle/<str:agent_name>/', views.admin_toggle_agent, name='admin_toggle_agent'),
    path('admin-panel/forex-data/', views.admin_forex_data, name='admin_forex_data'),
    path('admin-panel/predictions/', views.admin_predictions, name='admin_predictions'),
    path('admin-panel/risk-analysis/', views.admin_risk_analysis, name='admin_risk_analysis'),
    path('admin-panel/users/', views.admin_users, name='admin_users'),
    path('admin-panel/logs/', views.admin_logs, name='admin_logs'),
]
