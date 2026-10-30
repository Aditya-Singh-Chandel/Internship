import requests, json

login_res = requests.post(
    "http://127.0.0.1:8000/auth/login",
    data={"username": "admin@hms.com", "password": "Admin@123"}
)
token = login_res.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

bookings = requests.get("http://127.0.0.1:8000/bookings", headers=headers).json().get("data", [])
if bookings:
    print("Booking keys:", list(bookings[0].keys()))
    print("Sample booking:")
    print(json.dumps(bookings[0], indent=2, default=str))
