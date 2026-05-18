from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import AgentStatus

AGENT_CHOICES = [
    ('DataAgent', 'DataAgent'),
    ('TechnicalAnalysisAgent', 'TechnicalAnalysisAgent'),
    ('PredictionAgent', 'PredictionAgent'),
    ('SentimentAgent', 'SentimentAgent'),
    ('RiskManagementAgent', 'RiskManagementAgent'),
    ('DecisionAgent', 'DecisionAgent'),
    ('CustomAgent', 'Custom Agent (Other)'),
]

class RegistrationForm(UserCreationForm):
    """Custom registration form with email field"""
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email address'
        })
    )
    
    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')
    
    def __init__(self, *args, **kwargs):
        super(RegistrationForm, self).__init__(*args, **kwargs)
        # Add form-control class to all fields
        self.fields['username'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Choose a username'
        })
        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Create a password'
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Confirm your password'
        })
    
    def save(self, commit=True):
        user = super(RegistrationForm, self).save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user

class AgentStatusForm(forms.ModelForm):
    class Meta:
        model = AgentStatus
        fields = ['agent_name', 'is_active', 'status', 'message', 'last_error']
        widgets = {
            'agent_name': forms.Select(choices=AGENT_CHOICES),
            'status': forms.Select(choices=AgentStatus._meta.get_field('status').choices),
            'is_active': forms.CheckboxInput(),
            'message': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'last_error': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        }
        labels = {
            'agent_name': 'Agent Name',
            'is_active': 'Is Active',
            'status': 'Status',
            'message': 'Status Message',
            'last_error': 'Last Error',
        }
