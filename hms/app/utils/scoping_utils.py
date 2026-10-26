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
                detail=f"Access denied. You do not own the hotel for this booking."
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

