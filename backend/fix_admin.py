
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'forex_trading.settings')
django.setup()

from django.contrib.auth.models import User

# Check and set is_staff for user 'mas'
try:
    user = User.objects.get(username='mas')
    print(f'Current is_staff: {user.is_staff}')
    print(f'Current is_superuser: {user.is_superuser}')
    
    user.is_staff = True
    user.is_superuser = True
    user.save()
    
    # Verify
    user = User.objects.get(username='mas')
    print(f'After update - is_staff: {user.is_staff}')
    print(f'After update - is_superuser: {user.is_superuser}')
    print('Success! User "mas" now has full admin access.')
except User.DoesNotExist:
    print('Error: User "mas" not found')
except Exception as e:
    print(f'Error: {e}')

