import os
import sys
import django

# Add the project directory to the path
sys.path.insert(0, 'c:/Users/HP/VSCODE Programming Languages/Multi-Agent-System-For-Forex-trading')

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'forex_trading.settings')
django.setup()

from django.contrib.auth.models import User

# Update user 'mas' to be admin
try:
    user = User.objects.get(username='mas')
    user.is_staff = True
    user.is_superuser = True
    user.save()
    print(f"SUCCESS! User '{user.username}' now has is_staff=True and is_superuser=True")
except User.DoesNotExist:
    print(f"ERROR: User 'mas' not found!")
except Exception as e:
    print(f"ERROR: {e}")
