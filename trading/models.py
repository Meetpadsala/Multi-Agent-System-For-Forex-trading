from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class ForexData(models.Model):
    symbol = models.CharField(max_length=10)  # e.g., 'EURUSD'
    timestamp = models.DateTimeField()
    open_price = models.DecimalField(max_digits=10, decimal_places=5)
    high_price = models.DecimalField(max_digits=10, decimal_places=5)
    low_price = models.DecimalField(max_digits=10, decimal_places=5)
    close_price = models.DecimalField(max_digits=10, decimal_places=5)
    volume = models.BigIntegerField()

    class Meta:
        unique_together = ('symbol', 'timestamp')
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.symbol} at {self.timestamp}"

class Prediction(models.Model):
    symbol = models.CharField(max_length=10)
    timestamp = models.DateTimeField(auto_now_add=True)
    predicted_price = models.DecimalField(max_digits=10, decimal_places=5)
    trend = models.CharField(max_length=10, choices=[('UP', 'Up'), ('DOWN', 'Down')])
    confidence = models.DecimalField(max_digits=5, decimal_places=2)  # 0-100

    def __str__(self):
        return f"Prediction for {self.symbol}: {self.trend} ({self.confidence}%)"

class AgentLog(models.Model):
    agent_name = models.CharField(max_length=50)
    action = models.TextField()
    result = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.agent_name} - {self.timestamp}"

class AgentStatus(models.Model):
    """Model to track the status of each agent in the system"""
    agent_name = models.CharField(max_length=50, unique=True)
    is_active = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=[
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
        ('ERROR', 'Error'),
        ('RUNNING', 'Running')
    ], default='INACTIVE')
    last_run = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True, default='')
    message = models.TextField(blank=True, default='')
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.agent_name}: {self.status}"

    @classmethod
    def update_agent_status(cls, agent_name, is_active, status='ACTIVE', message='', last_error=''):
        """Update the status of an agent"""
        obj, created = cls.objects.update_or_create(
            agent_name=agent_name,
            defaults={
                'is_active': is_active,
                'status': status,
                'message': message,
                'last_error': last_error,
                'last_run': timezone.now() if is_active else None
            }
        )
        return obj

    @classmethod
    def get_all_agents_status(cls):
        """Get status of all agents"""
        agents = ['DataAgent', 'TechnicalAnalysisAgent', 'PredictionAgent', 'SentimentAgent', 'RiskManagementAgent', 'DecisionAgent']
        status_list = []
        
        for agent_name in agents:
            try:
                agent_status = cls.objects.get(agent_name=agent_name)
                status_list.append({
                    'name': agent_status.agent_name,
                    'is_active': agent_status.is_active,
                    'status': agent_status.status,
                    'last_run': agent_status.last_run.isoformat() if agent_status.last_run else None,
                    'message': agent_status.message,
                    'last_error': agent_status.last_error
                })
            except cls.DoesNotExist:
                status_list.append({
                    'name': agent_name,
                    'is_active': False,
                    'status': 'INACTIVE',
                    'last_run': None,
                    'message': 'Agent not initialized',
                    'last_error': ''
                })
        
        return status_list

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    favorite_pairs = models.JSONField(default=list)  # List of currency pairs
    risk_tolerance = models.CharField(max_length=20, choices=[('LOW', 'Low'), ('MEDIUM', 'Medium'), ('HIGH', 'High')], default='MEDIUM')
    account_balance = models.DecimalField(max_digits=15, decimal_places=2, default=10000.00)  # Default $10,000

    def __str__(self):
        return f"{self.user.username}'s profile"


class RiskAnalysis(models.Model):
    """Model to store comprehensive risk analysis results"""
    symbol = models.CharField(max_length=10)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # Value at Risk metrics
    var_95 = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True, help_text="Value at Risk at 95% confidence")
    var_99 = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True, help_text="Value at Risk at 99% confidence")
    cvar = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True, help_text="Conditional Value at Risk (Expected Shortfall)")
    
    # Risk metrics
    sharpe_ratio = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Sharpe Ratio")
    max_drawdown = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True, help_text="Maximum Drawdown as percentage")
    volatility = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True, help_text="Annualized Volatility")
    
    # ATR-based levels
    atr = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True, help_text="Average True Range")
    atr_stop_loss = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True, help_text="ATR-based Stop Loss")
    atr_take_profit = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True, help_text="ATR-based Take Profit")
    
    # Position sizing
    position_size = models.DecimalField(max_digits=10, decimal_places=5, null=True, blank=True, help_text="Recommended Position Size (lots)")
    risk_per_trade = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Risk per trade as percentage")
    
    # Risk/Reward
    risk_reward_ratio = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, help_text="Risk/Reward Ratio")
    
    # Overall risk score
    risk_score = models.DecimalField(max_digits=5, decimal_places=2, default=50.0, help_text="Overall Risk Score (0-100)")
    risk_level = models.CharField(max_length=20, choices=[
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('EXTREME', 'Extreme')
    ], default='MEDIUM')

    class Meta:
        ordering = ['-timestamp']
        unique_together = ('symbol', 'timestamp')

    def __str__(self):
        return f"Risk Analysis for {self.symbol} at {self.timestamp}"
