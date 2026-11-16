import os
from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import settings
from app.core.database import engine, db_class

# Importing every model module registers its table on db_class.metadata before create_all() below
from app.models import (  # noqa: F401
    role, user, guest, hotel, room_type, room,
    policy, amenity, media, booking, booking_item, booking_room, booking_guest, review,
    refresh_token, document, chat as chat_model,
)

from app.api.routes import (
    auth, roles, users, guests, hotels, room_types, rooms, 
    policies, amenities, media as media_routes, 
    bookings, booking_items, booking_rooms, booking_guests, reviews,
    documents, chat
)

db_class.metadata.create_all(bind=engine)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("hms")

@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Demo databases only: keeps bookings, rooms and reviews moving with the calendar (scripts/demo_autopilot.py).
    if settings.DEMO_AUTOPILOT:
        from scripts.demo_autopilot import start_background
        start_background(settings.DEMO_AUTOPILOT_INTERVAL_HOURS)
        logger.info("Demo autopilot started (every %s h)", settings.DEMO_AUTOPILOT_INTERVAL_HOURS)
    yield


app = FastAPI(title="Hotel Booking Engine API", lifespan=lifespan)

# Only the configured frontend origins may call this API with credentials (cookies)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    # Full details go to the server log only; clients never see SQL, paths or stack traces
    logger.exception(f"Unhandled error on {request.method} {request.url.path}")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "An unexpected internal server error occurred.",
            "error_code": "INTERNAL_SERVER_ERROR",
            "details": None
        }
    )

@app.get("/")
def home():
    return {
        "success": True,
        "message": "Welcome to Hotel Management System (HMS) API",
        "data": {"status": "online", "version": "1.0.0", "ui_url": "/app"}
    }

@app.get("/health", tags=["Health"])
def health():
    """Liveness/readiness probe: confirms the API is up and the database answers."""
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"success": True, "message": "ok", "data": {"database": "ok"}}

# Serve the built React app (frontend/dist) when it exists; in development use `npm run dev` instead
frontend_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")
dist_path = os.path.join(frontend_path, "dist")
if os.path.isdir(dist_path):
    assets_path = os.path.join(dist_path, "assets")
    if os.path.isdir(assets_path):
        app.mount("/assets", StaticFiles(directory=assets_path), name="assets")

    @app.get("/app", response_class=FileResponse, tags=["Frontend"])
    @app.get("/ui", response_class=FileResponse, tags=["Frontend"])
    def get_frontend_ui():
        return FileResponse(os.path.join(dist_path, "index.html"))


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
app.include_router(documents.router)
app.include_router(chat.router)