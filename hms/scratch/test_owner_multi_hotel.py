import sys, os
sys.path.insert(0, os.path.abspath("."))
from uuid import UUID
from app.core.database import session_maker
from app.models.hotel import Hotel
from app.models.user import User
from app.models.role import Role
from app.models.booking import Booking
from app.models.review import Review
from app.models.room_type import RoomType
from app.models.room import Room
from app.models.guest import Guest
from app.models.refresh_token import RefreshToken
from app.models.booking_room import BookingRoom
from app.models.booking_item import BookingItem
from app.models.booking_guest import BookingGuest
from app.models.media import Media
from app.models.document import HotelDocument
from app.models.policy import Policy
from app.models.amenity import Amenity
from app.models.chat import ChatSession, ChatMessage
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import create_access_token

def test_full_owner_and_reviews():
    client = TestClient(app)
    db = session_maker()
    try:
        # Find admin
        admin = db.query(User).join(Role, User.role_id == Role.id).filter(Role.name == "admin").first()
        admin_token = create_access_token(subject=admin.id, role="admin")

        # Find owner Boss
        boss = db.query(User).join(Role, User.role_id == Role.id).filter(User.email == "boss@gmail.com").first()
        boss_token = create_access_token(subject=boss.id, role="owner")

        hotels = db.query(Hotel).filter(Hotel.deleted_at.is_(None)).all()
        h1 = hotels[0]
        h2 = hotels[1]

        print(f"Admin: {admin.email}")
        print(f"Boss: {boss.email}")
        print(f"Hotel 1: {h1.name} (Owner: {h1.owner_id})")
        print(f"Hotel 2: {h2.name} (Owner: {h2.owner_id})")

        # 1. Test assigning h1 (already owned by someone else) to boss -> Expected 400
        res = client.put(
            f"/users/{boss.id}",
            data={"hotel_ids": f"{h1.id}"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        print("Assigning already owned hotel status:", res.status_code, res.json())
        assert res.status_code == 400, "Should reject assigning an already-owned hotel"
        err_msg = res.json().get("message") or res.json().get("detail", "")
        assert "already has an assigned owner" in err_msg
        print("[OK] Verified: Cannot assign hotel to multiple owners (1 Hotel -> at most 1 Owner)")

        # 2. Temporarily unassign h1 and h2 owner_id
        original_h1_owner = h1.owner_id
        original_h2_owner = h2.owner_id
        h1.owner_id = None
        h2.owner_id = None
        db.commit()

        # 3. Assign BOTH h1 and h2 to Boss (1 Owner -> Multiple Hotels)
        res2 = client.put(
            f"/users/{boss.id}",
            data={"hotel_ids": f"{h1.id},{h2.id}"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        print("Assigning 2 hotels to Boss status:", res2.status_code)
        assert res2.status_code == 200, f"Failed to assign 2 hotels: {res2.text}"
        data = res2.json()["data"]
        print("Boss owned_hotel_ids:", data["owned_hotel_ids"])
        print("Boss assigned_property_name:", data["assigned_property_name"])
        assert len(data["owned_hotel_ids"]) == 2, "Boss should have exactly 2 hotels"
        assert h1.name in data["assigned_property_name"], "Hotel 1 should be in assigned_property_name"
        assert h2.name in data["assigned_property_name"], "Hotel 2 should be in assigned_property_name"
        print("[OK] Verified: One owner can have multiple hotels under them (1 Owner -> Many Hotels)")

        # 4. Verify that trying to assign h1 to another owner now fails because Boss owns it
        other_owner = db.query(User).join(Role, User.role_id == Role.id).filter(User.email == "owner@gmail.com").first()
        res3 = client.put(
            f"/users/{other_owner.id}",
            data={"hotel_ids": f"{h1.id}"},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert res3.status_code == 400
        err_msg3 = res3.json().get("message") or res3.json().get("detail", "")
        assert "already has an assigned owner" in err_msg3
        print("[OK] Verified: Second owner cannot claim hotel already owned by Boss")

        # 5. Restore original state
        client.put(
            f"/users/{boss.id}",
            data={"hotel_ids": ""},
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        h1.owner_id = original_h1_owner
        h2.owner_id = original_h2_owner
        db.commit()
        print("[OK] Restored original hotel ownership.")

        # 6. Test Review Update
        rev = db.query(Review).filter(Review.deleted_at.is_(None)).first()
        if rev and rev.guest:
            user_author = db.query(User).filter(User.email == rev.guest.email).first()
            token_to_use = create_access_token(subject=user_author.id, role="customer") if user_author else admin_token

            update_res = client.put(
                f"/reviews/{rev.id}",
                data={"rating": 4, "comment": "Updated experience: absolutely stellar stay!"},
                headers={"Authorization": f"Bearer {token_to_use}"}
            )
            print("Update review status:", update_res.status_code)
            assert update_res.status_code == 200
            assert update_res.json()["data"]["rating"] == 4
            assert update_res.json()["data"]["comment"] == "Updated experience: absolutely stellar stay!"
            print("[OK] Verified: Review editing works cleanly via PUT /reviews/{id}")

        print("\nALL BACKEND TESTS PASSED SUCCESSFULLY!")

    finally:
        db.close()

if __name__ == "__main__":
    test_full_owner_and_reviews()
