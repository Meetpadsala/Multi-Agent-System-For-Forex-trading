
"""
URL configuration for forex_trading project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path, include
from django.contrib import admin
from trading import views as trading_views

urlpatterns = [
    # Default Django admin panel. It's recommended to use a unique path for it.
    path('super-admin/', admin.site.urls),

    # Custom Admin Panel URLs
    path('admin/', trading_views.admin_dashboard, name='admin_dashboard'),
    path('admin/agents/', trading_views.admin_agents, name='admin_agents'),
    path('admin/forex-data/', trading_views.admin_forex_data, name='admin_forex_data'),
    path('admin/predictions/', trading_views.admin_predictions, name='admin_predictions'),
    path('admin/risk-analysis/', trading_views.admin_risk_analysis, name='admin_risk_analysis'),
    path('admin/users/', trading_views.admin_users, name='admin_users'),
    path('admin/logs/', trading_views.admin_logs, name='admin_logs'),
    path('admin/toggle-agent/<str:agent_name>/', trading_views.admin_toggle_agent, name='admin_toggle_agent'),

    # Main application URLs
    path('', include('trading.urls')),
]

# Change Django Admin title
admin.site.site_header = "Forex Trading Admin"
admin.site.site_title = "Forex Trading Admin Portal"
admin.site.index_title = "Welcome to the Forex Trading Admin Portal"
