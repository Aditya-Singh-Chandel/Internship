import uuid
import sys
from datetime import date, timedelta
from fastapi.testclient import TestClient
from app.main import app

def run_tests():
    print("=" * 70)
    print("STARTING HMS FULL CAPABILITY AND REGRESSION TEST SUITE")
    print("=" * 70)

    client = TestClient(app)
    run_id = uuid.uuid4().hex[:6]
    passed_count = 0
    total_count = 0

    def test(name):
        nonlocal total_count
        total_count += 1
        print(f"\n[{total_count}] Testing: {name}...")

    def assert_status(response, expected_status, step_name=""):
        nonlocal passed_count
        if response.status_code != expected_status:
            print(f"FAILED: Expected {expected_status}, got {response.status_code}")
            try:
                print("Response JSON:", response.json())
            except Exception:
                print("Response text:", response.text)
            raise AssertionError(f"Step '{step_name}' failed status check: expected {expected_status}, got {response.status_code}")
        passed_count += 1
        print(f"PASSED (status {response.status_code})")
        return response.json() if response.content else {}

    # -------------------------------------------------------------
    # 1. Health / Home route
    # -------------------------------------------------------------
    test("Health Check GET /")
    res = client.get("/")
    data = assert_status(res, 200, "Health Check")
    assert data["success"] is True
    assert data["data"]["status"] == "online"

    # -------------------------------------------------------------
    # 2. Admin Initialization & Authentication
    # -------------------------------------------------------------
    test("Admin Initialization POST /auth/init-admin")
    admin_email = f"admin_{run_id}@hms.com"
    admin_password = "AdminSecure123!"
    res = client.post("/auth/init-admin", json={
        "name": f"Admin {run_id}",
        "email": admin_email,
        "password": admin_password,
        "phone": "+1234567890"
    })
    if res.status_code in [200, 201]:
        data = assert_status(res, res.status_code, "Init Admin")
        admin_token = data["data"]["access_token"]
    else:
        # Admin already initialized, login using existing admin credentials
        login_res = client.post("/auth/login", data={"username": "admin@hms.com", "password": "Admin123!"})
        data = assert_status(login_res, 200, "Login Existing Admin")
        admin_token = data["data"]["access_token"]

    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # -------------------------------------------------------------
    # 3. Roles Listing
    # -------------------------------------------------------------
    test("List Roles GET /roles (Requires Admin)")
    res = client.get("/roles", headers=admin_headers)
    roles_data = assert_status(res, 200, "List Roles")
    roles = roles_data.get("items") or roles_data.get("data")
    role_map = {r["name"].lower(): r["id"] for r in roles}
    print("Found roles:", list(role_map.keys()))
    assert "admin" in role_map
    assert "owner" in role_map
    assert "customer" in role_map

    # -------------------------------------------------------------
    # 4. Customer Registration & Token Lifecycle
    # -------------------------------------------------------------
    test("Register Customer POST /auth/register")
    cust_email = f"cust_{run_id}@example.com"
    cust_password = "CustomerPass123!"
    res = client.post("/auth/register", json={
        "name": f"Jane Doe {run_id}",
        "email": cust_email,
        "password": cust_password,
        "phone": "+1987654321"
    })
    cust_data = assert_status(res, 201, "Customer Register")
    cust_token = cust_data["data"]["access_token"]
    cust_refresh = cust_data["data"]["refresh_token"]
    customer_headers = {"Authorization": f"Bearer {cust_token}"}

    test("Get Customer Profile GET /auth/me")
    res = client.get("/auth/me", headers=customer_headers)
    me_data = assert_status(res, 200, "Customer /auth/me")
    assert me_data["data"]["email"] == cust_email

    test("Rotate Refresh Token POST /auth/refresh")
    res = client.post("/auth/refresh", json={"refresh_token": cust_refresh})
    ref_data = assert_status(res, 200, "Token Refresh")
    new_access_token = ref_data["data"]["access_token"]
    new_refresh_token = ref_data["data"]["refresh_token"]
    assert new_access_token != cust_token
    customer_headers = {"Authorization": f"Bearer {new_access_token}"}

    test("Token Theft Prevention: Reusing old refresh token must be rejected")
    res = client.post("/auth/refresh", json={"refresh_token": cust_refresh})
    assert_status(res, 401, "Token Theft Detection")

    # -------------------------------------------------------------
    # 5. Role-Based Access Control (RBAC) Enforcement
    # -------------------------------------------------------------
    test("RBAC Security: Customer attempting to create Hotel must return 403 Forbidden")
    res = client.post("/hotels", headers=customer_headers, data={
        "name": "Forbidden Palace",
        "address_line1": "123 Nowhere St",
        "city": "Metropolis",
        "country": "Wonderland"
    })
    assert_status(res, 403, "Customer Create Hotel 403")

    # -------------------------------------------------------------
    # 6. Create Hotel Owner & Login
    # -------------------------------------------------------------
    test("Admin creates Hotel Owner POST /users")
    owner_email = f"owner_{run_id}@hotelgroup.com"
    owner_password = "OwnerPass123!"
    res = client.post("/users", headers=admin_headers, data={
        "name": f"Bob Owner {run_id}",
        "email": owner_email,
        "password": owner_password,
        "role_id": role_map["owner"],
        "phone": "+1555000111"
    })
    owner_user_data = assert_status(res, 201, "Create Owner User")
    owner_id = owner_user_data["data"]["id"]

    test("Login as Hotel Owner POST /auth/login")
    res = client.post("/auth/login", data={"username": owner_email, "password": owner_password})
    owner_auth = assert_status(res, 200, "Owner Login")
    owner_token = owner_auth["data"]["access_token"]
    owner_headers = {"Authorization": f"Bearer {owner_token}"}

    # -------------------------------------------------------------
    # 7. Hotel Management
    # -------------------------------------------------------------
    test("Owner creates Hotel POST /hotels")
    hotel_name = f"Grand Plaza {run_id}"
    res = client.post("/hotels", headers=owner_headers, data={
        "name": hotel_name,
        "owner_id": owner_id,
        "address_line1": "777 Luxury Blvd",
        "city": "Miami",
        "state": "FL",
        "country": "USA",
        "postal_code": "33101",
        "description": "5-star luxury seaside resort",
        "email": f"resort_{run_id}@grandplaza.com",
        "phone": "+13055551234"
    })
    hotel_data = assert_status(res, 201, "Create Hotel")
    hotel_id = hotel_data["data"]["id"]

    test("Public/Guest can list Hotels GET /hotels with query filtering")
    res = client.get(f"/hotels?name={hotel_name}&city=Miami")
    hotels_list = assert_status(res, 200, "List Hotels")
    items = hotels_list.get("items") or hotels_list.get("data")
    assert len(items) >= 1
    assert any(h["id"] == hotel_id for h in items)

    # -------------------------------------------------------------
    # 8. Room Types & Physical Rooms
    # -------------------------------------------------------------
    test("Owner creates Room Type POST /room-types")
    res = client.post("/room-types", headers=owner_headers, data={
        "hotel_id": hotel_id,
        "name": f"Deluxe Ocean Suite {run_id}",
        "description": "Panoramic ocean view with king bed",
        "base_price": 250.00,
        "guests_allowed": 3
    })
    room_type_data = assert_status(res, 201, "Create Room Type")
    room_type_id = room_type_data["data"]["id"]

    test("Owner bulk creates Physical Rooms POST /rooms/bulk")
    res = client.post("/rooms/bulk", headers=owner_headers, json={
        "room_type_id": room_type_id,
        "rooms": [
            {"room_number": f"101-{run_id}", "floor": 1, "status": "available"},
            {"room_number": f"102-{run_id}", "floor": 1, "status": "available"}
        ]
    })
    rooms_bulk_data = assert_status(res, 201, "Bulk Create Rooms")
    created_rooms = rooms_bulk_data["data"]
    assert len(created_rooms) == 2
    room_101_id = created_rooms[0]["id"]
    room_102_id = created_rooms[1]["id"]

    test("Room uniqueness validation: duplicate room_number in hotel must return 400")
    res = client.post("/rooms", headers=owner_headers, data={
        "room_type_id": room_type_id,
        "room_number": f"101-{run_id}",
        "floor": 1
    })
    assert_status(res, 400, "Duplicate Room 400")

    # -------------------------------------------------------------
    # 9. Amenities, Policies, and Media
    # -------------------------------------------------------------
    test("Create Hotel Amenity POST /amenities")
    res = client.post("/amenities", headers=owner_headers, data={
        "hotel_id": hotel_id,
        "name": "Heated Infinity Pool",
        "description": "Olympic-sized ocean-view heated pool"
    })
    amenity_data = assert_status(res, 201, "Create Amenity")
    amenity_id = amenity_data["data"]["id"]

    test("Create Hotel Policy POST /policies")
    res = client.post("/policies", headers=owner_headers, data={
        "hotel_id": hotel_id,
        "policy_type": "Check-in",
        "description": "Standard check-in begins at 15:00. Government ID required."
    })
    policy_data = assert_status(res, 201, "Create Policy")
    policy_id = policy_data["data"]["id"]

    test("Create Media with XOR linkage check POST /media")
    # Mutual exclusivity: cannot specify BOTH hotel_id and room_type_id
    res = client.post("/media", headers=owner_headers, data={
        "hotel_id": hotel_id,
        "room_type_id": room_type_id,
        "image_url": "https://example.com/pool.jpg",
        "is_primary": True
    })
    assert_status(res, 400, "Media XOR validation")

    # Valid media for Hotel
    res = client.post("/media", headers=owner_headers, data={
        "hotel_id": hotel_id,
        "image_url": "https://example.com/hotel_front.jpg",
        "is_primary": True
    })
    media_data = assert_status(res, 201, "Create Hotel Media")
    media_id = media_data["data"]["id"]

    # -------------------------------------------------------------
    # 10. Booking Flow & Availability Validation
    # -------------------------------------------------------------
    today = date.today()
    checkin_str = today.isoformat()
    checkout_str = (today + timedelta(days=3)).isoformat()

    test("Booking Date Validation: Checkout on or before Checkin must return 400")
    res = client.post("/bookings", headers=customer_headers, json={
        "hotel_id": hotel_id,
        "checkin_date": checkout_str,
        "checkout_date": checkin_str,
        "items": [{"room_type_id": room_type_id, "quantity": 1}]
    })
    assert_status(res, 400, "Checkout before Checkin 400")

    test("Booking Inventory Validation: Requesting 10 rooms when only 2 exist must return 400")
    res = client.post("/bookings", headers=customer_headers, json={
        "hotel_id": hotel_id,
        "checkin_date": checkin_str,
        "checkout_date": checkout_str,
        "items": [{"room_type_id": room_type_id, "quantity": 10}]
    })
    assert_status(res, 400, "Overbooking Inventory 400")

    test("Customer creates Valid Booking POST /bookings")
    res = client.post("/bookings", headers=customer_headers, json={
        "hotel_id": hotel_id,
        "checkin_date": checkin_str,
        "checkout_date": checkout_str,
        "special_requests": "High floor ocean view please",
        "items": [{"room_type_id": room_type_id, "quantity": 1}]
    })
    booking_data = assert_status(res, 201, "Create Booking")
    booking_id = booking_data["data"]["id"]
    customer_guest_id = booking_data["data"]["guest_id"]
    booking_item_id = booking_data["data"]["booking_items"][0]["id"]
    print("Created Booking ID:", booking_id)
    print("Auto-provisioned Guest ID:", customer_guest_id)
    print("Booking Line Item ID:", booking_item_id)

    # -------------------------------------------------------------
    # 11. Room Assignment & Stay Lifecycle
    # -------------------------------------------------------------
    test("Staff assigns physical room POST /booking-rooms/bulk")
    res = client.post("/booking-rooms/bulk", headers=owner_headers, json={
        "booking_id": booking_id,
        "assignments": [{
            "booking_item_id": booking_item_id,
            "room_id": room_101_id,
            "guest_id": customer_guest_id
        }]
    })
    assigned_data = assert_status(res, 201, "Bulk Assign Room")
    booking_room_id = assigned_data["data"][0]["id"]
    # Verify rate calculation is nights * unit_price (3 nights * $250.00 = $750.00)
    assert float(assigned_data["data"][0]["room_rate"]) == 750.0, f"Expected 750.0, got {assigned_data['data'][0]['room_rate']}"

    test("Conflict check: Double booking physical room on overlapping dates must fail")
    res = client.post("/booking-rooms/bulk", headers=owner_headers, json={
        "booking_id": booking_id,
        "assignments": [{
            "booking_item_id": booking_item_id,
            "room_id": room_101_id,
            "guest_id": customer_guest_id
        }]
    })
    assert_status(res, 400, "Double assign conflict 400")

    test("Check-in room PATCH /booking-rooms/{id}/checkin")
    res = client.patch(f"/booking-rooms/{booking_room_id}/checkin", headers=owner_headers)
    assert_status(res, 200, "Check in room")

    # Verify physical room status is occupied
    res = client.get(f"/rooms/{room_101_id}")
    room_detail = assert_status(res, 200, "Verify Room Occupied")
    assert room_detail["data"]["status"] == "occupied"

    test("Add Companion Guest to Booking POST /booking-guests")
    # Create another guest profile
    res = client.post("/guests", headers=owner_headers, data={
        "name": f"Companion {run_id}",
        "email": f"companion_{run_id}@example.com",
        "id_document_number": f"ID-{run_id}"
    })
    companion_guest = assert_status(res, 201, "Create Companion Guest Profile")
    companion_guest_id = companion_guest["data"]["id"]

    res = client.post("/booking-guests", headers=owner_headers, data={
        "booking_id": booking_id,
        "guest_id": companion_guest_id,
        "booking_room_id": booking_room_id
    })
    assert_status(res, 201, "Register Companion Guest")

    test("Check-out room PATCH /booking-rooms/{id}/checkout")
    res = client.patch(f"/booking-rooms/{booking_room_id}/checkout", headers=owner_headers)
    assert_status(res, 200, "Check out room")

    # Verify physical room status is back to available
    res = client.get(f"/rooms/{room_101_id}")
    room_detail = assert_status(res, 200, "Verify Room Available After Checkout")
    assert room_detail["data"]["status"] == "available"

    # -------------------------------------------------------------
    # 12. Review Flow
    # -------------------------------------------------------------
    test("Customer submits Review for their Booking POST /reviews")
    res = client.post("/reviews", headers=customer_headers, data={
        "booking_id": booking_id,
        "guest_id": customer_guest_id,
        "rating": 5,
        "comment": "Outstanding view, seamless check-in and beautiful rooms!"
    })
    review_data = assert_status(res, 201, "Create Review")
    review_id = review_data["data"]["id"]

    test("Review rating bounds validation: rating > 5 must return 400/422")
    res = client.post("/reviews", headers=customer_headers, data={
        "booking_id": booking_id,
        "guest_id": customer_guest_id,
        "rating": 10,
        "comment": "Too high"
    })
    assert res.status_code in [400, 422]
    print(f"PASSED (status {res.status_code})")

    # -------------------------------------------------------------
    # 13. Soft Delete & Restore Cascades
    # -------------------------------------------------------------
    test("Soft delete policy DELETE /policies/{id}")
    res = client.delete(f"/policies/{policy_id}", headers=owner_headers)
    assert_status(res, 200, "Soft Delete Policy")

    test("Deleted policy is hidden from default listings")
    res = client.get(f"/policies?hotel_id={hotel_id}")
    pol_list = assert_status(res, 200, "List Active Policies")
    pols = pol_list.get("items") or pol_list.get("data")
    assert not any(p["id"] == policy_id for p in pols)

    test("Deleted policy appears when include_deleted=true")
    res = client.get(f"/policies?hotel_id={hotel_id}&include_deleted=true")
    pol_del_list = assert_status(res, 200, "List Including Deleted Policies")
    del_pols = pol_del_list.get("items") or pol_del_list.get("data")
    assert any(p["id"] == policy_id for p in del_pols)

    test("Restore soft-deleted policy POST /policies/{id}/restore")
    res = client.post(f"/policies/{policy_id}/restore", headers=owner_headers)
    assert_status(res, 200, "Restore Policy")

    # -------------------------------------------------------------
    # 14. Customer Data Isolation & Scoping Security
    # -------------------------------------------------------------
    test("Customer Scoping: Other Customer cannot access another user's booking (403 Forbidden)")
    other_cust_email = f"other_{run_id}@example.com"
    res = client.post("/auth/register", json={
        "name": f"Other Customer {run_id}",
        "email": other_cust_email,
        "password": "OtherPass123!",
        "phone": "+1999888777"
    })
    other_cust_data = assert_status(res, 201, "Register Other Customer")
    other_headers = {"Authorization": f"Bearer {other_cust_data['data']['access_token']}"}

    res = client.get(f"/bookings/{booking_id}", headers=other_headers)
    assert_status(res, 403, "Other Customer View Booking 403")

    # -------------------------------------------------------------
    # 15. Booking Cancellation Flow
    # -------------------------------------------------------------
    test("Booking Cancellation Flow POST /bookings/{id}/cancel")
    # Create a future booking to test cancellation
    future_in = (today + timedelta(days=10)).isoformat()
    future_out = (today + timedelta(days=12)).isoformat()
    res = client.post("/bookings", headers=customer_headers, json={
        "hotel_id": hotel_id,
        "checkin_date": future_in,
        "checkout_date": future_out,
        "special_requests": "Window seat",
        "items": [{"room_type_id": room_type_id, "quantity": 1}]
    })
    future_booking = assert_status(res, 201, "Create Future Booking For Cancellation")
    cancel_booking_id = future_booking["data"]["id"]

    res = client.patch(f"/bookings/{cancel_booking_id}/cancel", headers=customer_headers, json={"reason": "Change of plans"})
    cancelled_res = assert_status(res, 200, "Cancel Booking")
    assert cancelled_res["data"]["status"] == "cancelled"

    # Cannot cancel already cancelled booking
    res = client.patch(f"/bookings/{cancel_booking_id}/cancel", headers=customer_headers, json={"reason": "Again"})
    assert_status(res, 400, "Cancel Already Cancelled Booking 400")

    # -------------------------------------------------------------
    # 16. Booking Cascade Soft-Delete & Restore
    # -------------------------------------------------------------
    test("Cascade Soft-Delete Booking DELETE /bookings/{id}")
    res = client.delete(f"/bookings/{booking_id}", headers=owner_headers)
    assert_status(res, 200, "Soft Delete Booking")

    # Verify booking is hidden from active queries
    res = client.get(f"/bookings/{booking_id}", headers=owner_headers)
    assert_status(res, 404, "Verify Soft Deleted Booking Hidden")

    # Restore booking
    test("Cascade Restore Booking POST /bookings/{id}/restore")
    res = client.post(f"/bookings/{booking_id}/restore", headers=owner_headers)
    assert_status(res, 200, "Restore Booking")

    # Verify booking is active again
    res = client.get(f"/bookings/{booking_id}", headers=owner_headers)
    assert_status(res, 200, "Verify Restored Booking Visible")

    # -------------------------------------------------------------
    # 17. One-Click User Logout
    # -------------------------------------------------------------
    test("Instant One-Click Logout POST /auth/logout-me")
    res = client.post("/auth/logout-me", headers=other_headers)
    assert_status(res, 200, "One-Click Logout")

    # -------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------
    print("\n" + "=" * 70)
    print(f"ALL TESTS PASSED SUCCESSFULLY! ({passed_count}/{total_count} assertions verified)")
    print("=" * 70)

if __name__ == "__main__":
    try:
        run_tests()
        sys.exit(0)
    except Exception as exc:
        print("\nTEST SUITE RUN FAILED WITH ERROR:", exc)
        sys.exit(1)
