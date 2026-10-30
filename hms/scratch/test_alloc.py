import requests

login_res = requests.post(
    "http://127.0.0.1:8000/auth/login",
    data={"username": "admin@hms.com", "password": "Admin@123"}
)
token = login_res.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

hotels = requests.get("http://127.0.0.1:8000/hotels").json()["data"]
hotel_id = hotels[0]["id"]

# Fetch existing rooms
rooms = requests.get(f"http://127.0.0.1:8000/rooms?hotel_id={hotel_id}", headers=headers).json().get("data", [])
print(f"Total rooms: {len(rooms)}")
room_999 = next((r for r in rooms if r["room_number"] == "Suite 999"), rooms[0] if rooms else None)

# Fetch bookings
bookings = requests.get(f"http://127.0.0.1:8000/bookings?hotel_id={hotel_id}", headers=headers).json().get("data", [])

if bookings and room_999:
    bk = bookings[0]
    print(f"Allocating room '{room_999['room_number']}' (ID: {room_999['id']}) to booking {bk['id']}...")
    alloc_res = requests.post(
        "http://127.0.0.1:8000/booking-rooms",
        headers=headers,
        data={
            "booking_id": bk["id"],
            "room_id": room_999["id"]
        }
    )
    print("Allocate result:", alloc_res.status_code, alloc_res.json().get("message"))

    # Express check-in
    update_res = requests.put(
        f"http://127.0.0.1:8000/bookings/{bk['id']}",
        headers=headers,
        data={"status": "in_house"}
    )
    print("Express check-in result:", update_res.status_code, update_res.json().get("message"))
