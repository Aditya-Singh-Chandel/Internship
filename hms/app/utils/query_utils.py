import math
from sqlalchemy import asc, desc


# ---------------------------------------------------------------------------
# Operator definitions
# ---------------------------------------------------------------------------

OPERATOR_MAP = {
    "eq":   lambda col, val: col == val,
    "lt":   lambda col, val: col < val,
    "gt":   lambda col, val: col > val,
    "lte":  lambda col, val: col <= val,
    "gte":  lambda col, val: col >= val,
    "like": lambda col, val: col.ilike(f"%{val}%"),
}


# ---------------------------------------------------------------------------
# Reserved parameter keys (excluded from filter extraction)
# ---------------------------------------------------------------------------

BASE_RESERVED = {"sort_by", "sort_order", "include_deleted", "is_deleted", "page", "limit"}


def filter_active(query, model, query_params: dict | None = None):
    """
    Filter out soft-deleted records (deleted_at is None),
    unless the caller explicitly specified 'is_deleted' or 'include_deleted' in query_params.
    """
    if hasattr(model, "deleted_at"):
        if query_params:
            if "is_deleted" in query_params and query_params["is_deleted"] is not None:
                is_del = str(query_params.get("is_deleted", "")).lower() in ("true", "1")
                if is_del:
                    return query.filter(model.deleted_at.isnot(None))
                return query.filter(model.deleted_at.is_(None))
            if str(query_params.get("include_deleted", "")).lower() in ("true", "1"):
                return query
        return query.filter(model.deleted_at.is_(None))
    return query


# ---------------------------------------------------------------------------
# Extract pre-validated filters from query params
# ---------------------------------------------------------------------------

def extract_filters(query_params: dict, extra_reserved: set | None = None):
    """
    Convert query params into structured filter/sort dicts.
    Pairs fields with their corresponding operator keys (e.g., 'price' with 'price_op').

    Args:
        query_params:    dict of already-typed query values (from locals())
        extra_reserved:  additional param keys to skip (e.g. "month", "year")

    Returns:
        dict with keys: filters, sort_by, sort_order
    """
    reserved = BASE_RESERVED | (extra_reserved or set())

    filters = []

    for key, value in query_params.items():
        if key in reserved or key.endswith("_op"):
            continue

        op_key = f"{key}_op"
        op = query_params.get(op_key, "eq")
        # Enum values -> plain string
        op = op.value if hasattr(op, "value") else op

        filters.append({"field": key, "op": op, "value": value})

    # Enum values -> plain string for sort fields too
    sort_by = query_params.get("sort_by")
    if sort_by and hasattr(sort_by, "value"):
        sort_by = sort_by.value

    sort_order = query_params.get("sort_order", "asc")
    if hasattr(sort_order, "value"):
        sort_order = sort_order.value

    return {
        "filters": filters,
        "sort_by": sort_by,
        "sort_order": sort_order,
    }


# ---------------------------------------------------------------------------
# Query application helpers
# ---------------------------------------------------------------------------

def apply_filters(query, model, filters: list):
    """Apply a list of validated filter dicts to a SQLAlchemy query."""
    for f in filters:
        column = getattr(model, f["field"])
        op_func = OPERATOR_MAP[f["op"]]
        query = query.filter(op_func(column, f["value"]))
    return query


def apply_sorting(query, model, sort_by: str | None, sort_order: str = "asc"):
    """Apply ORDER BY to a SQLAlchemy query."""
    if sort_by:
        column = getattr(model, sort_by)
        query = query.order_by(
            desc(column) if sort_order == "desc" else asc(column)
        )
    return query


# ---------------------------------------------------------------------------
# Pagination helpers
# ---------------------------------------------------------------------------

def paginate_query(query, query_params: dict | None = None):
    """
    Paginate a SQLAlchemy query based on 'page' and 'limit' in query_params.
    Returns: (items, pagination_dict)
    """
    params = query_params or {}
    try:
        page = max(1, int(params.get("page") or 1))
    except (ValueError, TypeError):
        page = 1

    try:
        limit = max(1, int(params.get("limit") or 10))
    except (ValueError, TypeError):
        limit = 10

    total = query.count()
    total_pages = math.ceil(total / limit) if total > 0 else 0
    items = query.offset((page - 1) * limit).limit(limit).all()

    return items, {
        "total": total,
        "page": page,
        "limit": limit,
        "total_pages": total_pages,
    }


def paginate_and_format(query, entity_key: str, query_params: dict | None = None):
    """
    Helper that executes pagination and returns standard response dictionary.
    """
    items, meta = paginate_query(query, query_params)
    return {
        "total": meta["total"],
        "page": meta["page"],
        "limit": meta["limit"],
        "total_pages": meta["total_pages"],
        entity_key: items,
    }

