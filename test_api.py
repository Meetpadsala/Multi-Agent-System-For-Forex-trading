import requests

url = 'http://127.0.0.1:8000/api/forex/EURUSD/'
try:
    response = requests.get(url)
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
except Exception as e:
    print(f"Error: {e}")
