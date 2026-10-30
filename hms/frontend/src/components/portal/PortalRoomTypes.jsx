import React, { useState } from "react";
import { api } from "../../services/api";

export default function PortalRoomTypes({
  activeHotel,
  roomTypes = [],
  rooms = [],
  token,
  userRole,
  onRefresh
}) {
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingRoomType, setEditingRoomType] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const [formData, setFormData] = useState({
    name: "",
    base_price: "",
    guests_allowed: "2",
    description: ""
  });

  const canEdit = ["admin", "owner", "manager"].includes(userRole);

  const openAdd = () => {
    setFormData({
      name: "",
      base_price: "",
      guests_allowed: "2",
      description: ""
    });
    setEditingRoomType(null);
    setError(null);
    setSuccess(null);
    setShowAddModal(true);
  };

  const openEdit = (rt) => {
    setFormData({
      name: rt.name,
      base_price: rt.base_price,
      guests_allowed: rt.guests_allowed || "2",
      description: rt.description || ""
    });
    setEditingRoomType(rt);
    setError(null);
    setSuccess(null);
    setShowAddModal(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!formData.name || !formData.base_price) {
      setError("Please provide suite name and base nightly rate.");
      return;
    }
    setIsSubmitting(true);
    setError(null);
    setSuccess(null);

    try {
      if (editingRoomType) {
        await api.updateRoomType(
          editingRoomType.id,
          {
            name: formData.name,
            base_price: parseFloat(formData.base_price),
            guests_allowed: parseInt(formData.guests_allowed, 10),
            description: formData.description
          },
          token
        );
        setSuccess(`Updated suite category "${formData.name}" successfully!`);
      } else {
        await api.createRoomType(
          {
            hotel_id: activeHotel.id,
            name: formData.name,
            base_price: parseFloat(formData.base_price),
            guests_allowed: parseInt(formData.guests_allowed, 10),
            description: formData.description
          },
          token
        );
        setSuccess(`Created suite category "${formData.name}" successfully!`);
      }
      setShowAddModal(false);
      if (onRefresh) onRefresh();
    } catch (err) {
      setError(err.message || "Failed to save room type.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (rt) => {
    const physicalCount = rooms.filter((r) => r.room_type_id === rt.id).length;
    if (physicalCount > 0) {
      if (
        !window.confirm(
          `Warning: ${physicalCount} physical room(s) are currently configured under "${rt.name}". Deleting this room type may cause inconsistencies. Are you sure you wish to proceed?`
        )
      ) {
        return;
      }
    } else {
      if (!window.confirm(`Are you sure you want to delete suite type "${rt.name}"?`)) {
        return;
      }
    }

    try {
      await api.deleteRoomType(rt.id, token);
      setSuccess(`Deleted suite category "${rt.name}".`);
      if (onRefresh) onRefresh();
    } catch (err) {
      setError(err.message || "Failed to delete room type.");
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '22px' }}>
      {/* Top Banner */}
      <div className="portal-banner">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#dfc471', display: 'inline-block' }} />
            <span style={{ fontSize: '11px', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#dfc471' }}>
              Suite Rates & Inventory
            </span>
          </div>
          <h1 className="portal-banner-title">
            Suite Categories & Rates
          </h1>
          <p className="portal-banner-subtitle">
            Configure room categories, nightly rates, capacity limits, and descriptions for <span style={{ color: '#dfc471' }}>{activeHotel?.name}</span>
          </p>
        </div>

        {canEdit && (
          <button onClick={openAdd} className="portal-btn-gold">
            <span>+</span>
            <span>Add Suite Category</span>
          </button>
        )}
      </div>

      {/* Notifications */}
      {error && (
        <div style={{ padding: '14px 18px', borderRadius: '12px', background: 'rgba(239, 68, 68, 0.12)', border: '1px solid rgba(239, 68, 68, 0.25)', color: '#f87171', fontSize: '13px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>⚠️ {error}</span>
          <button onClick={() => setError(null)} style={{ background: 'none', border: 'none', color: '#f87171', cursor: 'pointer', fontSize: '14px' }}>✕</button>
        </div>
      )}
      {success && (
        <div style={{ padding: '14px 18px', borderRadius: '12px', background: 'rgba(16, 185, 129, 0.12)', border: '1px solid rgba(16, 185, 129, 0.25)', color: '#34d399', fontSize: '13px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>✓ {success}</span>
          <button onClick={() => setSuccess(null)} style={{ background: 'none', border: 'none', color: '#34d399', cursor: 'pointer', fontSize: '14px' }}>✕</button>
        </div>
      )}

      {/* Room Types Grid */}
      <div className="portal-grid-3">
        {roomTypes.length === 0 ? (
          <div className="portal-card" style={{ gridColumn: '1 / -1', textAlign: 'center', padding: '60px 20px' }}>
            <div style={{ fontSize: '3rem', marginBottom: '12px' }}>🛌</div>
            <h3 className="portal-card-title">No Suite Categories Configured</h3>
            <p style={{ fontSize: '13px', color: '#64748b', marginTop: '6px' }}>
              Create suite categories with pricing to enable physical room allocation and guest bookings.
            </p>
            {canEdit && (
              <button onClick={openAdd} className="portal-btn-sm portal-btn-secondary" style={{ color: '#dfc471', marginTop: '16px' }}>
                + Create First Category
              </button>
            )}
          </div>
        ) : (
          roomTypes.map((rt) => {
            const count = rooms.filter((r) => r.room_type_id === rt.id).length;
            const availableCount = rooms.filter(
              (r) => r.room_type_id === rt.id && r.status === "available"
            ).length;

            return (
              <div key={rt.id} className="portal-card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '14px' }}>
                    <div>
                      <h3 className="portal-card-title" style={{ fontSize: '1.2rem' }}>
                        {rt.name}
                      </h3>
                      <div style={{ display: 'flex', gap: '6px', marginTop: '6px' }}>
                        <span className="portal-badge portal-badge-gray">
                          Max {rt.guests_allowed || 2} Guests
                        </span>
                        <span className="portal-badge portal-badge-gold">
                          {count} Rooms Built
                        </span>
                      </div>
                    </div>
                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontFamily: 'monospace', fontWeight: 700, fontSize: '1.4rem', color: '#ffffff' }}>
                        ${parseFloat(rt.base_price).toLocaleString()}
                      </div>
                      <div style={{ fontSize: '10px', color: '#64748b', textTransform: 'uppercase' }}>per night</div>
                    </div>
                  </div>

                  <p style={{ fontSize: '12px', color: '#94a3b8', lineHeight: 1.5, marginBottom: '16px', minHeight: '36px' }}>
                    {rt.description || "Luxury accommodations with bespoke amenities and signature guest services."}
                  </p>

                  <div style={{ display: 'flex', justifyContent: 'space-between', padding: '10px 12px', borderRadius: '10px', background: 'rgba(7, 10, 18, 0.6)', border: '1px solid rgba(255, 255, 255, 0.05)', fontSize: '12px', marginBottom: '16px' }}>
                    <span style={{ color: '#64748b' }}>Inventory:</span>
                    <span style={{ color: availableCount > 0 ? '#34d399' : '#dfc471', fontWeight: 600 }}>
                      {availableCount} Clean / {count} Total
                    </span>
                  </div>
                </div>

                {canEdit && (
                  <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', paddingTop: '14px', borderTop: '1px solid rgba(255, 255, 255, 0.08)' }}>
                    <button onClick={() => openEdit(rt)} className="portal-btn-sm portal-btn-secondary">
                      ✏️ Edit Rate
                    </button>
                    <button onClick={() => handleDelete(rt)} className="portal-btn-sm portal-btn-danger">
                      Delete
                    </button>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Add / Edit Modal */}
      {showAddModal && (
        <div className="portal-modal-backdrop">
          <div className="portal-modal-box">
            <div className="portal-modal-header">
              <div>
                <h3 className="portal-card-title" style={{ fontSize: '1.25rem' }}>
                  {editingRoomType ? "Edit Suite Category" : "Create New Suite Category"}
                </h3>
                <p className="portal-card-subtitle">
                  Property: <span style={{ color: '#dfc471' }}>{activeHotel?.name}</span>
                </p>
              </div>
              <button onClick={() => setShowAddModal(false)} className="portal-modal-close">
                ✕
              </button>
            </div>

            <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div className="portal-form-group">
                <label className="portal-label">Suite Category Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Royal Penthouse Suite, Deluxe Ocean Villa"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="portal-input"
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div className="portal-form-group">
                  <label className="portal-label">Base Nightly Rate ($ USD) *</label>
                  <input
                    type="number"
                    step="0.01"
                    min="1"
                    required
                    placeholder="e.g. 450.00"
                    value={formData.base_price}
                    onChange={(e) => setFormData({ ...formData, base_price: e.target.value })}
                    className="portal-input"
                    style={{ fontFamily: 'monospace' }}
                  />
                </div>
                <div className="portal-form-group">
                  <label className="portal-label">Guest Capacity</label>
                  <select
                    value={formData.guests_allowed}
                    onChange={(e) => setFormData({ ...formData, guests_allowed: e.target.value })}
                    className="portal-select"
                  >
                    <option value="1">1 Guest</option>
                    <option value="2">2 Guests</option>
                    <option value="3">3 Guests</option>
                    <option value="4">4 Guests</option>
                    <option value="5">5 Guests</option>
                    <option value="6">6+ Guests (Family / Villa)</option>
                  </select>
                </div>
              </div>

              <div className="portal-form-group">
                <label className="portal-label">Description & Features</label>
                <textarea
                  rows="3"
                  placeholder="Describe the layout, bed type, scenic view, and signature perks..."
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  className="portal-textarea"
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', paddingTop: '16px', borderTop: '1px solid rgba(255, 255, 255, 0.08)' }}>
                <button type="button" onClick={() => setShowAddModal(false)} className="portal-btn-secondary">
                  Cancel
                </button>
                <button type="submit" disabled={isSubmitting} className="portal-btn-gold">
                  {isSubmitting ? "Saving..." : editingRoomType ? "Update Suite" : "Create Suite"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
