from enum import Enum

class UserRole(str, Enum):
    ADMIN = "admin"
    OWNER = "owner"
    MANAGER = "manager"
    RECEPTIONIST = "receptionist"
    CUSTOMER = "customer"

class RoleGroup:
    # Only System Administrators
    ADMIN_ONLY = [UserRole.ADMIN]

    # Property Owners & Superadmins (can create hotels, own properties, hire managers)
    OWNER_ADMIN = [UserRole.ADMIN, UserRole.OWNER]

    # Upper management: can configure hotels, rooms, policies, pricing, and staff
    MANAGEMENT = [UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER]

    # Front desk / operational staff: can manage day-to-day bookings, guests, room assignments
    STAFF = [UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER, UserRole.RECEPTIONIST]

    # Any authenticated user (including regular hotel guests / customers)
    AUTHENTICATED = [UserRole.ADMIN, UserRole.OWNER, UserRole.MANAGER, UserRole.RECEPTIONIST, UserRole.CUSTOMER]
