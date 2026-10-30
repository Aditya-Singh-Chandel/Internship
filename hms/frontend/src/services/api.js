/**
 * GrandStay Luxury API Client
 * Connects the React application to the FastAPI backend.
 */

const API_BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

// Helper for standard JSON headers with optional Bearer token
function getHeaders(token = null, isFormData = false) {
  const headers = {};
  if (!isFormData) {
    headers["Content-Type"] = "application/json";
  }
  const effectiveToken = 
    token || 
    (typeof window !== "undefined" && window.localStorage 
      ? (localStorage.getItem("grandstay_customer_token") || localStorage.getItem("token")) 
      : null);

  if (effectiveToken) {
    headers["Authorization"] = `Bearer ${effectiveToken}`;
  }
  return headers;
}

// Helper to extract clean error message
async function handleResponse(response) {
  const text = await response.text();
  let json;
  try {
    json = JSON.parse(text);
  } catch {
    json = { message: text || "An unexpected network error occurred." };
  }

  if (!response.ok) {
    const errorMsg = json.message || json.detail || `Request failed with status ${response.status}`;
    const err = new Error(errorMsg);
    err.status = response.status;
    err.data = json;
    throw err;
  }
  return json;
}

// Centralized singleton refresh promise to deduplicate concurrent refresh calls
let refreshPromise = null;

async function refreshAccessToken() {
  if (refreshPromise) return refreshPromise;

  refreshPromise = (async () => {
    try {
      // The browser automatically attaches the HttpOnly cookie when credentials: "include" is used
      const res = await fetch(`${API_BASE}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include'
      });

      if (!res.ok) {
        throw new Error('Refresh token expired or invalid');
      }

      const json = await res.json();
      const newAccessToken = json.data?.access_token || json.access_token;

      if (!newAccessToken) {
        throw new Error('Missing access token in refresh response');
      }

      // Store only the short-lived access token in localStorage for session persistence
      if (typeof window !== 'undefined' && window.localStorage) {
        localStorage.setItem('grandstay_customer_token', newAccessToken);
        window.dispatchEvent(new CustomEvent('grandstay_token_refreshed', { 
          detail: { token: newAccessToken } 
        }));
      }

      return newAccessToken;
    } catch (err) {
      if (typeof window !== 'undefined' && window.localStorage) {
        localStorage.removeItem('grandstay_customer_token');
        localStorage.removeItem('grandstay_customer_user');
        window.dispatchEvent(new Event('grandstay_auth_logout'));
      }
      throw err;
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

// Transparent fetch wrapper with automatic token refresh on 401
async function apiFetch(url, options = {}) {
  const opts = { ...options };
  opts.headers = { ...opts.headers };
  opts.credentials = 'include'; // Ensure cookies are sent cross-origin

  let res = await fetch(url, opts);

  // If 401 Unauthorized and not an auth login/refresh request, attempt silent token refresh via HttpOnly cookie
  const isAuthEndpoint = typeof url === 'string' && (url.includes('/auth/login') || url.includes('/auth/refresh'));
  if (res.status === 401 && !isAuthEndpoint) {
    try {
      const newToken = await refreshAccessToken();
      if (newToken) {
        opts.headers['Authorization'] = `Bearer ${newToken}`;
        res = await fetch(url, opts);
      }
    } catch (e) {
      // Refresh failed, proceed with original 401 response
    }
  }

  return res;
}

export const api = {
  // --- Public Hotel Discovery ---
  async getHotels(limit = 50) {
    const res = await apiFetch(`${API_BASE}/hotels?limit=${limit}`);
    const json = await handleResponse(res);
    return json.data || [];
  },

  async getHotel(id) {
    const res = await apiFetch(`${API_BASE}/hotels/${id}`);
    const json = await handleResponse(res);
    return json.data;
  },

  async getRoomTypes(hotelId = null, checkin = null, checkout = null, roomsCount = 1, onlyAvailable = false) {
    let url = `${API_BASE}/room-types?limit=50`;
    if (hotelId) url += `&hotel_id=${hotelId}`;
    if (checkin && checkout) {
      url += `&checkin_date=${checkin}&checkout_date=${checkout}&rooms_count=${roomsCount}`;
      if (onlyAvailable) url += `&only_available=true`;
    }
    const res = await apiFetch(url);
    const json = await handleResponse(res);
    return json.data || [];
  },

  async getPolicies(hotelId = null) {
    const url = hotelId ? `${API_BASE}/policies?hotel_id=${hotelId}&limit=50` : `${API_BASE}/policies?limit=50`;
    const res = await apiFetch(url);
    const json = await handleResponse(res);
    return json.data || [];
  },

  async getAmenities(hotelId = null) {
    const url = hotelId ? `${API_BASE}/amenities?hotel_id=${hotelId}&limit=50` : `${API_BASE}/amenities?limit=50`;
    const res = await apiFetch(url);
    const json = await handleResponse(res);
    return json.data || [];
  },

  async getReviews(hotelId = null, token = null) {
    const headers = token ? { Authorization: `Bearer ${token}` } : {};
    const url = hotelId 
      ? `${API_BASE}/reviews?hotel_id=${hotelId}&limit=100` 
      : `${API_BASE}/reviews?limit=100`;
    const res = await apiFetch(url, { headers });
    const json = await handleResponse(res);
    return json.data || [];
  },

  // --- Dynamic Media from PostgreSQL Media Table ---
  async getMedia(hotelId = null, roomTypeId = null) {
    const params = new URLSearchParams({ limit: "100" });
    if (hotelId) params.append("hotel_id", hotelId);
    if (roomTypeId) params.append("room_type_id", roomTypeId);
    const res = await apiFetch(`${API_BASE}/media?${params.toString()}`);
    const json = await handleResponse(res);
    return json.data || [];
  },

  async getAllMedia() {
    const res = await apiFetch(`${API_BASE}/media?limit=100`);
    const json = await handleResponse(res);
    return json.data || [];
  },

  // --- Customer Authentication ---
  async login(username, password) {
    const body = new URLSearchParams({
      username,
      password,
      grant_type: "password"
    });
    const res = await apiFetch(`${API_BASE}/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: body.toString()
    });
    return handleResponse(res);
  },

  async registerCustomer(name, email, password, phone = "") {
    const res = await apiFetch(`${API_BASE}/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name,
        email,
        password,
        phone,
        role: "customer"
      })
    });
    return handleResponse(res);
  },

  async getCurrentUser(token) {
    const res = await apiFetch(`${API_BASE}/auth/me`, {
      headers: getHeaders(token)
    });
    const json = await handleResponse(res);
    return json.data;
  },

  async refreshToken() {
    const res = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include"
    });
    return handleResponse(res);
  },

  async logout(token = null) {
    const headers = getHeaders(token);
    const res = await fetch(`${API_BASE}/auth/logout`, {
      method: "POST",
      headers,
      credentials: "include"
    });
    return handleResponse(res);
  },

  // --- Customer Bookings & Trips ---
  async getMyBookings(token) {
    const res = await apiFetch(`${API_BASE}/bookings?my_bookings=true&limit=50`, {
      headers: getHeaders(token)
    });
    const json = await handleResponse(res);
    return json.data || [];
  },

  async createBooking(bookingData, token) {
    const res = await apiFetch(`${API_BASE}/bookings`, {
      method: "POST",
      headers: getHeaders(token),
      body: JSON.stringify(bookingData)
    });
    return handleResponse(res);
  },

  async cancelBooking(bookingId, reason, token) {
    const res = await apiFetch(`${API_BASE}/bookings/${bookingId}/cancel`, {
      method: "PATCH",
      headers: getHeaders(token),
      body: JSON.stringify({ reason: reason || "Customer requested cancellation via portal." })
    });
    return handleResponse(res);
  },

  async submitReview(reviewData, token) {
    // reviewData: { booking_id, rating, comment }
    const form = new URLSearchParams();
    form.append("booking_id", reviewData.booking_id);
    form.append("rating", reviewData.rating.toString());
    if (reviewData.comment) form.append("comment", reviewData.comment);

    const res = await apiFetch(`${API_BASE}/reviews`, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": `Bearer ${token}`
      },
      body: form.toString()
    });
    return handleResponse(res);
  },

  async updateReview(reviewId, reviewData, token) {
    const form = new URLSearchParams();
    if (reviewData.rating !== undefined && reviewData.rating !== null) {
      form.append("rating", reviewData.rating.toString());
    }
    if (reviewData.comment !== undefined) {
      form.append("comment", reviewData.comment);
    }
    const res = await apiFetch(`${API_BASE}/reviews/${reviewId}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": `Bearer ${token}`
      },
      body: form.toString()
    });
    return handleResponse(res);
  },

  async deleteReview(reviewId, token) {
    const res = await apiFetch(`${API_BASE}/reviews/${reviewId}`, {
      method: "DELETE",
      headers: getHeaders(token)
    });
    return handleResponse(res);
  },

  // --- GrandStay AI Concierge ---
  async sendChatMessage(message, hotelId = null, sessionId = null, token = null) {
    const payload = { message };
    if (hotelId) payload.hotel_id = hotelId;
    if (sessionId) payload.session_id = sessionId;

    const res = await apiFetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: getHeaders(token),
      body: JSON.stringify(payload)
    });
    const json = await handleResponse(res);
    return json.data;
  },

  // ==========================================================================
  // OPERATIONS PORTAL API (Admin, Owner, Manager, Staff)
  // ==========================================================================

  // --- Front Desk & Stays Management ---
  async getAllBookings(params = {}, token) {
    const q = new URLSearchParams(params).toString();
    const res = await apiFetch(`${API_BASE}/bookings?${q}`, {
      headers: getHeaders(token)
    });
    const json = await handleResponse(res);
    return json.data || [];
  },

  async updateBooking(bookingId, updateData, token) {
    const form = new URLSearchParams();
    for (const [k, v] of Object.entries(updateData)) {
      if (v !== undefined && v !== null) form.append(k, v.toString());
    }
    const res = await apiFetch(`${API_BASE}/bookings/${bookingId}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": `Bearer ${token}`
      },
      body: form.toString()
    });
    return handleResponse(res);
  },

  async getBookingRooms(params = {}, token) {
    const q = new URLSearchParams(params).toString();
    const res = await apiFetch(`${API_BASE}/booking-rooms?${q}`, {
      headers: getHeaders(token)
    });
    const json = await handleResponse(res);
    return json.data || [];
  },

  async assignBookingRoom(data, token) {
    // data: { booking_item_id, room_id, guest_id, status }
    const form = new URLSearchParams();
    for (const [k, v] of Object.entries(data)) {
      if (v !== undefined && v !== null) form.append(k, v.toString());
    }
    const res = await apiFetch(`${API_BASE}/booking-rooms`, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": `Bearer ${token}`
      },
      body: form.toString()
    });
    return handleResponse(res);
  },

  async deleteBookingRoom(id, token) {
    const res = await apiFetch(`${API_BASE}/booking-rooms/${id}`, {
      method: "DELETE",
      headers: getHeaders(token)
    });
    return handleResponse(res);
  },

  // --- Physical Rooms Inventory ---
  async getRooms(params = {}, token = null) {
    const q = new URLSearchParams(params).toString();
    const res = await apiFetch(`${API_BASE}/rooms?${q}`, {
      headers: getHeaders(token)
    });
    const json = await handleResponse(res);
    return json.data || [];
  },

  async createRoom(data, token) {
    const form = new URLSearchParams();
    for (const [k, v] of Object.entries(data)) {
      if (v !== undefined && v !== null) form.append(k, v.toString());
    }
    const res = await apiFetch(`${API_BASE}/rooms`, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": `Bearer ${token}`
      },
      body: form.toString()
    });
    return handleResponse(res);
  },

  async updateRoom(roomId, data, token) {
    const form = new URLSearchParams();
    for (const [k, v] of Object.entries(data)) {
      if (v !== undefined && v !== null) form.append(k, v.toString());
    }
    const res = await apiFetch(`${API_BASE}/rooms/${roomId}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": `Bearer ${token}`
      },
      body: form.toString()
    });
    return handleResponse(res);
  },

  async deleteRoom(roomId, token) {
    const res = await apiFetch(`${API_BASE}/rooms/${roomId}`, {
      method: "DELETE",
      headers: getHeaders(token)
    });
    return handleResponse(res);
  },

  // --- Room Types & Nightly Rates ---
  async createRoomType(data, token) {
    const form = new URLSearchParams();
    for (const [k, v] of Object.entries(data)) {
      if (v !== undefined && v !== null) form.append(k, v.toString());
    }
    const res = await apiFetch(`${API_BASE}/room-types`, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": `Bearer ${token}`
      },
      body: form.toString()
    });
    return handleResponse(res);
  },

  async updateRoomType(id, data, token) {
    const form = new URLSearchParams();
    for (const [k, v] of Object.entries(data)) {
      if (v !== undefined && v !== null) form.append(k, v.toString());
    }
    const res = await apiFetch(`${API_BASE}/room-types/${id}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": `Bearer ${token}`
      },
      body: form.toString()
    });
    return handleResponse(res);
  },

  async deleteRoomType(id, token) {
    const res = await apiFetch(`${API_BASE}/room-types/${id}`, {
      method: "DELETE",
      headers: getHeaders(token)
    });
    return handleResponse(res);
  },

  // --- Operational Policies ---
  async createPolicy(data, token) {
    const form = new URLSearchParams();
    for (const [k, v] of Object.entries(data)) {
      if (v !== undefined && v !== null) form.append(k, v.toString());
    }
    const res = await apiFetch(`${API_BASE}/policies`, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": `Bearer ${token}`
      },
      body: form.toString()
    });
    return handleResponse(res);
  },

  async updatePolicy(id, data, token) {
    const form = new URLSearchParams();
    for (const [k, v] of Object.entries(data)) {
      if (v !== undefined && v !== null) form.append(k, v.toString());
    }
    const res = await apiFetch(`${API_BASE}/policies/${id}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": `Bearer ${token}`
      },
      body: form.toString()
    });
    return handleResponse(res);
  },

  async deletePolicy(id, token) {
    const res = await apiFetch(`${API_BASE}/policies/${id}`, {
      method: "DELETE",
      headers: getHeaders(token)
    });
    return handleResponse(res);
  },

  // --- Document Knowledge & RAG Sync ---
  async getHotelDocuments(hotelId, token = null) {
    const res = await apiFetch(`${API_BASE}/hotels/${hotelId}/documents`, {
      headers: getHeaders(token)
    });
    const json = await handleResponse(res);
    return json.data || [];
  },

  async uploadHotelDocument(hotelId, file, title = "", category = "general", token) {
    const formData = new FormData();
    formData.append("file", file);
    if (title) formData.append("title", title);
    if (category) formData.append("category", category);

    const res = await apiFetch(`${API_BASE}/hotels/${hotelId}/documents/upload`, {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${token}`
      },
      body: formData
    });
    return handleResponse(res);
  },

  async syncHotelDatabaseKnowledge(hotelId, token) {
    const res = await apiFetch(`${API_BASE}/hotels/${hotelId}/documents/sync`, {
      method: "POST",
      headers: getHeaders(token)
    });
    return handleResponse(res);
  },

  async deleteHotelDocument(hotelId, documentId, token) {
    const res = await apiFetch(`${API_BASE}/hotels/${hotelId}/documents/${documentId}`, {
      method: "DELETE",
      headers: getHeaders(token)
    });
    return handleResponse(res);
  },

  // --- Media & Photos Management ---
  async getMedia(params = {}, token = null) {
    const q = new URLSearchParams(params).toString();
    const res = await apiFetch(`${API_BASE}/media?${q}`, {
      headers: getHeaders(token)
    });
    const json = await handleResponse(res);
    return json.data || [];
  },

  async createMedia(data, token) {
    const form = new URLSearchParams();
    for (const [k, v] of Object.entries(data)) {
      if (v !== undefined && v !== null) form.append(k, v.toString());
    }
    const res = await apiFetch(`${API_BASE}/media`, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": `Bearer ${token}`
      },
      body: form.toString()
    });
    return handleResponse(res);
  },

  async updateMedia(id, data, token) {
    const form = new URLSearchParams();
    for (const [k, v] of Object.entries(data)) {
      if (v !== undefined && v !== null) form.append(k, v.toString());
    }
    const res = await apiFetch(`${API_BASE}/media/${id}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": `Bearer ${token}`
      },
      body: form.toString()
    });
    return handleResponse(res);
  },

  async deleteMedia(id, token) {
    const res = await apiFetch(`${API_BASE}/media/${id}`, {
      method: "DELETE",
      headers: getHeaders(token)
    });
    return handleResponse(res);
  },

  // --- Team & Users Management ---
  async getUsers(params = {}, token) {
    const q = new URLSearchParams(params).toString();
    const res = await apiFetch(`${API_BASE}/users?${q}`, {
      headers: getHeaders(token)
    });
    const json = await handleResponse(res);
    return json.data || [];
  },

  async createUser(data, token) {
    const form = new URLSearchParams();
    for (const [k, v] of Object.entries(data)) {
      if (Array.isArray(v)) {
        for (const item of v) form.append(k, item.toString());
      } else if (v !== undefined && v !== null) {
        form.append(k, v.toString());
      }
    }
    const res = await apiFetch(`${API_BASE}/users`, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": `Bearer ${token}`
      },
      body: form.toString()
    });
    return handleResponse(res);
  },

  async updateUser(id, data, token) {
    const form = new URLSearchParams();
    for (const [k, v] of Object.entries(data)) {
      if (Array.isArray(v)) {
        for (const item of v) form.append(k, item.toString());
      } else if (v !== undefined && v !== null) {
        form.append(k, v.toString());
      }
    }
    const res = await apiFetch(`${API_BASE}/users/${id}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": `Bearer ${token}`
      },
      body: form.toString()
    });
    return handleResponse(res);
  },

  async deleteUser(id, token) {
    const res = await apiFetch(`${API_BASE}/users/${id}`, {
      method: "DELETE",
      headers: getHeaders(token)
    });
    return handleResponse(res);
  },

  async getRoles(token) {
    const res = await apiFetch(`${API_BASE}/roles`, {
      headers: getHeaders(token)
    });
    const json = await handleResponse(res);
    return json.data || [];
  },

  // --- Hotels Management (Admin / Owner) ---
  async createHotel(data, token) {
    const form = new URLSearchParams();
    for (const [k, v] of Object.entries(data)) {
      if (v !== undefined && v !== null) form.append(k, v.toString());
    }
    const res = await apiFetch(`${API_BASE}/hotels`, {
      method: "POST",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": `Bearer ${token}`
      },
      body: form.toString()
    });
    return handleResponse(res);
  },

  async updateHotel(id, data, token) {
    const form = new URLSearchParams();
    for (const [k, v] of Object.entries(data)) {
      if (v !== undefined && v !== null) form.append(k, v.toString());
    }
    const res = await apiFetch(`${API_BASE}/hotels/${id}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": `Bearer ${token}`
      },
      body: form.toString()
    });
    return handleResponse(res);
  },

  // --- Guests Directory ---
  async getGuests(params = {}, token) {
    const q = new URLSearchParams(params).toString();
    const res = await apiFetch(`${API_BASE}/guests?${q}`, {
      headers: getHeaders(token)
    });
    const json = await handleResponse(res);
    return json.data || [];
  }
};
