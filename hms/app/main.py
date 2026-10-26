from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import engine, db_class

from app.models import (
    role, user, guest, hotel, room_type, room, 
    policy, amenity, media, booking, booking_item, booking_room, booking_guest, review,
    refresh_token
)

from app.api.routes import (
    auth, roles, users, guests, hotels, room_types, rooms, 
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

from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

STATUS_CODE_ERROR_MAP = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    409: "CONFLICT",
    422: "VALIDATION_ERROR",
    500: "INTERNAL_SERVER_ERROR",
}

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    error_code = STATUS_CODE_ERROR_MAP.get(exc.status_code, f"HTTP_{exc.status_code}")
    headers = getattr(exc, "headers", None)
    return JSONResponse(
        status_code=exc.status_code,
        headers=headers,
        content={
            "success": False,
            "message": str(exc.detail),
            "error_code": error_code,
            "details": None
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    first_msg = errors[0].get("msg", "Validation error") if errors else "Validation failed"
    first_loc = " -> ".join(str(loc) for loc in errors[0].get("loc", [])) if errors else ""
    formatted_msg = f"{first_loc}: {first_msg}" if first_loc else first_msg

    cleaned_errors = []
    for err in errors:
        err_copy = dict(err)
        if "ctx" in err_copy and "error" in err_copy["ctx"]:
            err_copy["ctx"]["error"] = str(err_copy["ctx"]["error"])
        cleaned_errors.append(err_copy)

    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "message": formatted_msg,
            "error_code": "VALIDATION_ERROR",
            "details": cleaned_errors
        }
    )

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "An unexpected internal server error occurred.",
            "error_code": "INTERNAL_SERVER_ERROR",
            "details": str(exc)
        }
    )

@app.get("/")
def home():
    return {
        "success": True,
        "message": "Welcome to Hotel Management System (HMS) API",
        "data": {"status": "online", "version": "1.0.0"}
    }


app.include_router(auth.router)
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