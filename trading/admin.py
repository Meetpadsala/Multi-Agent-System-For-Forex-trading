from django.contrib import admin
from .models import ForexData, Prediction, AgentLog, UserProfile

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
    list_display = ('user', 'risk_tolerance')
    list_filter = ('risk_tolerance',)
