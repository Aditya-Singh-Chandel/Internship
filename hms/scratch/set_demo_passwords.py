import sys, os
sys.path.insert(0, os.path.abspath("."))
from app.core.security import get_password_hash, verify_password
from app.core.database import session_maker
import app.models.role, app.models.user, app.models.guest, app.models.hotel, app.models.room_type, app.models.room, app.models.policy, app.models.amenity, app.models.media, app.models.booking, app.models.booking_item, app.models.booking_room, app.models.booking_guest, app.models.review, app.models.refresh_token, app.models.document, app.models.chat
from app.models.user import User

db = session_maker()
accounts = [
    ("admin@hms.com", "Admin@123"),
    ("owner@hms.com", "Owner@123"),
    ("manager@hms.com", "Manager@123"),
    ("staff@hms.com", "Staff@123"),
    ("marcus.vance@techcorp.io", "Customer@123")
]

for email, pwd in accounts:
    u = db.query(User).filter(User.email == email).first()
    if u:
        u.password_hash = get_password_hash(pwd)
        db.add(u)
        print(f"Updated password for {email} to {pwd}")
    else:
        print(f"User {email} not found")

db.commit()

# Verify
for email, pwd in accounts:
    u = db.query(User).filter(User.email == email).first()
    if u:
        ok = verify_password(pwd, u.password_hash)
        print(f"Verification {email} with {pwd}: {ok}")

db.close()
