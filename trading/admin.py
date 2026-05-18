
from django.contrib import admin
from .models import ForexData, Prediction, AgentLog, UserProfile, AgentStatus, RiskAnalysis

@admin.register(ForexData)
class ForexDataAdmin(admin.ModelAdmin):
    list_display = ('symbol', 'timestamp', 'close_price', 'volume')
    list_filter = ('symbol', 'timestamp')
    search_fields = ('symbol',)

@admin.register(Prediction)
class PredictionAdmin(admin.ModelAdmin):
    list_display = ('symbol', 'timestamp', 'predicted_price', 'trend', 'confidence')
    list_filter = ('symbol', 'trend')

@admin.register(AgentLog)
class AgentLogAdmin(admin.ModelAdmin):
    list_display = ('agent_name', 'timestamp', 'action')
    list_filter = ('agent_name', 'timestamp')
    search_fields = ('action', 'result')

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'risk_tolerance', 'account_balance')
    list_filter = ('risk_tolerance',)

@admin.register(AgentStatus)
class AgentStatusAdmin(admin.ModelAdmin):
    list_display = ('agent_name', 'is_active', 'status', 'last_run', 'updated_at')
    list_filter = ('status', 'is_active')
    search_fields = ('agent_name', 'message')
    readonly_fields = ('updated_at',)

@admin.register(RiskAnalysis)
class RiskAnalysisAdmin(admin.ModelAdmin):
    list_display = ('symbol', 'timestamp', 'risk_score', 'risk_level')
    list_filter = ('symbol', 'risk_level', 'timestamp')
    search_fields = ('symbol',)

