import requests

login_res = requests.post(
    "http://127.0.0.1:8000/auth/login",
    data={"username": "admin@hms.com", "password": "Admin@123"}
)
print("Login status:", login_res.status_code)
token = login_res.json().get("access_token")

hotels_res = requests.get("http://127.0.0.1:8000/hotels")
hotels = hotels_res.json().get("data", [])
h = hotels[0]
print(f"Testing sync for hotel: {h['name']} ({h['id']})")

sync_res = requests.post(
    f"http://127.0.0.1:8000/hotels/{h['id']}/documents/sync",
    headers={"Authorization": f"Bearer {token}"}
)
print("Sync status:", sync_res.status_code)
print("Sync response:", sync_res.json())
