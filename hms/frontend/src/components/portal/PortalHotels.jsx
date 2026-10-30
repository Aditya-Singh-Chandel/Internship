import React, { useState } from "react";
import { api } from "../../services/api";

export default function PortalHotels({
  hotels = [],
  activeHotel,
  onSelectHotel,
  token,
  userRole,
  onRefresh
}) {
  const [showModal, setShowModal] = useState(false);
  const [editingHotel, setEditingHotel] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const [formData, setFormData] = useState({
    name: "",
    address_line1: "",
    address_line2: "",
    city: "",
    state: "",
    country: "",
    postal_code: "",
    phone: "",
    email: "",
    description: ""
  });

  const canManage = ["admin", "owner"].includes(userRole);

  const openAdd = () => {
    setFormData({
      name: "",
      address_line1: "",
      address_line2: "",
      city: "",
      state: "",
      country: "",
      postal_code: "",
      phone: "",
      email: "",
      description: ""
    });
    setEditingHotel(null);
    setError(null);
    setSuccess(null);
    setShowModal(true);
  };

  const openEdit = (h) => {
    setFormData({
      name: h.name || "",
      address_line1: h.address_line1 || "",
      address_line2: h.address_line2 || "",
      city: h.city || "",
      state: h.state || "",
      country: h.country || "",
      postal_code: h.postal_code || "",
      phone: h.phone || "",
      email: h.email || "",
      description: h.description || ""
    });
    setEditingHotel(h);
    setError(null);
    setSuccess(null);
    setShowModal(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.name || !formData.city || !formData.country || !formData.address_line1) {
      setError("Please complete all required address and hotel identity fields.");
      return;
    }

    setIsSubmitting(true);
    setError(null);
    setSuccess(null);

    try {
      const payload = {
        name: formData.name.trim(),
        address_line1: formData.address_line1.trim(),
        address_line2: formData.address_line2.trim() || undefined,
        city: formData.city.trim(),
        state: formData.state.trim() || formData.city.trim(),
        country: formData.country.trim(),
        postal_code: formData.postal_code.trim() || "10001",
        phone: formData.phone.trim() || undefined,
        email: formData.email.trim() || undefined,
        description: formData.description.trim() || undefined
      };

      if (editingHotel) {
        await api.updateHotel(editingHotel.id, payload, token);
        setSuccess(`Updated property profile for "${formData.name}" successfully!`);
      } else {
        await api.createHotel(payload, token);
        setSuccess(`Registered new luxury property "${formData.name}" into portfolio!`);
      }
      setShowModal(false);
      if (onRefresh) onRefresh();
    } catch (err) {
      setError(err.message || "Failed to save hotel profile.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      {/* Top Banner */}
      <div className="portal-banner">
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div
            style={{
              width: 44,
              height: 44,
              borderRadius: 12,
              background: "rgba(197, 155, 39, 0.15)",
              border: "1px solid rgba(197, 155, 39, 0.3)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 22
            }}
          >
            🏢
          </div>
          <div>
            <h1 className="portal-banner-title">Property Portfolio Management</h1>
            <p className="portal-banner-subtitle">
              Multi-resort directory, location geocoding, and property credentials
            </p>
          </div>
        </div>

        {canManage && (
          <button onClick={openAdd} className="portal-btn-gold">
            <span>+</span>
            <span>Register New Property</span>
          </button>
        )}
      </div>

      {/* Notifications */}
      {error && (
        <div className="portal-alert-error">
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <strong>⚠️ Error:</strong>
            <span>{error}</span>
          </div>
          <button
            onClick={() => setError(null)}
            style={{ background: "none", border: "none", color: "#fca5a5", cursor: "pointer", fontSize: 16 }}
          >
            ✕
          </button>
        </div>
      )}
      {success && (
        <div className="portal-alert-success">
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <strong>✓ Success:</strong>
            <span>{success}</span>
          </div>
          <button
            onClick={() => setSuccess(null)}
            style={{ background: "none", border: "none", color: "#6ee7b7", cursor: "pointer", fontSize: 16 }}
          >
            ✕
          </button>
        </div>
      )}

      {/* Hotel Cards Grid */}
      <div className="portal-grid-3">
        {hotels.map((h) => {
          const isActive = activeHotel?.id === h.id;
          const heroMedia = h.media?.find((m) => m.is_primary) || h.media?.[0];
          const roomCount = h.rooms?.length || 0;
          const suiteCount = h.room_types?.length || 0;

          return (
            <div
              key={h.id}
              className="portal-card"
              style={{
                padding: 0,
                overflow: "hidden",
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
                borderColor: isActive ? "rgba(197, 155, 39, 0.8)" : "rgba(255, 255, 255, 0.08)",
                boxShadow: isActive ? "0 0 24px rgba(197, 155, 39, 0.2)" : undefined
              }}
            >
              <div>
                {/* Hero preview */}
                <div style={{ position: "relative", width: "100%", aspectRatio: "16 / 9", background: "#060910" }}>
                  <img
                    src={
                      heroMedia?.image_url ||
                      "https://images.unsplash.com/photo-1542314831-068cd1dbfeeb?auto=format&fit=crop&w=1200&q=80"
                    }
                    alt={h.name}
                    style={{ width: "100%", height: "100%", objectFit: "cover" }}
                  />
                  <div
                    style={{
                      position: "absolute",
                      inset: 0,
                      background: "linear-gradient(to top, rgba(7, 10, 18, 0.95) 0%, rgba(7, 10, 18, 0.3) 50%, transparent 100%)"
                    }}
                  />

                  {isActive && (
                    <div
                      style={{
                        position: "absolute",
                        top: 12,
                        right: 12,
                        padding: "4px 10px",
                        borderRadius: 9999,
                        background: "#dfc471",
                        color: "#070a12",
                        fontSize: 11,
                        fontWeight: 700,
                        boxShadow: "0 2px 8px rgba(0,0,0,0.5)"
                      }}
                    >
                      ✓ Active Workplace
                    </div>
                  )}

                  <div style={{ position: "absolute", bottom: 12, left: 16, right: 16 }}>
                    <h3
                      style={{
                        fontFamily: "'Playfair Display', Georgia, serif",
                        fontSize: "1.15rem",
                        fontWeight: 700,
                        color: "#ffffff",
                        margin: 0
                      }}
                    >
                      {h.name}
                    </h3>
                    <div style={{ fontSize: 12, color: "#dfc471", marginTop: 2, display: "flex", alignItems: "center", gap: 4 }}>
                      <span>📍</span>
                      <span>
                        {h.city}, {h.country}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Details */}
                <div style={{ padding: "18px 20px", display: "flex", flexDirection: "column", gap: 12 }}>
                  <p
                    style={{
                      fontSize: 12,
                      color: "#94a3b8",
                      lineHeight: 1.5,
                      margin: 0,
                      display: "-webkit-box",
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: "vertical",
                      overflow: "hidden"
                    }}
                  >
                    {h.description || "World-class luxury sanctuary curated for high-touch hospitality and rejuvenation."}
                  </p>

                  <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
                    <div
                      style={{
                        padding: 10,
                        borderRadius: 10,
                        background: "rgba(6, 9, 16, 0.6)",
                        border: "1px solid rgba(255, 255, 255, 0.05)"
                      }}
                    >
                      <div style={{ fontSize: 10, textTransform: "uppercase", color: "#64748b" }}>Suite Types</div>
                      <div style={{ fontSize: 16, fontWeight: 700, color: "#ffffff", fontFamily: "monospace", marginTop: 2 }}>
                        {suiteCount}
                      </div>
                    </div>
                    <div
                      style={{
                        padding: 10,
                        borderRadius: 10,
                        background: "rgba(6, 9, 16, 0.6)",
                        border: "1px solid rgba(255, 255, 255, 0.05)"
                      }}
                    >
                      <div style={{ fontSize: 10, textTransform: "uppercase", color: "#64748b" }}>Physical Rooms</div>
                      <div style={{ fontSize: 16, fontWeight: 700, color: "#dfc471", fontFamily: "monospace", marginTop: 2 }}>
                        {roomCount}
                      </div>
                    </div>
                  </div>

                  <div style={{ fontSize: 12, color: "#94a3b8", display: "flex", flexDirection: "column", gap: 4, paddingTop: 4 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ color: "#64748b" }}>📞 Phone:</span>
                      <span style={{ color: "#cbd5e1", fontFamily: "monospace" }}>{h.phone || "Not set"}</span>
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ color: "#64748b" }}>✉️ Email:</span>
                      <span style={{ color: "#cbd5e1", fontFamily: "monospace", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {h.email || "concierge@grandstay.com"}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Actions */}
              <div
                style={{
                  padding: "14px 20px",
                  background: "rgba(6, 9, 16, 0.8)",
                  borderTop: "1px solid rgba(255, 255, 255, 0.06)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  gap: 8
                }}
              >
                {!isActive ? (
                  <button
                    onClick={() => onSelectHotel && onSelectHotel(h)}
                    className="portal-btn-secondary"
                    style={{ flex: 1, justifyContent: "center" }}
                  >
                    Switch Operations Here
                  </button>
                ) : (
                  <span style={{ fontSize: 12, color: "#dfc471", fontWeight: 600, paddingLeft: 4 }}>
                    Managing Now
                  </span>
                )}

                {canManage && (
                  <button onClick={() => openEdit(h)} className="portal-btn-secondary">
                    ✏️ Edit Profile
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Add / Edit Hotel Modal */}
      {showModal && (
        <div className="portal-modal-backdrop" onClick={() => setShowModal(false)}>
          <div className="portal-modal-box" onClick={(e) => e.stopPropagation()}>
            <div className="portal-modal-header">
              <div>
                <h3 className="portal-card-title">
                  {editingHotel ? "Edit Property Profile" : "Register Luxury Property"}
                </h3>
                <p className="portal-card-subtitle">
                  Set location credentials, guest contact info, and identity
                </p>
              </div>
              <button onClick={() => setShowModal(false)} className="portal-modal-close">
                ✕
              </button>
            </div>

            <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div className="portal-form-group">
                <label className="portal-label">Property Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. GrandStay Alpine Chalet & Spa"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="portal-input"
                />
              </div>

              <div className="portal-form-group">
                <label className="portal-label">Street Address Line 1 *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. 742 Evergreen Boulevard"
                  value={formData.address_line1}
                  onChange={(e) => setFormData({ ...formData, address_line1: e.target.value })}
                  className="portal-input"
                />
              </div>

              <div className="portal-form-row-2">
                <div className="portal-form-group">
                  <label className="portal-label">City *</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Aspen"
                    value={formData.city}
                    onChange={(e) => setFormData({ ...formData, city: e.target.value })}
                    className="portal-input"
                  />
                </div>
                <div className="portal-form-group">
                  <label className="portal-label">Country *</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. United States"
                    value={formData.country}
                    onChange={(e) => setFormData({ ...formData, country: e.target.value })}
                    className="portal-input"
                  />
                </div>
              </div>

              <div className="portal-form-row-2">
                <div className="portal-form-group">
                  <label className="portal-label">Contact Phone</label>
                  <input
                    type="tel"
                    placeholder="+1 (800) 555-0199"
                    value={formData.phone}
                    onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                    className="portal-input"
                    style={{ fontFamily: "monospace" }}
                  />
                </div>
                <div className="portal-form-group">
                  <label className="portal-label">Contact Email</label>
                  <input
                    type="email"
                    placeholder="concierge@grandstay.com"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    className="portal-input"
                    style={{ fontFamily: "monospace" }}
                  />
                </div>
              </div>

              <div className="portal-form-group">
                <label className="portal-label">Property Description & Experience</label>
                <textarea
                  rows="3"
                  placeholder="Describe the architectural heritage, scenic vistas, and luxury offerings..."
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  className="portal-textarea"
                />
              </div>

              <div
                style={{
                  display: "flex",
                  justifyContent: "flex-end",
                  gap: 12,
                  paddingTop: 16,
                  borderTop: "1px solid rgba(255, 255, 255, 0.08)"
                }}
              >
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="portal-btn-secondary"
                >
                  Cancel
                </button>
                <button type="submit" disabled={isSubmitting} className="portal-btn-gold">
                  {isSubmitting ? "Saving..." : editingHotel ? "Update Property" : "Register Property"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
