from fastapi import FastAPI
from app.core.database import engine
from app.core.database import db_class

from app.models import (
    role, user, guest, hotel, room_type, room, 
    policy, amenity, media, booking, booking_guest, review
)

from app.api.routes import (
    roles, users, guests, hotels, room_types, rooms, 
    policies, amenities, media as media_routes, 
    bookings, booking_guests, reviews
)

db_class.metadata.create_all(bind=engine)

app = FastAPI(title="Hotel Booking Engine API")


@app.get("/")
def home():
    return {"message": "this is hms list"}

app.include_router(roles.router)
app.include_router(users.router)
app.include_router(guests.router)
app.include_router(hotels.router)
app.include_router(room_types.router)
app.include_router(rooms.router)
app.include_router(policies.router)
app.include_router(amenities.router)
app.include_router(media_routes.router)
app.include_router(bookings.router)
app.include_router(booking_guests.router)
app.include_router(reviews.router)