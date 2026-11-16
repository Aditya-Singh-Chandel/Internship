from app.models.booking import Booking
from app.models.document import HotelDocumentChunk
from app.models.hotel import Hotel
from app.models.review import Review
from app.models.room import Room
from evals.seed import HOTELS, REVIEWS, ROOM_COUNTS, STAFF_ONLY_CANARY


def test_seed_loads(db):
    assert db.query(Hotel).count() == len(HOTELS)
    # 3 bookings by the two named guests + 6 past completed stays that carry the reviews
    assert db.query(Booking).count() == 3 + sum(len(v) for v in REVIEWS.values())
    assert db.query(Booking).filter(Booking.status == "completed").count() == 1 + sum(len(v) for v in REVIEWS.values())
    assert db.query(Review).count() == sum(len(v) for v in REVIEWS.values())
    assert db.query(Room).count() == sum(ROOM_COUNTS.values())
    chunks = db.query(HotelDocumentChunk).all()
    assert chunks and all(c.embedding is not None for c in chunks)
    staff_only = [c for c in chunks if c.access_level == "staff_only"]
    assert staff_only and all(STAFF_ONLY_CANARY in c.content for c in staff_only)
