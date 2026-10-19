from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import engine
from app.core.database import db_class

from app.models import (
    role, user, guest, hotel, room_type, room, 
    policy, amenity, media, booking, booking_item, booking_room, booking_guest, review
)

from app.api.routes import (
    roles, users, guests, hotels, room_types, rooms, 
    policies, amenities, media as media_routes, 
    bookings, booking_items, booking_rooms, booking_guests, reviews
)

db_class.metadata.create_all(bind=engine)

app = FastAPI(title="Hotel Booking Engine API")

# Allow the HTML frontend to call this API from any origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# import os
# from fastapi.staticfiles import StaticFiles

@app.get("/")
def home():
    return {"message": "this is hms"}


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
app.include_router(booking_items.router)
app.include_router(booking_rooms.router)
app.include_router(booking_guests.router)
app.include_router(reviews.router)