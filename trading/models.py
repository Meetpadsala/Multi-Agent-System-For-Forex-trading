from django.db import models
from django.contrib.auth.models import User

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

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    favorite_pairs = models.JSONField(default=list)  # List of currency pairs
    risk_tolerance = models.CharField(max_length=20, choices=[('LOW', 'Low'), ('MEDIUM', 'Medium'), ('HIGH', 'High')], default='MEDIUM')

    def __str__(self):
        return f"{self.user.username}'s profile"
