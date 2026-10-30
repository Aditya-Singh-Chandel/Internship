import requests

login_res = requests.post(
    "http://127.0.0.1:8000/auth/login",
    data={"username": "admin@hms.com", "password": "Admin@123"}
)
token = login_res.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# 1. Get first hotel
hotels = requests.get("http://127.0.0.1:8000/hotels").json()["data"]
hotel = hotels[0]
hotel_id = hotel["id"]
print(f"Working with hotel: {hotel['name']}")

# 2. Get room types
room_types = requests.get(f"http://127.0.0.1:8000/room-types?hotel_id={hotel_id}", headers=headers).json().get("data", [])
print(f"Room types found: {len(room_types)}")
rt_id = room_types[0]["id"] if room_types else None

# 3. Create a physical room
room_res = requests.post(
    "http://127.0.0.1:8000/rooms",
    headers=headers,
    data={
        "hotel_id": hotel_id,
        "room_type_id": rt_id,
        "room_number": "Suite 999",
        "floor": 9,
        "status": "available"
    }
)
print("Create room status:", room_res.status_code, room_res.json().get("message"))
new_room_id = room_res.json().get("data", {}).get("id")

# 4. Check bookings for this hotel
bookings = requests.get(f"http://127.0.0.1:8000/bookings?hotel_id={hotel_id}", headers=headers).json().get("data", [])
print(f"Total bookings found: {len(bookings)}")

if bookings and new_room_id:
    bk = bookings[0]
    print(f"Booking keys: {list(bk.keys())}")
    ref = bk.get('booking_reference') or bk.get('reference') or bk.get('id')
    print(f"Allocating Room 999 to Booking #{ref} (ID: {bk['id']})...")
    alloc_res = requests.post(
        "http://127.0.0.1:8000/booking-rooms",
        headers=headers,
        data={
            "booking_id": bk["id"],
            "room_id": new_room_id
        }
    )
    print("Allocate room status:", alloc_res.status_code, alloc_res.json().get("message"))

    # Update booking status to in_house (Express Check-in)
    update_res = requests.put(
        f"http://127.0.0.1:8000/bookings/{bk['id']}",
        headers=headers,
        data={"status": "in_house"}
    )
    print("Check-in status:", update_res.status_code, update_res.json().get("message"))

# 5. Create a dynamic policy
policy_res = requests.post(
    "http://127.0.0.1:8000/policies",
    headers=headers,
    data={
        "hotel_id": hotel_id,
        "policy_type": "cancellation",
        "description": "Peak Season Policy: Full refund for cancellations made at least 72 hours prior to scheduled 3:00 PM check-in. 50% refund between 24-72 hours. Non-refundable under 24 hours."
    }
)
print("Create policy status:", policy_res.status_code, policy_res.json().get("message"))
