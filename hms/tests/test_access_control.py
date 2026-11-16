"""Who may touch what: hotel-scoped documents, registration, admin bootstrap, chat sessions, error handling."""
import uuid

import pytest

from app.models.chat import ChatMessage, ChatSession
from evals.seed import STAFF_ONLY_CANARY, TEST_PASSWORD, sid

MAYFAIR, ASPEN = sid("hotel:mayfair"), sid("hotel:aspen")


def login(client, email):
    r = client.post("/auth/login", data={"username": email, "password": TEST_PASSWORD})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def reception_mayfair(client):
    return login(client, "reception.mayfair@test.hms")


@pytest.fixture()
def reception_aspen(client):
    return login(client, "reception.aspen@test.hms")


@pytest.fixture()
def admin(client):
    return login(client, "admin@test.hms")


# ---------------- knowledge-base documents ----------------
def test_document_list_requires_login(client):
    assert client.get(f"/hotels/{MAYFAIR}/documents").status_code == 401


def test_staff_can_list_their_own_hotels_documents(client, reception_mayfair):
    r = client.get(f"/hotels/{MAYFAIR}/documents", headers=reception_mayfair)
    assert r.status_code == 200
    assert any(d["access_level"] == "staff_only" for d in r.json()["data"])


def test_staff_cannot_list_another_hotels_documents(client, reception_aspen):
    assert client.get(f"/hotels/{MAYFAIR}/documents", headers=reception_aspen).status_code == 403


def test_staff_cannot_write_to_another_hotel(client, reception_aspen):
    payload = {"title": "Any title", "content": "Some content long enough to pass validation.", "category": "faq", "access_level": "public"}
    assert client.post(f"/hotels/{MAYFAIR}/documents/text", json=payload, headers=reception_aspen).status_code == 403
    assert client.post(f"/hotels/{MAYFAIR}/documents/sync", headers=reception_aspen).status_code == 403
    files = {"file": ("a.txt", b"hello", "text/plain")}
    assert client.post(f"/hotels/{MAYFAIR}/documents/upload", files=files, headers=reception_aspen).status_code == 403


def test_staff_cannot_delete_another_hotels_document(client, db, reception_aspen):
    from app.models.document import HotelDocument
    doc = db.query(HotelDocument).filter(HotelDocument.hotel_id == MAYFAIR).first()
    assert client.delete(f"/hotels/{MAYFAIR}/documents/{doc.id}", headers=reception_aspen).status_code == 403


def test_delete_requires_document_to_belong_to_the_hotel_in_the_path(client, db, admin):
    """Even an admin must not delete hotel A's document through hotel B's URL."""
    from app.models.document import HotelDocument
    doc = db.query(HotelDocument).filter(HotelDocument.hotel_id == MAYFAIR).first()
    assert client.delete(f"/hotels/{ASPEN}/documents/{doc.id}", headers=admin).status_code == 404
    db.refresh(doc)
    assert doc.deleted_at is None


def test_invalid_access_level_is_rejected(client, reception_mayfair):
    payload = {"title": "Any title", "content": "Some content long enough to pass validation.", "category": "faq", "access_level": "everyone"}
    assert client.post(f"/hotels/{MAYFAIR}/documents/text", json=payload, headers=reception_mayfair).status_code == 422
    files = {"file": ("a.txt", b"hello", "text/plain")}
    r = client.post(f"/hotels/{MAYFAIR}/documents/upload", files=files, data={"access_level": "everyone"}, headers=reception_mayfair)
    assert r.status_code == 422


def test_oversized_upload_is_rejected(client, reception_mayfair):
    files = {"file": ("big.txt", b"a" * (10 * 1024 * 1024 + 1), "text/plain")}
    assert client.post(f"/hotels/{MAYFAIR}/documents/upload", files=files, headers=reception_mayfair).status_code == 413


def test_public_search_never_returns_staff_only_content(client):
    for query in ("master key override code for the night safe", "internal staff memo", STAFF_ONLY_CANARY):
        r = client.post(f"/hotels/{MAYFAIR}/documents/search", json={"query": query, "top_k": 20})
        assert r.status_code == 200
        assert STAFF_ONLY_CANARY not in r.text


# ---------------- registration & bootstrap ----------------
@pytest.mark.parametrize("extra", [
    {"role_name": "owner"},
    {"role_name": "admin"},
    {"role_id": str(sid("role:admin"))},
    {"hotel_id": str(MAYFAIR)},
])
def test_public_registration_always_creates_a_customer(client, db, extra):
    email = f"new.{uuid.uuid4().hex[:8]}@test.hms"
    r = client.post("/auth/register", json={"name": "New Person", "email": email, "password": "Passw0rd!", **extra})
    assert r.status_code == 201, r.text
    from app.models.user import User
    user = db.query(User).filter(User.email == email).one()
    assert user.role.name == "customer" and user.hotel_id is None


def test_init_admin_needs_a_password_and_refuses_when_admin_exists(client):
    assert client.post("/auth/init-admin").status_code == 422
    assert client.post("/auth/init-admin", json={"email": "x@test.hms"}).status_code == 422
    r = client.post("/auth/init-admin", json={"email": "x@test.hms", "password": "LongEnoughPassword1"})
    assert r.status_code == 400


# ---------------- AI configuration endpoints ----------------
@pytest.mark.parametrize("method,path", [("post", "/chat/llm-config"), ("get", "/chat/llm-status")])
def test_llm_configuration_endpoints_are_gone(client, method, path):
    kwargs = {"json": {"api_key": "x"}} if method == "post" else {}
    assert getattr(client, method)(path, **kwargs).status_code in (404, 405)


# ---------------- chat sessions ----------------
@pytest.fixture()
def marcus_session(db):
    session = ChatSession(user_id=sid("user:marcus"), title="private chat")
    db.add(session)
    db.flush()
    db.add(ChatMessage(session_id=session.id, role="user", content="what is my booking total?"))
    db.commit()
    yield session
    db.query(ChatMessage).filter(ChatMessage.session_id == session.id).delete()
    db.query(ChatSession).filter(ChatSession.id == session.id).delete()
    db.commit()


def test_chat_history_is_private_to_the_session_owner(client, marcus_session):
    url = f"/chat/sessions/{marcus_session.id}/messages"
    assert client.get(url).status_code == 403                                                    # anonymous
    assert client.get(url, headers=login(client, "sophia.carter@test.hms")).status_code == 403   # another customer
    assert client.get(url, headers=login(client, "marcus.vance@test.hms")).status_code == 200


def test_other_callers_cannot_take_over_a_signed_in_users_session(db, marcus_session):
    from app.services.chat_service import get_or_create_session
    hijack = get_or_create_session(db, session_id=marcus_session.id, user_id=None)
    assert hijack.id != marcus_session.id and hijack.user_id is None
    other = get_or_create_session(db, session_id=marcus_session.id, user_id=sid("user:sophia"))
    assert other.id != marcus_session.id
    owner = get_or_create_session(db, session_id=marcus_session.id, user_id=sid("user:marcus"))
    assert owner.id == marcus_session.id
    for s in (hijack, other):
        db.query(ChatSession).filter(ChatSession.id == s.id).delete()
    db.commit()


def test_chat_message_length_is_capped(client):
    assert client.post("/chat", json={"message": "a" * 2001}).status_code == 422
    assert client.post("/chat", json={"message": ""}).status_code == 422


# ---------------- platform behaviour ----------------
def test_health_endpoint(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["data"]["database"] == "ok"


def test_unhandled_errors_do_not_leak_details():
    from fastapi.testclient import TestClient
    from app.main import app

    def boom():
        raise RuntimeError("secret internal detail: SELECT * FROM users")

    app.add_api_route("/__boom", boom)
    try:
        r = TestClient(app, raise_server_exceptions=False).get("/__boom")
    finally:
        app.router.routes.pop()
    assert r.status_code == 500
    assert "secret internal detail" not in r.text and "SELECT" not in r.text
