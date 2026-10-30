import re
import uuid
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any, Union
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.guest import Guest
from app.models.hotel import Hotel
from app.services import llm_service

logger = logging.getLogger(__name__)

class StructuredRAGSecurityError(ValueError):
    """Raised when a generated or provided SQL query violates safety guardrails."""
    pass


SCHEMA_DEFINITION_PROMPT = """
You are a PostgreSQL expert for GrandStay Luxury Hotel Management System.
Given the user's natural language request, generate a single, highly accurate PostgreSQL SELECT query.

DATABASE SCHEMA:
- hotels (
    id UUID PRIMARY KEY,
    name VARCHAR,
    address_line1 VARCHAR,
    address_line2 VARCHAR,
    city VARCHAR,
    state VARCHAR,
    country VARCHAR,
    postal_code VARCHAR,
    phone VARCHAR,
    email VARCHAR,
    description TEXT,
    deleted_at TIMESTAMP
  )
- room_types (
    id UUID PRIMARY KEY,
    hotel_id UUID REFERENCES hotels(id),
    name VARCHAR,
    description TEXT,
    base_price NUMERIC,
    guests_allowed INT,
    deleted_at TIMESTAMP
  )
- rooms (
    id UUID PRIMARY KEY,
    room_type_id UUID REFERENCES room_types(id),
    room_number VARCHAR,
    floor INT,
    status VARCHAR, -- 'available', 'occupied', 'maintenance'
    deleted_at TIMESTAMP
  )
- amenities (
    id UUID PRIMARY KEY,
    hotel_id UUID REFERENCES hotels(id),
    room_type_id UUID REFERENCES room_types(id),
    name VARCHAR,
    deleted_at TIMESTAMP
  )
- policies (
    id UUID PRIMARY KEY,
    hotel_id UUID REFERENCES hotels(id),
    policy_type VARCHAR, -- 'cancellation', 'checkin_checkout', 'pet', 'smoking', 'damage'
    description TEXT,
    deleted_at TIMESTAMP
  )
- reviews (
    id UUID PRIMARY KEY,
    guest_id UUID REFERENCES guests(id),
    booking_id UUID REFERENCES bookings(id),
    rating INT, -- 1 to 5
    comment TEXT,
    created_at TIMESTAMP,
    deleted_at TIMESTAMP
  )
- bookings (
    id UUID PRIMARY KEY,
    hotel_id UUID REFERENCES hotels(id),
    guest_id UUID REFERENCES guests(id),
    checkin_date DATE,
    checkout_date DATE,
    total_amount NUMERIC,
    status VARCHAR, -- 'confirmed', 'checked_in', 'checked_out', 'cancelled', 'completed'
    special_requests TEXT,
    created_at TIMESTAMP,
    deleted_at TIMESTAMP
  )
- booking_rooms (
    id UUID PRIMARY KEY,
    booking_id UUID REFERENCES bookings(id),
    room_id UUID REFERENCES rooms(id),
    guest_id UUID REFERENCES guests(id),
    status VARCHAR,
    checkin_date DATE,
    checkout_date DATE,
    room_rate NUMERIC,
    deleted_at TIMESTAMP
  )
- guests (
    id UUID PRIMARY KEY,
    name VARCHAR,
    email VARCHAR,
    phone VARCHAR,
    id_document_number VARCHAR,
    deleted_at TIMESTAMP
  )

STRICT RULES:
1. Output ONLY the raw SQL query. NO markdown code blocks (```sql), NO explanations, NO surrounding text.
2. ONLY generate read-only SELECT queries.
3. For booking queries, join 'hotels' to provide hotel name and city, and select checkin_date, checkout_date, status, and total_amount.
4. For rooms/accommodations, join 'room_types' to provide room type name and base price.
5. When filtering by hotel name from natural language, ALWAYS use ILIKE with wildcards (e.g., h.name ILIKE '%Alpine Peak%') instead of strict '=' equality, as hotel names may have suffixes like '& Spa' or '& Ski Resort'.
6. Filter active rows: WHERE deleted_at IS NULL (or aliases.deleted_at IS NULL).
7. Always use sensible column aliases (e.g., h.name AS hotel_name, rt.name AS room_type_name).
"""


def clean_sql(raw_sql: str) -> str:
    """Removes markdown code fences, comments, and trailing semicolons."""
    cleaned = raw_sql.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    # Strip multi-line comments /* ... */
    cleaned = re.sub(r'/\*.*?\*/', ' ', cleaned, flags=re.DOTALL)
    # Strip single-line comments -- ...
    cleaned = re.sub(r'--.*$', ' ', cleaned, flags=re.MULTILINE)
    # Strip trailing semicolons or whitespace
    cleaned = re.sub(r';+\s*$', '', cleaned).strip()
    return cleaned


def get_table_alias(sql: str, table_name: str) -> Optional[str]:
    """
    Finds the exact alias for `table_name` in FROM or JOIN clauses.
    Returns alias if aliased (e.g., 'b' for 'FROM bookings b'),
    or table_name if unaliased (e.g., 'FROM bookings'),
    or None if table is not referenced.
    """
    pattern = rf'\b(?:FROM|JOIN)\s+{table_name}\s+(?:AS\s+)?([a-zA-Z0-9_]+)'
    m = re.search(pattern, sql, re.IGNORECASE)
    sql_keywords = {
        'where', 'join', 'inner', 'left', 'right', 'cross', 'outer', 'full',
        'on', 'group', 'order', 'limit', 'union', 'using', 'natural', 'lateral'
    }
    if m:
        candidate = m.group(1)
        if candidate.lower() not in sql_keywords:
            return candidate

    if re.search(rf'\b(?:FROM|JOIN)\s+{table_name}\b', sql, re.IGNORECASE):
        return table_name

    return None


def inject_conditions(sql: str, conditions: List[str]) -> str:
    """
    Safely injects `conditions` into the WHERE clause of `sql`.
    If a WHERE clause exists, injects `((c1) AND (c2)) AND ` right after WHERE.
    If no WHERE clause exists, injects ` WHERE (c1) AND (c2) ` before GROUP BY / ORDER BY / LIMIT,
    or at the end of the query.
    """
    if not conditions:
        return sql
    combined = ' AND '.join(f'({c})' for c in conditions)
    m_where = re.search(r'\bWHERE\b', sql, re.IGNORECASE)
    if m_where:
        idx = m_where.end()
        return sql[:idx] + f' ({combined}) AND ' + sql[idx:]
    else:
        m_after = re.search(r'\b(GROUP\s+BY|HAVING|ORDER\s+BY|LIMIT|OFFSET)\b', sql, re.IGNORECASE)
        if m_after:
            idx = m_after.start()
            return sql[:idx] + f' WHERE {combined} ' + sql[idx:]
        else:
            return f'{sql} WHERE {combined}'


def enforce_guardrails_and_scope(
    raw_sql: str,
    guest_ids: Optional[List[str]] = None,
    hotel_id: Optional[Union[str, uuid.UUID]] = None,
    user_logged_in: bool = False,
    is_personal_query: bool = False
) -> str:
    """
    Enforces strict guardrails and programmatic scoping:
    1. Read-Only: Blocks all mutating queries (INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, etc.).
    2. Zero Multiple Statements: Blocks semicolons.
    3. Block Sensitive / Auth Tables: Strictly forbids queries targeting users, refresh_tokens, roles, or pg catalog.
    4. Programmatic User Scoping (in code only):
       - When a user is logged in: appends `guest_id IN ('...')` / `id IN ('...')` for bookings/guests/booking_rooms.
       - When user is NOT logged in and queries personal tables: injects `1 = 0` to guarantee zero data leakage.
    5. Programmatic Hotel Scoping (in code only):
       - If hotel_id is specified: appends `hotel_id = '...'` or `id = '...'` for hotels/room_types/rooms/policies/amenities/reviews/bookings.
    6. LIMIT <= 15:
       - If LIMIT > 15, rewrites to LIMIT 15.
       - If no LIMIT present, appends LIMIT 15.
    """
    sql = clean_sql(raw_sql)
    hotel_id_str = str(hotel_id) if hotel_id else None

    # Guardrail 1: Disallow mutating queries
    forbidden_pattern = (
        r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|TRUNCATE|EXEC|EXECUTE|CREATE|REPLACE|"
        r"GRANT|REVOKE|MERGE|CALL|COPY|VACUUM|LOCK|SET|DO|BEGIN|COMMIT|ROLLBACK)\b"
    )
    if re.search(forbidden_pattern, sql, re.IGNORECASE):
        raise StructuredRAGSecurityError("Security Violation: Only read-only SELECT queries are permitted.")

    # Guardrail 2: Disallow SQL comments (injection/truncation vectors)
    if "--" in raw_sql or "/*" in raw_sql or "*/" in raw_sql:
        raise StructuredRAGSecurityError("Security Violation: SQL comments are strictly prohibited.")

    # Guardrail 3: Disallow multi-statement queries
    if ";" in sql:
        raise StructuredRAGSecurityError("Security Violation: Multiple SQL statements are not permitted.")

    # Guardrail 4: Must start with SELECT or WITH
    if not re.match(r"^\s*(SELECT|WITH)\b", sql, re.IGNORECASE):
        raise StructuredRAGSecurityError("Security Violation: Query must start with SELECT or WITH.")

    # Guardrail 5: Block access to forbidden tables (users, refresh_tokens, roles, system catalog, alembic)
    forbidden_tables = r"\b(users|refresh_tokens|roles|alembic_version|information_schema|pg_\w+)\b"
    if re.search(forbidden_tables, sql, re.IGNORECASE):
        raise StructuredRAGSecurityError("Security Violation: Access to system, authentication, or user credential tables is strictly prohibited.")

    # Guardrail 6: Programmatic Scoping (in code only)
    code_conditions: List[str] = []

    b_alias = get_table_alias(sql, "bookings")
    g_alias = get_table_alias(sql, "guests")
    br_alias = get_table_alias(sql, "booking_rooms")
    bi_alias = get_table_alias(sql, "booking_items")
    bg_alias = get_table_alias(sql, "booking_guests")

    # User Scoping
    if user_logged_in and guest_ids:
        formatted_ids = ", ".join(f"'{gid}'" for gid in guest_ids)
        if b_alias:
            code_conditions.append(f"{b_alias}.guest_id IN ({formatted_ids})")
            code_conditions.append(f"{b_alias}.deleted_at IS NULL")
        if g_alias:
            code_conditions.append(f"{g_alias}.id IN ({formatted_ids})")
            code_conditions.append(f"{g_alias}.deleted_at IS NULL")
        if br_alias:
            code_conditions.append(f"{br_alias}.guest_id IN ({formatted_ids})")
            code_conditions.append(f"{br_alias}.deleted_at IS NULL")
        if bi_alias:
            code_conditions.append(f"{bi_alias}.booking_id IN (SELECT id FROM bookings WHERE guest_id IN ({formatted_ids}) AND deleted_at IS NULL)")
            code_conditions.append(f"{bi_alias}.deleted_at IS NULL")
        if bg_alias:
            code_conditions.append(f"{bg_alias}.guest_id IN ({formatted_ids})")
    elif not user_logged_in and (b_alias or g_alias or br_alias or bi_alias or bg_alias or is_personal_query):
        # Strict zero-leakage security guardrail: Unauthenticated users can never view bookings or guest data
        code_conditions.append("1 = 0")

    # Hotel Scoping
    if hotel_id_str:
        h_alias = get_table_alias(sql, "hotels")
        rt_alias = get_table_alias(sql, "room_types")
        p_alias = get_table_alias(sql, "policies")
        a_alias = get_table_alias(sql, "amenities")
        r_alias = get_table_alias(sql, "rooms")
        rev_alias = get_table_alias(sql, "reviews")

        if h_alias:
            code_conditions.append(f"{h_alias}.id = '{hotel_id_str}'")
            code_conditions.append(f"{h_alias}.deleted_at IS NULL")
        if b_alias and not any(f"{b_alias}.hotel_id" in c for c in code_conditions):
            code_conditions.append(f"{b_alias}.hotel_id = '{hotel_id_str}'")
        if rt_alias:
            code_conditions.append(f"{rt_alias}.hotel_id = '{hotel_id_str}'")
            code_conditions.append(f"{rt_alias}.deleted_at IS NULL")
        if p_alias:
            code_conditions.append(f"{p_alias}.hotel_id = '{hotel_id_str}'")
            code_conditions.append(f"{p_alias}.deleted_at IS NULL")
        if a_alias:
            code_conditions.append(f"{a_alias}.hotel_id = '{hotel_id_str}'")
            code_conditions.append(f"{a_alias}.deleted_at IS NULL")
        if r_alias and not rt_alias:
            code_conditions.append(f"{r_alias}.room_type_id IN (SELECT id FROM room_types WHERE hotel_id = '{hotel_id_str}' AND deleted_at IS NULL)")
            code_conditions.append(f"{r_alias}.deleted_at IS NULL")
        if rev_alias:
            code_conditions.append(f"{rev_alias}.booking_id IN (SELECT id FROM bookings WHERE hotel_id = '{hotel_id_str}' AND deleted_at IS NULL)")
            code_conditions.append(f"{rev_alias}.deleted_at IS NULL")

    # Deduplicate conditions
    unique_conditions = []
    for cond in code_conditions:
        if cond not in unique_conditions:
            unique_conditions.append(cond)

    if unique_conditions:
        sql = inject_conditions(sql, unique_conditions)

    # Guardrail 5: Enforce LIMIT <= 15
    limit_match = re.search(r"\bLIMIT\s+(\d+)\b", sql, re.IGNORECASE)
    if limit_match:
        val = int(limit_match.group(1))
        if val > 15:
            sql = re.sub(r"\bLIMIT\s+\d+\b", "LIMIT 15", sql, flags=re.IGNORECASE)
    else:
        sql = f"{sql.strip()} LIMIT 15"

    return sql


def serialize_value(v: Any) -> Any:
    """Serializes database field types to JSON-safe primitives."""
    if isinstance(v, uuid.UUID):
        return str(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, list):
        return [serialize_value(x) for x in v]
    if isinstance(v, dict):
        return {k: serialize_value(val) for k, val in v.items()}
    return v


def execute_read_only_sql(db: Session, sql: str) -> List[Dict[str, Any]]:
    """
    Executes the validated read-only SQL query against PostgreSQL.
    Fetches up to 15 rows maximum.
    """
    try:
        cursor = db.execute(text(sql))
        raw_rows = cursor.mappings().fetchmany(15)
        return [{k: serialize_value(val) for k, val in dict(r).items()} for r in raw_rows]
    except Exception as e:
        db.rollback()
        raise e


def generate_sql_for_query(
    natural_query: str,
    target_hotel_id: Optional[uuid.UUID] = None,
    target_hotel_name: Optional[str] = None,
    user_logged_in: bool = False,
    user_name: Optional[str] = None
) -> str:
    """
    Uses Gemini to generate a single PostgreSQL SELECT statement based on natural language.
    """
    prompt = f"User Question: \"{natural_query}\"\n"
    if user_logged_in:
        prompt += f"Context: Authenticated user is '{user_name}'. They are asking about their own reservations or hotel details.\n"
    if target_hotel_id:
        prompt += f"Context: Target Hotel ID is '{target_hotel_id}' ({target_hotel_name or 'Hotel'}).\n"

    raw_response = llm_service.call_gemini_cloud_api(
        prompt=prompt,
        system_instruction=SCHEMA_DEFINITION_PROMPT,
        temperature=0.0,
        max_tokens=600
    )
    return clean_sql(raw_response)


def synthesize_nl_response(
    natural_query: str,
    sql_executed: str,
    rows: List[Dict[str, Any]],
    hotel_name: Optional[str] = None,
    user_name: Optional[str] = None,
    extra_context: Optional[str] = None
) -> str:
    """
    Uses Gemini to translate the SQL rows into a natural, warm, and sophisticated concierge response.
    """
    prompt = (
        f"User Question: \"{natural_query}\"\n"
        f"SQL Query Executed: {sql_executed}\n"
        f"Database Results ({len(rows)} records found):\n{rows}\n\n"
    )
    if hotel_name:
        prompt += f"Hotel Context: {hotel_name}\n"
    if user_name:
        prompt += f"Guest Context: {user_name}\n"
    if extra_context:
        prompt += f"Additional Operational Context / Policy:\n{extra_context}\n"

    prompt += (
        "\nINSTRUCTIONS:\n"
        "1. Formulate a warm, sophisticated, and highly accurate AI Concierge response.\n"
        "2. Ground your answer strictly and exclusively in the database results and operational facts above.\n"
        "3. Format dates gracefully (e.g. 'October 28, 2026') and currency nicely ($520.00).\n"
        "4. Never mention raw SQL, table names, or database jargon in the conversational response.\n"
        "5. If 0 records were found:\n"
        "   - If asking about bookings, politely inform the guest that no matching active or upcoming bookings were found under their account.\n"
        "   - If asking about specific amenities/rates, inform them that no verified records were found in the hotel catalog.\n"
        "6. If the guest is asking to cancel a booking, clearly explain policy and refund eligibility based on the records, "
        "and instruct them to complete their cancellation in 'My Trips' / 'My Reservations' at the top of the portal. "
        "Never pretend that you can perform the cancellation directly."
    )

    sys_inst = (
        "You are strictly the warm, sophisticated AI Hotel Concierge for GrandStay Luxury Hotels & Resorts. "
        "Provide elegant, accurate, and completely factual answers based on verified database records."
    )

    return llm_service.call_gemini_cloud_api(
        prompt=prompt,
        system_instruction=sys_inst,
        temperature=0.3,
        max_tokens=1200
    )


def query_structured_rag(
    db: Session,
    query: str,
    user: Optional[User] = None,
    hotel_id: Optional[uuid.UUID] = None,
    hotel_name: Optional[str] = None,
    is_personal_booking: bool = False,
    extra_context: Optional[str] = None
) -> Dict[str, Any]:
    """
    Main entry point for Structured RAG (NL -> SQL -> NL).
    Executes with strict guardrails:
    - Read-only queries only.
    - Limit 15 max.
    - Code-only programmatic scoping for user and hotel.
    """
    user_logged_in = user is not None
    guest_ids: List[str] = []

    if user_logged_in:
        from app.services.chat_service import or_guest_filter
        matching_guests = db.query(Guest).filter(or_guest_filter(user)).all()
        guest_ids = [str(g.id) for g in matching_guests]

    # Resolve hotel name if missing but hotel_id provided
    if hotel_id and not hotel_name:
        h = db.query(Hotel).filter(Hotel.id == hotel_id, Hotel.deleted_at.is_(None)).first()
        if h:
            hotel_name = h.name

    # Step 1: Natural Language -> SQL Generation
    raw_sql = generate_sql_for_query(
        natural_query=query,
        target_hotel_id=hotel_id,
        target_hotel_name=hotel_name,
        user_logged_in=user_logged_in,
        user_name=user.name if user else None
    )

    # Step 2: Enforce Guardrails & Code-Only Programmatic Scoping
    scoped_sql = enforce_guardrails_and_scope(
        raw_sql=raw_sql,
        guest_ids=guest_ids if user_logged_in else None,
        hotel_id=hotel_id,
        user_logged_in=user_logged_in,
        is_personal_query=is_personal_booking
    )

    # Step 3: Execute Read-Only SQL against Database
    try:
        rows = execute_read_only_sql(db=db, sql=scoped_sql)
    except Exception as e:
        logger.warning(f"Structured RAG query execution issue: {e}. Falling back to empty rows.")
        db.rollback()
        rows = []

    # Step 4: SQL Rows -> Natural Language Synthesis
    nl_response = synthesize_nl_response(
        natural_query=query,
        sql_executed=scoped_sql,
        rows=rows,
        hotel_name=hotel_name,
        user_name=user.name if user else None,
        extra_context=extra_context
    )

    # Step 5: Format Citations and Context Data
    citations = []
    for r in rows[:6]:
        if "hotel_name" in r:
            citations.append({
                "source_type": "database_record",
                "title": f"Verified Record - {r['hotel_name']}",
                "relevance_score": 1.0,
                "snippet": f"Check-in: {r.get('checkin_date')}, Status: {r.get('status')}, Total: ${r.get('total_amount', 0)}"
            })
        elif "policy_type" in r:
            citations.append({
                "source_type": "policy",
                "title": f"Policy - {r['policy_type']}",
                "relevance_score": 1.0,
                "snippet": str(r.get('description', ''))[:200]
            })
        elif "base_price" in r:
            citations.append({
                "source_type": "room_catalog",
                "title": f"Room Type - {r.get('name', 'Room')}",
                "relevance_score": 1.0,
                "snippet": f"Base price: ${r.get('base_price')}, Guests allowed: {r.get('guests_allowed')}"
            })

    return {
        "response": nl_response.strip(),
        "citations": citations,
        "context_data": {
            "structured_rag": True,
            "sql_executed": scoped_sql,
            "rows_count": len(rows),
            "rows": rows[:5],
            "hotel_id": str(hotel_id) if hotel_id else None
        }
    }
