import React, { useState } from "react";
import { api } from "../../services/api";

const COMMON_POLICY_TYPES = [
  { value: "cancellation", label: "🔄 Cancellation & Refunds", icon: "🔄" },
  { value: "check_in_check_out", label: "⏰ Check-In & Check-Out", icon: "⏰" },
  { value: "pet_policy", label: "🐾 Pet Policy", icon: "🐾" },
  { value: "pool_and_spa", label: "🏊 Pool & Wellness Facilities", icon: "🏊" },
  { value: "quiet_hours", label: "🌙 Quiet Hours & Guest Conduct", icon: "🌙" },
  { value: "parking_valet", label: "🅿️ Valet & Parking Services", icon: "🅿️" },
  { value: "deposit_security", label: "🛡️ Security Deposit & Incidentals", icon: "🛡️" },
  { value: "smoking_policy", label: "🚭 Smoking Restrictions", icon: "🚭" },
  { value: "custom", label: "📜 Custom Operational Policy", icon: "📜" }
];

export default function PortalPolicies({
  activeHotel,
  policies = [],
  token,
  userRole,
  onRefresh,
  onNavigateTab
}) {
  const [showModal, setShowModal] = useState(false);
  const [editingPolicy, setEditingPolicy] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const [filterType, setFilterType] = useState("all");

  const [formData, setFormData] = useState({
    policy_type_select: "cancellation",
    custom_type: "",
    description: ""
  });

  const canEdit = ["admin", "owner", "manager"].includes(userRole);

  const openAdd = () => {
    setFormData({
      policy_type_select: "cancellation",
      custom_type: "",
      description: ""
    });
    setEditingPolicy(null);
    setError(null);
    setSuccess(null);
    setShowModal(true);
  };

  const openEdit = (p) => {
    const isStandard = COMMON_POLICY_TYPES.some((t) => t.value === p.policy_type);
    setFormData({
      policy_type_select: isStandard ? p.policy_type : "custom",
      custom_type: isStandard ? "" : p.policy_type,
      description: p.description || ""
    });
    setEditingPolicy(p);
    setError(null);
    setSuccess(null);
    setShowModal(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const finalType =
      formData.policy_type_select === "custom"
        ? formData.custom_type.trim()
        : formData.policy_type_select;

    if (!finalType) {
      setError("Please specify a policy category/type.");
      return;
    }
    if (!formData.description.trim()) {
      setError("Please write the policy terms & conditions description.");
      return;
    }

    setIsSubmitting(true);
    setError(null);
    setSuccess(null);

    try {
      if (editingPolicy) {
        await api.updatePolicy(
          editingPolicy.id,
          {
            policy_type: finalType,
            description: formData.description.trim()
          },
          token
        );
        setSuccess(`Updated policy "${finalType}" successfully!`);
      } else {
        await api.createPolicy(
          {
            hotel_id: activeHotel.id,
            policy_type: finalType,
            description: formData.description.trim()
          },
          token
        );
        setSuccess(`Created policy "${finalType}" successfully!`);
      }
      setShowModal(false);
      if (onRefresh) onRefresh();
    } catch (err) {
      setError(err.message || "Failed to save operational policy.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (p) => {
    if (!window.confirm(`Are you sure you want to delete policy "${p.policy_type}"?`)) {
      return;
    }

    try {
      await api.deletePolicy(p.id, token);
      setSuccess(`Deleted policy "${p.policy_type}".`);
      if (onRefresh) onRefresh();
    } catch (err) {
      setError(err.message || "Failed to delete policy.");
    }
  };

  const filteredPolicies = policies.filter((p) => {
    if (filterType === "all") return true;
    return p.policy_type?.toLowerCase().includes(filterType.toLowerCase());
  });

  const getPolicyBadge = (type) => {
    const t = (type || "").toLowerCase();
    if (t.includes("cancel")) return { label: "Cancellation & Refund", cls: "portal-badge-gold", icon: "🔄" };
    if (t.includes("check")) return { label: "Check-In / Out", cls: "portal-badge-blue", icon: "⏰" };
    if (t.includes("pet")) return { label: "Pet Policy", cls: "portal-badge-green", icon: "🐾" };
    if (t.includes("pool") || t.includes("spa")) return { label: "Pool & Spa", cls: "portal-badge-green", icon: "🏊" };
    if (t.includes("quiet")) return { label: "Quiet Hours", cls: "portal-badge-purple", icon: "🌙" };
    if (t.includes("park")) return { label: "Parking / Valet", cls: "portal-badge-blue", icon: "🅿️" };
    if (t.includes("smoke")) return { label: "Smoking Rules", cls: "portal-badge-red", icon: "🚭" };
    return { label: type, cls: "portal-badge-gray", icon: "📜" };
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
            📜
          </div>
          <div>
            <h1 className="portal-banner-title">Operational & Cancellation Policies</h1>
            <p className="portal-banner-subtitle">
              Manage live terms, cancellation refund matrices, and guest guidelines for{" "}
              <span style={{ color: "#dfc471", fontWeight: 600 }}>{activeHotel?.name}</span>
            </p>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          {onNavigateTab && (
            <button
              onClick={() => onNavigateTab("knowledge")}
              className="portal-btn-secondary"
            >
              <span>⚡ AI Knowledge Sync</span>
            </button>
          )}

          {canEdit && (
            <button onClick={openAdd} className="portal-btn-gold">
              <span>+</span>
              <span>Add Property Policy</span>
            </button>
          )}
        </div>
      </div>

      {/* AI Vectorization Tip Banner */}
      <div className="portal-alert-tip">
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ fontSize: 20 }}>🤖</span>
          <div>
            <strong style={{ color: "#dfc471" }}>Dynamic AI Concierge Integration: </strong>
            Any policy created or edited here is live in the database and automatically vectorized into semantic chunks via FastEmbed RAG for conversational queries.
          </div>
        </div>
        {onNavigateTab && (
          <button
            onClick={() => onNavigateTab("knowledge")}
            style={{
              color: "#dfc471",
              background: "transparent",
              border: "none",
              textDecoration: "underline",
              fontWeight: 600,
              fontSize: 12,
              cursor: "pointer"
            }}
          >
            Go to AI & RAG Sync →
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
        {[
          { id: "all", label: `All Policies (${policies.length})` },
          { id: "cancellation", label: "Cancellation & Refunds" },
          { id: "check", label: "Check-in / Out" },
          { id: "pet", label: "Pets" },
          { id: "pool", label: "Pool & Spa" }
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setFilterType(tab.id)}
            className={`portal-tab-pill ${filterType === tab.id ? "active" : ""}`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Policies Grid */}
      <div className="portal-grid-2">
        {filteredPolicies.length === 0 ? (
          <div className="portal-empty-state" style={{ gridColumn: "1 / -1" }}>
            <div className="portal-empty-icon">📋</div>
            <div className="portal-empty-title">No Operational Policies Found</div>
            <p className="portal-empty-desc">
              Define cancellation refund schedules, check-in rules, and property regulations for this resort.
            </p>
            {canEdit && (
              <button onClick={openAdd} className="portal-btn-gold" style={{ marginTop: 16 }}>
                + Add First Policy
              </button>
            )}
          </div>
        ) : (
          filteredPolicies.map((p) => {
            const badge = getPolicyBadge(p.policy_type);
            return (
              <div
                key={p.id}
                className="portal-card"
                style={{ display: "flex", flexDirection: "column", justifyContent: "space-between" }}
              >
                <div>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "space-between",
                      gap: 10,
                      marginBottom: 12
                    }}
                  >
                    <span className={`portal-badge ${badge.cls}`}>
                      <span>{badge.icon}</span>
                      <span>{badge.label}</span>
                    </span>
                    <span
                      style={{
                        fontSize: 10,
                        textTransform: "uppercase",
                        letterSpacing: "0.08em",
                        color: "#64748b",
                        fontFamily: "monospace"
                      }}
                    >
                      {p.policy_type}
                    </span>
                  </div>

                  <div
                    style={{
                      fontSize: 13,
                      color: "#cbd5e1",
                      lineHeight: 1.6,
                      whiteSpace: "pre-line",
                      background: "rgba(6, 9, 16, 0.7)",
                      padding: 16,
                      borderRadius: 12,
                      border: "1px solid rgba(255, 255, 255, 0.06)",
                      minHeight: 110
                    }}
                  >
                    {p.description}
                  </div>
                </div>

                {canEdit && (
                  <div
                    style={{
                      paddingTop: 16,
                      marginTop: 16,
                      borderTop: "1px solid rgba(255, 255, 255, 0.08)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "flex-end",
                      gap: 8
                    }}
                  >
                    <button onClick={() => openEdit(p)} className="portal-btn-secondary">
                      ✏️ Edit Policy
                    </button>
                    <button onClick={() => handleDelete(p)} className="portal-btn-danger">
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
      {showModal && (
        <div className="portal-modal-backdrop" onClick={() => setShowModal(false)}>
          <div className="portal-modal-box" onClick={(e) => e.stopPropagation()}>
            <div className="portal-modal-header">
              <div>
                <h3 className="portal-card-title">
                  {editingPolicy ? "Edit Property Policy" : "Add Property Policy"}
                </h3>
                <p className="portal-card-subtitle">
                  Property: <span style={{ color: "#dfc471" }}>{activeHotel?.name}</span>
                </p>
              </div>
              <button onClick={() => setShowModal(false)} className="portal-modal-close">
                ✕
              </button>
            </div>

            <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div className="portal-form-group">
                <label className="portal-label">Policy Category *</label>
                <select
                  value={formData.policy_type_select}
                  onChange={(e) => setFormData({ ...formData, policy_type_select: e.target.value })}
                  className="portal-select"
                >
                  {COMMON_POLICY_TYPES.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </select>
              </div>

              {formData.policy_type_select === "custom" && (
                <div className="portal-form-group">
                  <label className="portal-label">Custom Policy Identifier *</label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. drone_photography, dress_code"
                    value={formData.custom_type}
                    onChange={(e) => setFormData({ ...formData, custom_type: e.target.value })}
                    className="portal-input"
                  />
                </div>
              )}

              <div className="portal-form-group">
                <label className="portal-label">Policy Terms & Rules Description *</label>
                <textarea
                  rows="6"
                  required
                  placeholder="e.g. Free cancellation up to 48 hours prior to 3:00 PM check-in date. Cancellations made within 48 hours are subject to a 1-night room & tax fee..."
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
                  {isSubmitting ? "Saving..." : editingPolicy ? "Update Policy" : "Save Policy"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
