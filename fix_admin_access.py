import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'forex_trading.settings')
django.setup()

from django.contrib.auth.models import User

# Try to find and update the user
users = User.objects.all()
print("Available users:")
for u in users:
    print(f"  - {u.username} (is_staff={u.is_staff}, is_superuser={u.is_superuser})")

# Find a user and make them admin
if users:
    user = users[0]
    user.is_staff = True
    user.is_superuser = True
    user.save()
    print(f"\nUpdated user '{user.username}':")
    print(f"  is_staff = {user.is_staff}")
    print(f"  is_superuser = {user.is_superuser}")
else:
    print("No users found!")
