import sys, os
sys.path.insert(0, os.path.abspath("."))
from app.core.security import verify_password
from app.core.database import session_maker
import app.models.role, app.models.user, app.models.guest, app.models.hotel, app.models.room_type, app.models.room, app.models.policy, app.models.amenity, app.models.media, app.models.booking, app.models.booking_item, app.models.booking_room, app.models.booking_guest, app.models.review, app.models.refresh_token, app.models.document, app.models.chat
from app.models.user import User

db = session_maker()
tests = [
    ("admin@hms.com", "Admin123!"),
    ("owner@hms.com", "Owner123!"),
    ("manager@hms.com", "Manager123!"),
    ("staff@hms.com", "Staff123!"),
    ("sophia.carter@gmail.com", "Guest123!"),
    ("marcus.vance@techcorp.io", "Guest123!"),
]

for email, pwd in tests:
    u = db.query(User).filter(User.email == email).first()
    if not u:
        print(f"Missing {email}")
        continue
    ok = verify_password(pwd, u.password_hash)
    print(f"User: {email} | Password: {pwd} | Match: {ok}")
db.close()
