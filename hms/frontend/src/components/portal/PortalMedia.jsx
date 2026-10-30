import React, { useState, useEffect } from "react";
import { api } from "../../services/api";

export default function PortalMedia({
  activeHotel,
  roomTypes = [],
  token,
  userRole
}) {
  const [mediaList, setMediaList] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [filterScope, setFilterScope] = useState("all");
  const [showAddModal, setShowAddModal] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const [formData, setFormData] = useState({
    image_url: "",
    is_primary: false,
    room_type_id: ""
  });

  const canEdit = ["admin", "owner", "manager"].includes(userRole);

  const fetchMedia = async () => {
    if (!activeHotel?.id) return;
    setIsLoading(true);
    try {
      const data = await api.getMedia({ hotel_id: activeHotel.id, limit: 100 }, token);
      setMediaList(data || []);
    } catch (err) {
      console.error("Failed to load hotel media", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchMedia();
  }, [activeHotel?.id]);

  const handleAddMedia = async (e) => {
    e.preventDefault();
    if (!formData.image_url.trim()) {
      setError("Please provide a valid image URL.");
      return;
    }

    setIsSubmitting(true);
    setError(null);
    setSuccess(null);

    try {
      const payload = {
        hotel_id: activeHotel.id,
        image_url: formData.image_url.trim(),
        is_primary: formData.is_primary ? "true" : "false"
      };
      if (formData.room_type_id) {
        payload.room_type_id = formData.room_type_id;
      }

      await api.createMedia(payload, token);
      setSuccess("Media asset added successfully!");
      setShowAddModal(false);
      setFormData({ image_url: "", is_primary: false, room_type_id: "" });
      fetchMedia();
    } catch (err) {
      setError(err.message || "Failed to create media item.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSetPrimary = async (item) => {
    try {
      await api.updateMedia(item.id, { is_primary: true }, token);
      setSuccess("Set as primary hero photo!");
      fetchMedia();
    } catch (err) {
      setError(err.message || "Failed to update primary status.");
    }
  };

  const handleDelete = async (item) => {
    if (!window.confirm("Are you sure you want to delete this photo from the gallery?")) {
      return;
    }

    try {
      await api.deleteMedia(item.id, token);
      setSuccess("Media photo deleted.");
      fetchMedia();
    } catch (err) {
      setError(err.message || "Failed to delete media.");
    }
  };

  const filteredMedia = mediaList.filter((m) => {
    if (filterScope === "primary") return m.is_primary;
    if (filterScope === "hotel_general") return !m.room_type_id;
    if (filterScope !== "all") return m.room_type_id === filterScope;
    return true;
  });

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
            🖼️
          </div>
          <div>
            <h1 className="portal-banner-title">Media & Gallery Curation</h1>
            <p className="portal-banner-subtitle">
              Curate high-resolution hero showcases and suite photography for{" "}
              <span style={{ color: "#dfc471", fontWeight: 600 }}>{activeHotel?.name}</span>
            </p>
          </div>
        </div>

        {canEdit && (
          <button
            onClick={() => {
              setFormData({ image_url: "", is_primary: false, room_type_id: "" });
              setError(null);
              setSuccess(null);
              setShowAddModal(true);
            }}
            className="portal-btn-gold"
          >
            <span>+</span>
            <span>Add Photo to Gallery</span>
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

      {/* Filter Tabs */}
      <div className="portal-tabs-bar">
        <button
          onClick={() => setFilterScope("all")}
          className={`portal-tab-pill ${filterScope === "all" ? "active" : ""}`}
        >
          All Photos ({mediaList.length})
        </button>
        <button
          onClick={() => setFilterScope("primary")}
          className={`portal-tab-pill ${filterScope === "primary" ? "active" : ""}`}
        >
          ⭐ Primary Hero Photos ({mediaList.filter((m) => m.is_primary).length})
        </button>
        <button
          onClick={() => setFilterScope("hotel_general")}
          className={`portal-tab-pill ${filterScope === "hotel_general" ? "active" : ""}`}
        >
          🏢 Property-Level
        </button>
        {roomTypes.map((rt) => (
          <button
            key={rt.id}
            onClick={() => setFilterScope(rt.id)}
            className={`portal-tab-pill ${filterScope === rt.id ? "active" : ""}`}
          >
            {rt.name}
          </button>
        ))}
      </div>

      {/* Media Grid */}
      {isLoading ? (
        <div style={{ textAlign: "center", padding: 60, color: "#94a3b8" }}>
          Loading property photography...
        </div>
      ) : filteredMedia.length === 0 ? (
        <div className="portal-empty-state">
          <div className="portal-empty-icon">📸</div>
          <div className="portal-empty-title">No Photos In This Scope</div>
          <p className="portal-empty-desc">
            Upload showcase imagery to present your property and room suites in their finest light.
          </p>
          {canEdit && (
            <button
              onClick={() => setShowAddModal(true)}
              className="portal-btn-gold"
              style={{ marginTop: 16 }}
            >
              + Add First Photo
            </button>
          )}
        </div>
      ) : (
        <div className="portal-grid-4">
          {filteredMedia.map((item) => {
            const rt = roomTypes.find((r) => r.id === item.room_type_id);
            return (
              <div key={item.id} className="portal-media-card">
                <div className="portal-media-thumb">
                  <img
                    src={item.image_url}
                    alt={rt ? rt.name : activeHotel?.name}
                    onError={(e) => {
                      e.target.src =
                        "https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=1200&q=80";
                    }}
                  />

                  {/* Badges */}
                  <div className="portal-media-badges">
                    {item.is_primary && (
                      <span className="portal-badge portal-badge-gold">
                        ⭐ Primary Hero
                      </span>
                    )}
                    <span className="portal-badge portal-badge-gray">
                      {rt ? rt.name : "🏢 Property Wide"}
                    </span>
                  </div>
                </div>

                {/* Footer Controls */}
                <div className="portal-media-footer">
                  <div
                    style={{
                      fontSize: 11,
                      color: "#94a3b8",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                      maxWidth: 130
                    }}
                    title={item.image_url}
                  >
                    {item.image_url}
                  </div>

                  {canEdit && (
                    <div style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
                      {!item.is_primary && (
                        <button
                          onClick={() => handleSetPrimary(item)}
                          className="portal-btn-secondary portal-btn-sm"
                          title="Set as Primary Hero Image"
                        >
                          ★ Make Hero
                        </button>
                      )}
                      <button
                        onClick={() => handleDelete(item)}
                        className="portal-btn-danger"
                        title="Delete photo"
                        style={{ padding: "4px 8px" }}
                      >
                        🗑️
                      </button>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Add Media Modal */}
      {showAddModal && (
        <div className="portal-modal-backdrop" onClick={() => setShowAddModal(false)}>
          <div className="portal-modal-box" onClick={(e) => e.stopPropagation()}>
            <div className="portal-modal-header">
              <div>
                <h3 className="portal-card-title">Add Showcase Photo</h3>
                <p className="portal-card-subtitle">
                  Property: <span style={{ color: "#dfc471" }}>{activeHotel?.name}</span>
                </p>
              </div>
              <button onClick={() => setShowAddModal(false)} className="portal-modal-close">
                ✕
              </button>
            </div>

            <form onSubmit={handleAddMedia} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div className="portal-form-group">
                <label className="portal-label">High-Resolution Image URL *</label>
                <input
                  type="url"
                  required
                  placeholder="https://images.unsplash.com/... or CDN link"
                  value={formData.image_url}
                  onChange={(e) => setFormData({ ...formData, image_url: e.target.value })}
                  className="portal-input"
                  style={{ fontFamily: "monospace" }}
                />
              </div>

              {formData.image_url && (
                <div
                  style={{
                    aspectRatio: "16 / 9",
                    borderRadius: 12,
                    overflow: "hidden",
                    border: "1px solid rgba(255, 255, 255, 0.1)",
                    background: "#060910"
                  }}
                >
                  <img
                    src={formData.image_url}
                    alt="Preview"
                    style={{ width: "100%", height: "100%", objectFit: "cover" }}
                    onError={(e) => {
                      e.target.style.display = "none";
                    }}
                  />
                </div>
              )}

              <div className="portal-form-group">
                <label className="portal-label">Attach to Suite Category (Optional)</label>
                <select
                  value={formData.room_type_id}
                  onChange={(e) => setFormData({ ...formData, room_type_id: e.target.value })}
                  className="portal-select"
                >
                  <option value="">🏢 General Hotel Showcase (Entire Property)</option>
                  {roomTypes.map((rt) => (
                    <option key={rt.id} value={rt.id}>
                      🛌 {rt.name} (${parseFloat(rt.base_price).toLocaleString()}/night)
                    </option>
                  ))}
                </select>
              </div>

              <div style={{ display: "flex", alignItems: "center", gap: 8, paddingTop: 4 }}>
                <input
                  type="checkbox"
                  id="primaryHeroCheck"
                  checked={formData.is_primary}
                  onChange={(e) => setFormData({ ...formData, is_primary: e.target.checked })}
                  style={{ width: 16, height: 16, accentColor: "#dfc471", cursor: "pointer" }}
                />
                <label
                  htmlFor="primaryHeroCheck"
                  style={{ fontSize: 13, color: "#cbd5e1", cursor: "pointer", userSelect: "none" }}
                >
                  Designate as <strong style={{ color: "#dfc471" }}>Primary Hero</strong> photo for property cards
                </label>
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
                  onClick={() => setShowAddModal(false)}
                  className="portal-btn-secondary"
                >
                  Cancel
                </button>
                <button type="submit" disabled={isSubmitting} className="portal-btn-gold">
                  {isSubmitting ? "Adding Photo..." : "Add to Gallery"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
