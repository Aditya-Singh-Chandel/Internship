import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Uuid
from sqlalchemy.orm import relationship
from app.core.database import db_class

class User(db_class):
    __tablename__ = "users"

    id = Column(Uuid, primary_key=True, default=uuid.uuid4)
    role_id = Column(Uuid, ForeignKey("roles.id"))
    hotel_id = Column(Uuid, ForeignKey("hotels.id"), nullable=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    deleted_at = Column(DateTime, nullable=True)

    role = relationship("Role", back_populates="users")
    hotel = relationship("Hotel", foreign_keys=[hotel_id])
    owned_hotels = relationship("Hotel", foreign_keys="Hotel.owner_id", back_populates="owner")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")

    @property
    def assigned_property_name(self) -> str | None:
        role_str = (self.role.name.lower() if self.role else "")
        if role_str == "admin":
            return "Global Portfolio"
        if role_str == "owner":
            active_owned = [h.name for h in (self.owned_hotels or []) if getattr(h, "deleted_at", None) is None]
            if active_owned:
                return ", ".join(active_owned)
            return "Unassigned Portfolio"
        if self.hotel:
            return self.hotel.name
        return None

    @property
    def owned_hotel_ids(self) -> list[uuid.UUID]:
        return [h.id for h in (self.owned_hotels or []) if getattr(h, "deleted_at", None) is None]