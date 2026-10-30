import sys
import os
sys.path.insert(0, os.path.abspath("."))

from app.core.database import session_maker
# Import all models to avoid mapper errors
import app.models.role
import app.models.user
import app.models.guest
import app.models.hotel
import app.models.room_type
import app.models.room
import app.models.policy
import app.models.amenity
import app.models.media
import app.models.booking
import app.models.booking_item
import app.models.booking_room
import app.models.booking_guest
import app.models.review
import app.models.refresh_token
import app.models.document
import app.models.chat

from app.models.user import User
from app.models.role import Role

db = session_maker()
try:
    users = db.query(User).all()
    print(f"Total users found: {len(users)}")
    for u in users:
        role_name = u.role.name if u.role else "No Role"
        print(f"Email: {u.email} | Name: {u.name} | Role: {role_name} | Password Hash: {u.password_hash[:15]}...")
finally:
    db.close()
