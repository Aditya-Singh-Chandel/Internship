import React, { useState, useEffect } from "react";
import { api } from "../../services/api";

export default function PortalStaff({
  activeHotel,
  hotels = [],
  token,
  userRole,
  currentUserId
}) {
  const [users, setUsers] = useState([]);
  const [roles, setRoles] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [filterRole, setFilterRole] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");

  const [showAddModal, setShowAddModal] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  const [modalError, setModalError] = useState(null);
  const [portfolioModalError, setPortfolioModalError] = useState(null);

  const [formData, setFormData] = useState({
    name: "",
    email: "",
    password: "",
    phone: "",
    role_name: "receptionist",
    hotel_id: activeHotel?.id || "",
    owner_hotel_ids: []
  });

  const [managePortfolioUser, setManagePortfolioUser] = useState(null);
  const [portfolioHotelIds, setPortfolioHotelIds] = useState([]);
  const [isUpdatingPortfolio, setIsUpdatingPortfolio] = useState(false);

  const canHire = ["admin", "owner", "manager"].includes(userRole);

  const fetchData = async () => {
    setIsLoading(true);
    try {
      const [usersData, rolesData] = await Promise.all([
        api.getUsers({ limit: 100 }, token).catch(() => []),
        api.getRoles(token).catch(() => [])
      ]);
      setUsers(usersData || []);
      setRoles(rolesData || []);
    } catch (err) {
      console.error("Failed to load users & roles", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [activeHotel?.id]);

  const openAdd = () => {
    let defaultRole = "receptionist";
    if (userRole === "admin") defaultRole = "manager";
    if (userRole === "owner") defaultRole = "manager";

    setFormData({
      name: "",
      email: "",
      password: "",
      phone: "",
      role_name: defaultRole,
      hotel_id: activeHotel?.id || (hotels[0]?.id || ""),
      owner_hotel_ids: []
    });
    setModalError(null);
    setError(null);
    setSuccess(null);
    setShowAddModal(true);
  };

  const handleCreateUser = async (e) => {
    e.preventDefault();
    if (!formData.name || !formData.email || !formData.password) {
      setModalError("Please provide Name, Email, and Password.");
      return;
    }
    if (formData.password.length < 6) {
      setModalError("Password must be at least 6 characters long.");
      return;
    }

    setIsSubmitting(true);
    setModalError(null);
    setError(null);
    setSuccess(null);

    try {
      const payload = {
        name: formData.name.trim(),
        email: formData.email.trim(),
        password: formData.password,
        phone: formData.phone.trim() || undefined,
        role_name: formData.role_name
      };

      if (formData.role_name === "owner") {
        if (formData.owner_hotel_ids && formData.owner_hotel_ids.length > 0) {
          payload.hotel_ids = formData.owner_hotel_ids.join(",");
        }
      } else if (formData.hotel_id && formData.role_name !== "admin") {
        payload.hotel_id = formData.hotel_id;
      }

      await api.createUser(payload, token);
      setSuccess(`Created ${formData.role_name} account for "${formData.name}" successfully!`);
      setShowAddModal(false);
      fetchData();
    } catch (err) {
      setModalError(err.message || "Failed to create user.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const openManagePortfolio = (u) => {
    setManagePortfolioUser(u);
    const currentOwned = (u.owned_hotel_ids && u.owned_hotel_ids.length > 0)
      ? u.owned_hotel_ids
      : hotels.filter((h) => h.owner_id === u.id).map((h) => h.id);
    setPortfolioHotelIds(currentOwned || []);
    setPortfolioModalError(null);
    setError(null);
    setSuccess(null);
  };

  const handleSavePortfolio = async (e) => {
    e.preventDefault();
    if (!managePortfolioUser) return;

    setIsUpdatingPortfolio(true);
    setPortfolioModalError(null);
    setError(null);
    setSuccess(null);

    try {
      await api.updateUser(
        managePortfolioUser.id,
        { hotel_ids: portfolioHotelIds.join(",") },
        token
      );
      setSuccess(`Updated luxury property portfolio for "${managePortfolioUser.name}" (${portfolioHotelIds.length} properties assigned).`);
      setManagePortfolioUser(null);
      fetchData();
    } catch (err) {
      setPortfolioModalError(err.message || "Failed to update property portfolio.");
    } finally {
      setIsUpdatingPortfolio(false);
    }
  };

  const [userToRevoke, setUserToRevoke] = useState(null);
  const [isRevoking, setIsRevoking] = useState(false);

  const handleDeleteUser = (u) => {
    if (u.id === currentUserId) {
      setError("You cannot revoke your own active account.");
      return;
    }
    setUserToRevoke(u);
  };

  const confirmRevokeUser = async () => {
    if (!userToRevoke) return;
    setIsRevoking(true);
    setError(null);
    setSuccess(null);

    try {
      await api.deleteUser(userToRevoke.id, token);
      setSuccess(`Revoked access for user "${userToRevoke.name}" (${userToRevoke.email}) successfully.`);
      setUserToRevoke(null);
      fetchData();
    } catch (err) {
      setError(err.message || "Failed to revoke user access.");
      setUserToRevoke(null);
    } finally {
      setIsRevoking(false);
    }
  };

  const ROLE_HIERARCHY_LEVELS = {
    admin: 4,
    owner: 3,
    manager: 2,
    receptionist: 1,
    customer: 0
  };
  const myLevel = ROLE_HIERARCHY_LEVELS[userRole] || 0;

  const getAllowedRoles = () => {
    if (userRole === "admin") {
      return [
        { value: "owner", label: "🏢 Property Owner" },
        { value: "manager", label: "👔 General Manager" },
        { value: "receptionist", label: "🛎️ Receptionist / Front Desk" }
      ];
    }
    if (userRole === "owner") {
      return [
        { value: "manager", label: "👔 General Manager" },
        { value: "receptionist", label: "🛎️ Receptionist / Front Desk" }
      ];
    }
    if (userRole === "manager") {
      return [
        { value: "receptionist", label: "🛎️ Receptionist / Front Desk" }
      ];
    }
    return [];
  };

  // Strict Hierarchy: Users can only see team members strictly below their own authority level!
  // - Admin (4) cannot see another Admin (4), but sees Owner (3), Manager (2), Receptionist (1).
  // - Owner (3) cannot see Admin (4) or Owner (3), but sees Manager (2), Receptionist (1).
  // - Manager (2) cannot see Admin (4), Owner (3), or Manager (2), but sees Receptionist (1).
  const visibleUsers = users.filter((u) => {
    const roleName = u.role?.name?.toLowerCase() || "";
    const targetLevel = ROLE_HIERARCHY_LEVELS[roleName] || 0;
    return targetLevel < myLevel;
  });

  const filteredUsers = visibleUsers.filter((u) => {
    const roleName = u.role?.name?.toLowerCase() || "";
    if (filterRole !== "all" && roleName !== filterRole) return false;
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchName = u.name?.toLowerCase().includes(q);
      const matchEmail = u.email?.toLowerCase().includes(q);
      if (!matchName && !matchEmail) return false;
    }
    return true;
  });

  const getRoleBadge = (roleName) => {
    const r = (roleName || "").toLowerCase();
    if (r === "admin") return { label: "System Admin", cls: "portal-badge-purple", icon: "👑" };
    if (r === "owner") return { label: "Property Owner", cls: "portal-badge-gold", icon: "🏢" };
    if (r === "manager") return { label: "General Manager", cls: "portal-badge-blue", icon: "👔" };
    if (r === "receptionist") return { label: "Front Desk Staff", cls: "portal-badge-green", icon: "🛎️" };
    return { label: "Guest / Traveler", cls: "portal-badge-gray", icon: "👤" };
  };

  const getTabs = () => {
    if (userRole === "admin") {
      return [
        { id: "all", label: `All Members (${visibleUsers.length})` },
        { id: "owner", label: "Owners" },
        { id: "manager", label: "Managers" },
        { id: "receptionist", label: "Front Desk" }
      ];
    }
    if (userRole === "owner") {
      return [
        { id: "all", label: `All Staff (${visibleUsers.length})` },
        { id: "manager", label: "Managers" },
        { id: "receptionist", label: "Front Desk" }
      ];
    }
    if (userRole === "manager") {
      return [
        { id: "all", label: `Front Desk Staff (${visibleUsers.length})` },
        { id: "receptionist", label: "Front Desk" }
      ];
    }
    return [{ id: "all", label: "All Members" }];
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
              background: "rgba(14, 165, 233, 0.15)",
              border: "1px solid rgba(14, 165, 233, 0.3)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 22
            }}
          >
            👥
          </div>
          <div>
            <h1 className="portal-banner-title">Staff Roster & Access Control</h1>
            <p className="portal-banner-subtitle">
              Role-based access management, staff onboarding, and hotel assignments
            </p>
          </div>
        </div>

        {canHire && (
          <button onClick={openAdd} className="portal-btn-gold">
            <span>+</span>
            <span>Onboard New Staff Member</span>
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

      {/* Search and Filters */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 12,
          alignItems: "center",
          justifyContent: "space-between"
        }}
      >
        <div style={{ position: "relative", minWidth: 280, flex: 1, maxWidth: 420 }}>
          <input
            type="text"
            placeholder="Search team member by name or email..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="portal-input"
            style={{ paddingLeft: 34, fontSize: 12 }}
          />
          <span style={{ position: "absolute", left: 12, top: "50%", transform: "translateY(-50%)", color: "#64748b", fontSize: 13 }}>
            🔍
          </span>
        </div>

        <div className="portal-tabs-bar">
          {getTabs().map((tab) => (
            <button
              key={tab.id}
              onClick={() => setFilterRole(tab.id)}
              className={`portal-tab-pill ${filterRole === tab.id ? "active" : ""}`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Team Roster Table */}
      <div className="portal-card" style={{ padding: 0, overflow: "hidden" }}>
        <div className="portal-table-wrap" style={{ border: "none", borderRadius: 0 }}>
          <table className="portal-table">
            <thead>
              <tr>
                <th>Team Member</th>
                <th>Role Permission</th>
                <th>Assigned Property</th>
                <th>Contact Phone</th>
                <th>Joined</th>
                {canHire && <th style={{ textAlign: "right" }}>Actions</th>}
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={6} style={{ textAlign: "center", padding: 48, color: "#94a3b8" }}>
                    Loading team members...
                  </td>
                </tr>
              ) : filteredUsers.length === 0 ? (
                <tr>
                  <td colSpan={6} style={{ textAlign: "center", padding: 48, color: "#94a3b8" }}>
                    <div style={{ fontSize: 32, marginBottom: 8 }}>👥</div>
                    <div style={{ color: "#e2e8f0", fontWeight: 600 }}>No team members found matching your filter criteria.</div>
                  </td>
                </tr>
              ) : (
                filteredUsers.map((u) => {
                  const roleName = u.role?.name?.toLowerCase() || "";
                  const badge = getRoleBadge(roleName);
                  const assignedHotel = hotels.find((h) => h.id === u.hotel_id);
                  const isSelf = u.id === currentUserId;

                  return (
                    <tr key={u.id}>
                      <td>
                        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                          <div
                            style={{
                              width: 34,
                              height: 34,
                              borderRadius: "50%",
                              background: "rgba(197, 155, 39, 0.15)",
                              border: "1px solid rgba(197, 155, 39, 0.3)",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              fontWeight: 700,
                              color: "#dfc471",
                              fontSize: 13
                            }}
                          >
                            {u.name ? u.name.charAt(0).toUpperCase() : "U"}
                          </div>
                          <div>
                            <div style={{ display: "flex", alignItems: "center", gap: 6, fontWeight: 600, color: "#ffffff" }}>
                              <span>{u.name}</span>
                              {isSelf && (
                                <span className="portal-badge portal-badge-gold" style={{ padding: "2px 6px", fontSize: 9 }}>
                                  YOU
                                </span>
                              )}
                            </div>
                            <div style={{ fontSize: 11, color: "#94a3b8", fontFamily: "monospace" }}>{u.email}</div>
                          </div>
                        </div>
                      </td>
                      <td>
                        <span className={`portal-badge ${badge.cls}`}>
                          <span>{badge.icon}</span>
                          <span>{badge.label}</span>
                        </span>
                      </td>
                      <td style={{ color: "#cbd5e1" }}>
                        {roleName === "owner" ? (
                          u.assigned_property_name && u.assigned_property_name !== "Unassigned Portfolio" ? (
                            <div style={{ display: "flex", flexWrap: "wrap", gap: 5 }}>
                              {u.assigned_property_name.split(", ").map((propName, idx) => (
                                <span
                                  key={idx}
                                  className="portal-badge portal-badge-gold"
                                  style={{ fontSize: 10, padding: "2px 8px", whiteSpace: "nowrap" }}
                                >
                                  🏢 {propName}
                                </span>
                              ))}
                            </div>
                          ) : (
                            <span style={{ color: "#64748b", fontStyle: "italic" }}>
                              Unassigned Portfolio (0 properties)
                            </span>
                          )
                        ) : u.assigned_property_name ? (
                          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                            <span>🏨</span>
                            <span>{u.assigned_property_name}</span>
                          </div>
                        ) : assignedHotel ? (
                          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                            <span>🏨</span>
                            <span>{assignedHotel.name}</span>
                          </div>
                        ) : roleName === "admin" ? (
                          <span style={{ color: "#c084fc", fontWeight: 600 }}>Global Portfolio</span>
                        ) : (
                          <span style={{ color: "#64748b", fontStyle: "italic" }}>Unassigned</span>
                        )}
                      </td>
                      <td style={{ fontFamily: "monospace", color: "#94a3b8" }}>
                        {u.phone || "—"}
                      </td>
                      <td style={{ color: "#94a3b8" }}>
                        {u.created_at ? new Date(u.created_at).toLocaleDateString() : "Active"}
                      </td>
                      {canHire && (
                        <td style={{ textAlign: "right" }}>
                          <div style={{ display: "flex", alignItems: "center", justifyContent: "flex-end", gap: 8 }}>
                            {userRole === "admin" && roleName === "owner" && !isSelf && (
                              <button
                                onClick={() => openManagePortfolio(u)}
                                className="portal-btn-secondary"
                                style={{
                                  padding: "5px 10px",
                                  fontSize: 11,
                                  borderColor: "rgba(197, 155, 39, 0.4)",
                                  color: "#dfc471",
                                  whiteSpace: "nowrap"
                                }}
                              >
                                🏢 Portfolio
                              </button>
                            )}
                            {!isSelf && (
                              <button
                                onClick={() => handleDeleteUser(u)}
                                className="portal-btn-danger"
                                style={{ padding: "5px 10px", fontSize: 11 }}
                              >
                                Revoke
                              </button>
                            )}
                          </div>
                        </td>
                      )}
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Add Staff Modal */}
      {showAddModal && (
        <div className="portal-modal-backdrop" onClick={() => setShowAddModal(false)}>
          <div className="portal-modal-box" onClick={(e) => e.stopPropagation()}>
            <div className="portal-modal-header">
              <div>
                <h3 className="portal-card-title">Onboard Staff Member</h3>
                <p className="portal-card-subtitle">
                  Authorize operations portal access with defined role permissions
                </p>
              </div>
              <button onClick={() => setShowAddModal(false)} className="portal-modal-close">
                ✕
              </button>
            </div>

            {modalError && (
              <div className="portal-alert-error" style={{ marginBottom: 14 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <strong>⚠️ Error:</strong>
                  <span>{modalError}</span>
                </div>
                <button
                  type="button"
                  onClick={() => setModalError(null)}
                  style={{ background: "none", border: "none", color: "#fca5a5", cursor: "pointer", fontSize: 16 }}
                >
                  ✕
                </button>
              </div>
            )}

            <form onSubmit={handleCreateUser} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div className="portal-form-group">
                <label className="portal-label">Full Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Eleanor Vance"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  className="portal-input"
                />
              </div>

              <div className="portal-form-row-2">
                <div className="portal-form-group">
                  <label className="portal-label">Email Address *</label>
                  <input
                    type="email"
                    required
                    placeholder="e.g. eleanor@grandstay.com"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    className="portal-input"
                    style={{ fontFamily: "monospace" }}
                  />
                </div>
                <div className="portal-form-group">
                  <label className="portal-label">Initial Password *</label>
                  <input
                    type="password"
                    required
                    placeholder="Min 6 characters"
                    value={formData.password}
                    onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                    className="portal-input"
                  />
                </div>
              </div>

              <div className="portal-form-group">
                <label className="portal-label">Role & Authority *</label>
                <select
                  value={formData.role_name}
                  onChange={(e) => setFormData({ ...formData, role_name: e.target.value })}
                  className="portal-select"
                >
                  {getAllowedRoles().map((r) => (
                    <option key={r.value} value={r.value}>
                      {r.label}
                    </option>
                  ))}
                </select>
              </div>

              {formData.role_name === "owner" ? (
                <div className="portal-form-group">
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                    <label className="portal-label" style={{ marginBottom: 0 }}>
                      Assign Properties to Owner Portfolio (Multi-Property)
                    </label>
                    <span style={{ fontSize: 11, color: "#dfc471", fontWeight: 600 }}>
                      {formData.owner_hotel_ids.length} Properties Selected
                    </span>
                  </div>
                  <div
                    style={{
                      maxHeight: 180,
                      overflowY: "auto",
                      background: "rgba(15, 23, 42, 0.6)",
                      border: "1px solid rgba(255, 255, 255, 0.1)",
                      borderRadius: 8,
                      padding: "8px 10px",
                      display: "flex",
                      flexDirection: "column",
                      gap: 6
                    }}
                  >
                    {hotels.map((h) => {
                      const isAlreadyOwned = Boolean(h.owner_id);
                      const isSelected = formData.owner_hotel_ids.includes(h.id);
                      const otherOwner = isAlreadyOwned ? users.find((u) => u.id === h.owner_id) : null;

                      return (
                        <label
                          key={h.id}
                          style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            padding: "6px 8px",
                            borderRadius: 6,
                            background: isSelected ? "rgba(197, 155, 39, 0.12)" : "rgba(255, 255, 255, 0.02)",
                            cursor: isAlreadyOwned ? "not-allowed" : "pointer",
                            opacity: isAlreadyOwned ? 0.6 : 1
                          }}
                        >
                          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                            <input
                              type="checkbox"
                              disabled={isAlreadyOwned}
                              checked={isSelected}
                              onChange={(e) => {
                                if (e.target.checked) {
                                  setFormData({
                                    ...formData,
                                    owner_hotel_ids: [...formData.owner_hotel_ids, h.id]
                                  });
                                } else {
                                  setFormData({
                                    ...formData,
                                    owner_hotel_ids: formData.owner_hotel_ids.filter((id) => id !== h.id)
                                  });
                                }
                              }}
                              style={{ cursor: isAlreadyOwned ? "not-allowed" : "pointer", accentColor: "#c59b27" }}
                            />
                            <span style={{ fontSize: 13, color: isSelected ? "#dfc471" : "#ffffff", fontWeight: isSelected ? 600 : 400 }}>
                              🏨 {h.name} <span style={{ fontSize: 11, color: "#94a3b8" }}>({h.city})</span>
                            </span>
                          </div>
                          {isAlreadyOwned ? (
                            <span className="portal-badge portal-badge-gray" style={{ fontSize: 10, padding: "2px 6px" }}>
                              🔒 Owned by {otherOwner ? otherOwner.name : "Other Owner"}
                            </span>
                          ) : isSelected ? (
                            <span className="portal-badge portal-badge-gold" style={{ fontSize: 10, padding: "2px 6px" }}>
                              ✓ In Portfolio
                            </span>
                          ) : (
                            <span style={{ fontSize: 10, color: "#64748b" }}>Available</span>
                          )}
                        </label>
                      );
                    })}
                  </div>
                  <div style={{ fontSize: "11px", color: "#dfc471", marginTop: "6px", display: "flex", alignItems: "center", gap: 6 }}>
                    <span>✦</span>
                    <span>One owner can manage multiple luxury properties, but each hotel strictly supports only a single owner.</span>
                  </div>
                </div>
              ) : (
                <div className="portal-form-group">
                  <label className="portal-label">Assigned Workplace Property *</label>
                  <select
                    value={formData.hotel_id}
                    onChange={(e) => setFormData({ ...formData, hotel_id: e.target.value })}
                    disabled={userRole === "manager"}
                    className="portal-select"
                  >
                    {hotels.map((h) => (
                      <option key={h.id} value={h.id}>
                        {h.name} ({h.city})
                      </option>
                    ))}
                  </select>
                </div>
              )}

              <div className="portal-form-group">
                <label className="portal-label">Contact Phone (Optional)</label>
                <input
                  type="tel"
                  placeholder="+1 (555) 000-0000"
                  value={formData.phone}
                  onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                  className="portal-input"
                  style={{ fontFamily: "monospace" }}
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
                  onClick={() => setShowAddModal(false)}
                  className="portal-btn-secondary"
                >
                  Cancel
                </button>
                <button type="submit" disabled={isSubmitting} className="portal-btn-gold">
                  {isSubmitting ? "Onboarding..." : "Authorize Account"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Manage Property Portfolio Modal (for Existing Owners) */}
      {managePortfolioUser && (
        <div className="portal-modal-backdrop" onClick={() => setManagePortfolioUser(null)}>
          <div className="portal-modal-box" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 540 }}>
            <div className="portal-modal-header">
              <div>
                <h3 className="portal-card-title">Manage Property Portfolio</h3>
                <p className="portal-card-subtitle">
                  Assign luxury properties for <strong>{managePortfolioUser.name}</strong> ({managePortfolioUser.email})
                </p>
              </div>
              <button onClick={() => setManagePortfolioUser(null)} className="portal-modal-close">
                ✕
              </button>
            </div>

            {portfolioModalError && (
              <div className="portal-alert-error" style={{ marginBottom: 14 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <strong>⚠️ Error:</strong>
                  <span>{portfolioModalError}</span>
                </div>
                <button
                  type="button"
                  onClick={() => setPortfolioModalError(null)}
                  style={{ background: "none", border: "none", color: "#fca5a5", cursor: "pointer", fontSize: 16 }}
                >
                  ✕
                </button>
              </div>
            )}

            <form onSubmit={handleSavePortfolio} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span style={{ fontSize: 12, color: "#94a3b8" }}>
                  Select one or more luxury properties for this owner's portfolio:
                </span>
                <span className="portal-badge portal-badge-gold" style={{ fontSize: 11 }}>
                  {portfolioHotelIds.length} Assigned
                </span>
              </div>

              <div
                style={{
                  maxHeight: 280,
                  overflowY: "auto",
                  background: "rgba(15, 23, 42, 0.6)",
                  border: "1px solid rgba(255, 255, 255, 0.1)",
                  borderRadius: 10,
                  padding: "10px 12px",
                  display: "flex",
                  flexDirection: "column",
                  gap: 8
                }}
              >
                {hotels.map((h) => {
                  const isOwnedByThisOwner = portfolioHotelIds.includes(h.id);
                  const isOwnedByOther = Boolean(h.owner_id && h.owner_id !== managePortfolioUser.id && !isOwnedByThisOwner);
                  const otherOwner = isOwnedByOther ? users.find((u) => u.id === h.owner_id) : null;

                  return (
                    <label
                      key={h.id}
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        padding: "8px 10px",
                        borderRadius: 8,
                        background: isOwnedByThisOwner ? "rgba(197, 155, 39, 0.15)" : "rgba(255, 255, 255, 0.02)",
                        border: isOwnedByThisOwner ? "1px solid rgba(197, 155, 39, 0.3)" : "1px solid transparent",
                        cursor: isOwnedByOther ? "not-allowed" : "pointer",
                        opacity: isOwnedByOther ? 0.55 : 1
                      }}
                    >
                      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                        <input
                          type="checkbox"
                          disabled={isOwnedByOther}
                          checked={isOwnedByThisOwner}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setPortfolioHotelIds([...portfolioHotelIds, h.id]);
                            } else {
                              setPortfolioHotelIds(portfolioHotelIds.filter((id) => id !== h.id));
                            }
                          }}
                          style={{ cursor: isOwnedByOther ? "not-allowed" : "pointer", accentColor: "#c59b27" }}
                        />
                        <div>
                          <div style={{ fontSize: 13, color: isOwnedByThisOwner ? "#dfc471" : "#ffffff", fontWeight: isOwnedByThisOwner ? 600 : 400 }}>
                            🏨 {h.name}
                          </div>
                          <div style={{ fontSize: 11, color: "#94a3b8" }}>{h.city} • {h.address}</div>
                        </div>
                      </div>

                      {isOwnedByOther ? (
                        <span className="portal-badge portal-badge-gray" style={{ fontSize: 10, padding: "2px 8px" }}>
                          🔒 Owned by {otherOwner ? otherOwner.name : "Other"}
                        </span>
                      ) : isOwnedByThisOwner ? (
                        <span className="portal-badge portal-badge-gold" style={{ fontSize: 10, padding: "2px 8px" }}>
                          ✓ In Portfolio
                        </span>
                      ) : (
                        <span style={{ fontSize: 10, color: "#64748b" }}>Available</span>
                      )}
                    </label>
                  );
                })}
              </div>

              <div
                style={{
                  background: "rgba(197, 155, 39, 0.08)",
                  border: "1px solid rgba(197, 155, 39, 0.2)",
                  padding: "10px 14px",
                  borderRadius: 8,
                  fontSize: 11,
                  color: "#dfc471",
                  display: "flex",
                  alignItems: "center",
                  gap: 8
                }}
              >
                <span>ℹ</span>
                <span>
                  <strong>Multi-Property Rule:</strong> An Owner can have multiple hotels (1 Owner → Many Hotels). However, a hotel cannot have multiple owners.
                </span>
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
                  onClick={() => setManagePortfolioUser(null)}
                  className="portal-btn-secondary"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isUpdatingPortfolio}
                  className="portal-btn-gold"
                >
                  {isUpdatingPortfolio ? "Updating Portfolio..." : "Save Portfolio Changes"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Revoke Access Confirmation Modal */}
      {userToRevoke && (
        <div className="portal-modal-backdrop" onClick={() => setUserToRevoke(null)}>
          <div className="portal-modal-box" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 440 }}>
            <div className="portal-modal-header">
              <div>
                <h3 className="portal-card-title" style={{ color: "#f87171" }}>Revoke Team Access</h3>
                <p className="portal-card-subtitle">
                  Immediate termination of operations portal access
                </p>
              </div>
              <button onClick={() => setUserToRevoke(null)} className="portal-modal-close">✕</button>
            </div>

            <div style={{ padding: "14px 0 22px" }}>
              <p style={{ color: "#e2e8f0", fontSize: 13, lineHeight: 1.6 }}>
                Are you sure you want to revoke operations access for <strong>{userToRevoke.name}</strong> ({userToRevoke.email})?
              </p>
              <p style={{ color: "#94a3b8", fontSize: 12, marginTop: 8 }}>
                This user will be removed from your staff roster and all active sessions will be terminated immediately.
              </p>
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: 12, borderTop: "1px solid rgba(255,255,255,0.08)", paddingTop: 16 }}>
              <button type="button" onClick={() => setUserToRevoke(null)} className="portal-btn-secondary">
                Cancel
              </button>
              <button
                type="button"
                disabled={isRevoking}
                onClick={confirmRevokeUser}
                className="portal-btn-danger"
                style={{ background: "#dc2626", borderColor: "#ef4444", padding: "8px 16px" }}
              >
                {isRevoking ? "Revoking..." : "Confirm Revoke"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
