from uuid import UUID
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.user import User
from app.models.guest import Guest
from app.models.booking import Booking
from app.models.review import Review
from app.models.hotel import Hotel
from app.core.roles import UserRole

def get_or_create_guest_for_user(db: Session, user: User) -> Guest:
    """
    Retrieve or automatically provision a Guest profile corresponding to the authenticated User.
    """
    guest = db.query(Guest).filter(
        Guest.email.ilike(user.email.strip()),
        Guest.deleted_at.is_(None)
    ).first()

    if not guest:
        doc_number = f"USR-{str(user.id)[:8].upper()}"
        guest = Guest(
            name=user.name,
            email=user.email.strip().lower(),
            phone=user.phone or "",
            id_document_number=doc_number
        )
        db.add(guest)
        db.commit()
        db.refresh(guest)

    return guest

def get_user_guest_ids(db: Session, user: User) -> list[UUID]:
    """
    Return all Guest IDs associated with the user's email address.
    """
    guests = db.query(Guest.id).filter(
        Guest.email.ilike(user.email.strip()),
        Guest.deleted_at.is_(None)
    ).all()
    return [g.id for g in guests]

def resolve_and_verify_hotel_id(db: Session, current_user: User, payload_hotel_id: UUID | None) -> UUID:
    """
    Resolve and verify permission for an entity requiring a hotel_id:
    - Admins: can specify any valid hotel_id (or must provide one if omitted).
    - Owners: can manage hotels they own (auto-injects if exactly 1 hotel owned).
    - Managers: can only manage their assigned hotel (auto-injects current_user.hotel_id).
    """
    role_name = current_user.role.name.lower() if current_user.role else "customer"

    if role_name == UserRole.ADMIN.value:
        if payload_hotel_id:
            return payload_hotel_id
        if current_user.hotel_id:
            return current_user.hotel_id
        first_hotel = db.query(Hotel).filter(Hotel.deleted_at.is_(None)).first()
        if first_hotel:
            return first_hotel.id
        raise HTTPException(status_code=400, detail="hotel_id is required.")

    if role_name == UserRole.OWNER.value:
        if payload_hotel_id:
            hotel = db.query(Hotel).filter(Hotel.id == payload_hotel_id, Hotel.deleted_at.is_(None)).first()
            if not hotel:
                raise HTTPException(status_code=404, detail="Hotel not found.")
            if hotel.owner_id != current_user.id:
                raise HTTPException(status_code=403, detail="Access denied. You do not own this hotel.")
            return payload_hotel_id

        # Auto-inject for owner
        owned_hotels = db.query(Hotel).filter(Hotel.owner_id == current_user.id, Hotel.deleted_at.is_(None)).all()
        if len(owned_hotels) == 1:
            return owned_hotels[0].id
        elif len(owned_hotels) > 1:
            raise HTTPException(
                status_code=400,
                detail=f"Please specify hotel_id. You own multiple hotels: {[str(h.id) for h in owned_hotels]}."
            )
        else:
            raise HTTPException(
                status_code=400,
                detail="You do not own any hotels yet. Please create a hotel first via POST /hotels."
            )

    # Manager / Receptionist / Staff:
    if current_user.hotel_id:
        if payload_hotel_id and payload_hotel_id != current_user.hotel_id:
            raise HTTPException(status_code=403, detail="Access denied. You can only manage your assigned hotel.")
        return current_user.hotel_id

    raise HTTPException(status_code=403, detail="Access denied. You are not assigned to any hotel.")

def verify_booking_access(
    db: Session,
    booking: Booking,
    current_user: User,
    action: str = "view"
) -> bool:
    """
    Ownership & scoping check for a specific booking.
    - Customers can ONLY access their own bookings.
    - Staff (manager/receptionist) can only access bookings belonging to their assigned hotel.
    - Owners can access bookings belonging to any hotel they own.
    - Admins have full access.
    """
    role_name = current_user.role.name.lower() if current_user.role else "customer"

    # Admin: unrestricted
    if role_name == UserRole.ADMIN.value:
        return True

    # Owner: must own the booking's hotel
    if role_name == UserRole.OWNER.value:
        hotel = db.query(Hotel).filter(Hotel.id == booking.hotel_id).first()
        if not hotel or hotel.owner_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. You do not own the hotel for this booking."
            )
        return True

    # Customer: must match guest email
    if role_name in [UserRole.CUSTOMER.value, "guest"]:
        guest = db.query(Guest).filter(Guest.id == booking.guest_id).first()
        booking_guest_email = guest.email if guest else None
        if not booking_guest_email or booking_guest_email.strip().lower() != current_user.email.strip().lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. You can only {action} your own bookings."
            )
        return True

    # Staff (receptionist or manager): must match assigned hotel if one is set
    if role_name in [UserRole.RECEPTIONIST.value, UserRole.MANAGER.value]:
        assigned_hotel_id = current_user.hotel_id
        if assigned_hotel_id and booking.hotel_id != assigned_hotel_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. You can only {action} bookings for your assigned hotel."
            )
        return True

    return True

def verify_review_access(
    db: Session,
    review: Review,
    current_user: User,
    action: str = "edit"
) -> bool:
    """
    Ownership & scoping check for reviews:
    - Customers can only edit/delete their own reviews.
    - Owners, Managers & Admins can moderate/delete any review.
    """
    role_name = current_user.role.name.lower() if current_user.role else "customer"

    # Admin, Owner, and Manager can moderate
    if role_name in [UserRole.ADMIN.value, UserRole.OWNER.value, UserRole.MANAGER.value]:
        return True

    # Customer: must be the review author
    guest = db.query(Guest).filter(Guest.id == review.guest_id).first()
    review_guest_email = guest.email if guest else None
    if not review_guest_email or review_guest_email.strip().lower() != current_user.email.strip().lower():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied. You can only {action} your own reviews."
        )

    return True


# ---------------------------------------------------------------------------------------------------------------
# Hotel scope for the staff-side operational records (room assignments, line items, booking guests, guest profiles).
# Admins see every hotel, owners the hotels they own, managers and receptionists their assigned hotel only.
# ---------------------------------------------------------------------------------------------------------------

def staff_hotel_scope(db: Session, user: User) -> list[UUID] | None:
    """Hotel ids this staff-side user may see; None means every hotel (admin)."""
    role_name = user.role.name.lower() if user.role else UserRole.CUSTOMER.value
    if role_name == UserRole.ADMIN.value:
        return None
    if role_name == UserRole.OWNER.value:
        return [h.id for h in db.query(Hotel.id).filter(Hotel.owner_id == user.id, Hotel.deleted_at.is_(None)).all()]
    return [user.hotel_id] if user.hotel_id else []


def bookings_in_scope(hotel_ids: list[UUID]):
    """Subquery of the booking ids that belong to the given hotels."""
    from sqlalchemy import select
    return select(Booking.id).where(Booking.hotel_id.in_(hotel_ids))


def guests_in_scope(hotel_ids: list[UUID]):
    """Subquery of the guests who booked, stayed or travelled with a booking at the given hotels."""
    from sqlalchemy import select, union
    from app.models.booking_guest import BookingGuest
    from app.models.booking_item import BookingItem
    from app.models.booking_room import BookingRoom
    return union(
        select(Booking.guest_id).where(Booking.hotel_id.in_(hotel_ids)),
        select(BookingGuest.guest_id).join(Booking, BookingGuest.booking_id == Booking.id).where(Booking.hotel_id.in_(hotel_ids)),
        select(BookingRoom.guest_id).join(BookingItem, BookingRoom.booking_item_id == BookingItem.id)
        .join(Booking, BookingItem.booking_id == Booking.id).where(Booking.hotel_id.in_(hotel_ids)),
    )


def ensure_booking_in_scope(db: Session, user: User, booking_id: UUID | None) -> None:
    """403 unless the booking belongs to a hotel this user may manage (404 if it does not exist)."""
    scope = staff_hotel_scope(db, user)
    if scope is None or booking_id is None:
        return
    hotel_id = db.query(Booking.hotel_id).filter(Booking.id == booking_id).scalar()
    if hotel_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.")
    if hotel_id not in scope:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied. This booking belongs to a hotel you do not manage.")


def ensure_guest_in_scope(db: Session, user: User, guest_id: UUID) -> None:
    """404 unless the guest has a booking at a hotel this user may manage (a guest of another hotel is not revealed)."""
    scope = staff_hotel_scope(db, user)
    if scope is None:
        return
    found = db.query(Guest.id).filter(Guest.id == guest_id, Guest.id.in_(guests_in_scope(scope))).first()
    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This Guest is not present.")
