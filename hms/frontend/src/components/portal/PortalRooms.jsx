import React, { useState } from 'react';
import { api } from '../../services/api';
import { useAuth } from '../../context/AuthContext';

export default function PortalRooms({ 
  hotel, 
  rooms = [], 
  roomTypes = [], 
  onRefreshData, 
  addToast 
}) {
  const { token, user } = useAuth();
  const rawRole = (typeof user?.role === 'object' ? user?.role?.name : user?.role) || '';
  const role = rawRole.toLowerCase();
  const canManage = role !== 'receptionist'; // manager, owner, admin can create/delete rooms

  const [addModalOpen, setAddModalOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [updatingRoomId, setUpdatingRoomId] = useState(null);

  // New Room Form State
  const [newRoomNumber, setNewRoomNumber] = useState('');
  const [newFloor, setNewFloor] = useState(1);
  const [newRoomTypeId, setNewRoomTypeId] = useState('');
  const [newStatus, setNewStatus] = useState('available');

  // Filters
  const [selectedFloor, setSelectedFloor] = useState('all');
  const [selectedStatus, setSelectedStatus] = useState('all');

  // Group rooms by floor
  const floors = Array.from(new Set(rooms.map(r => r.floor || 1))).sort((a, b) => a - b);

  // Handle Quick Status Toggle
  const handleStatusChange = async (room, nextStatus) => {
    setUpdatingRoomId(room.id);
    try {
      await api.updateRoom(room.id, { status: nextStatus }, token);
      addToast?.('success', `Room ${room.room_number} set to ${nextStatus.toUpperCase()}`);
      onRefreshData?.();
    } catch (err) {
      addToast?.('error', `⚠️ Failed to update room: ${err.message}`);
    } finally {
      setUpdatingRoomId(null);
    }
  };

  // Handle Create Physical Room
  const handleCreateRoom = async (e) => {
    e.preventDefault();
    if (!newRoomNumber.trim()) {
      addToast?.('error', "Room number is required.");
      return;
    }
    if (!newRoomTypeId) {
      addToast?.('error', "Please select a suite type category.");
      return;
    }

    setSubmitting(true);
    try {
      await api.createRoom({
        hotel_id: hotel.id,
        room_type_id: newRoomTypeId,
        room_number: newRoomNumber.trim(),
        floor: parseInt(newFloor, 10),
        status: newStatus
      }, token);

      addToast?.('success', `Room ${newRoomNumber} added successfully!`);
      setAddModalOpen(false);
      setNewRoomNumber('');
      setNewFloor(1);
      onRefreshData?.();
    } catch (err) {
      addToast?.('error', `⚠️ Error creating room: ${err.message}`);
    } finally {
      setSubmitting(false);
    }
  };

  // Handle Delete Physical Room
  const handleDeleteRoom = async (room) => {
    if (!window.confirm(`Are you sure you want to delete Room ${room.room_number}?`)) {
      return;
    }

    try {
      await api.deleteRoom(room.id, token);
      addToast?.('success', `Room ${room.room_number} removed from inventory.`);
      onRefreshData?.();
    } catch (err) {
      addToast?.('error', `⚠️ Failed to delete room: ${err.message}`);
    }
  };

  // Filtered rooms
  const filteredRooms = rooms.filter(r => {
    if (selectedFloor !== 'all' && (r.floor || 1) !== parseInt(selectedFloor, 10)) return false;
    if (selectedStatus !== 'all' && (r.status || '').toLowerCase() !== selectedStatus.toLowerCase()) return false;
    return true;
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '22px' }}>
      {/* Top Banner */}
      <div className="portal-banner">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#dfc471', display: 'inline-block' }} />
            <span style={{ fontSize: '11px', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#dfc471' }}>
              Inventory Matrix
            </span>
          </div>
          <h1 className="portal-banner-title">
            Physical Room Grid
          </h1>
          <p className="portal-banner-subtitle">
            Monitor floor-by-floor door status, housekeeping cleanliness, and maintenance locks for <span style={{ color: '#dfc471' }}>{hotel?.name}</span>
          </p>
        </div>

        {canManage && (
          <button
            type="button"
            onClick={() => {
              setNewRoomTypeId(roomTypes[0]?.id || '');
              setAddModalOpen(true);
            }}
            className="portal-btn-gold"
          >
            <span>+</span>
            <span>Add Physical Room</span>
          </button>
        )}
      </div>

      {/* Filter Bars */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
        {/* Floor Filter */}
        <div className="portal-tabs-bar">
          <button
            type="button"
            onClick={() => setSelectedFloor('all')}
            className={`portal-tab-pill ${selectedFloor === 'all' ? 'active' : ''}`}
          >
            All Floors ({rooms.length})
          </button>
          {floors.map(fl => {
            const count = rooms.filter(r => (r.floor || 1) === fl).length;
            return (
              <button
                key={fl}
                type="button"
                onClick={() => setSelectedFloor(fl.toString())}
                className={`portal-tab-pill ${selectedFloor === fl.toString() ? 'active' : ''}`}
              >
                Floor {fl} ({count})
              </button>
            );
          })}
        </div>

        {/* Status Filter */}
        <div className="portal-tabs-bar">
          {[
            { id: 'all', label: `All Statuses (${rooms.length})` },
            { id: 'available', label: `Available (${rooms.filter(r => (r.status || '').toLowerCase() === 'available').length})` },
            { id: 'occupied', label: `Occupied (${rooms.filter(r => ['occupied', 'in_house'].includes((r.status || '').toLowerCase())).length})` },
            { id: 'maintenance', label: `Maintenance (${rooms.filter(r => (r.status || '').toLowerCase() === 'maintenance').length})` },
          ].map(st => (
            <button
              key={st.id}
              type="button"
              onClick={() => setSelectedStatus(st.id)}
              className={`portal-tab-pill ${selectedStatus === st.id ? 'active' : ''}`}
            >
              {st.label}
            </button>
          ))}
        </div>
      </div>

      {/* Rooms Grid */}
      {filteredRooms.length === 0 ? (
        <div className="portal-card" style={{ textAlign: 'center', padding: '60px 20px' }}>
          <div style={{ fontSize: '3rem', marginBottom: '12px' }}>🚪</div>
          <h3 className="portal-card-title">No Physical Rooms In This Filter</h3>
          <p style={{ fontSize: '13px', color: '#64748b', marginTop: '6px' }}>
            Add physical suite door numbers to enable front desk room keys and resident check-ins.
          </p>
          {canManage && (
            <button
              type="button"
              onClick={() => setAddModalOpen(true)}
              className="portal-btn-sm portal-btn-secondary"
              style={{ color: '#dfc471', marginTop: '16px' }}
            >
              + Add Room Door
            </button>
          )}
        </div>
      ) : (
        <div className="portal-grid-4">
          {filteredRooms.map(room => {
            const rt = roomTypes.find(t => t.id === room.room_type_id);
            const statusLower = (room.status || '').toLowerCase();
            const isUpdating = updatingRoomId === room.id;

            let badgeClass = "portal-badge-green";
            let badgeIcon = "✨";
            if (statusLower === 'occupied') {
              badgeClass = "portal-badge-blue";
              badgeIcon = "👤";
            } else if (statusLower === 'maintenance') {
              badgeClass = "portal-badge-gold";
              badgeIcon = "🔧";
            }

            return (
              <div key={room.id} className="portal-room-card">
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
                    <div>
                      <div className="portal-room-number">
                        🚪 {room.room_number}
                      </div>
                      <div style={{ fontSize: '11px', color: '#64748b', marginTop: '2px' }}>
                        Floor {room.floor || 1}
                      </div>
                    </div>

                    <span className={`portal-badge ${badgeClass}`}>
                      <span>{badgeIcon}</span>
                      <span>{room.status || 'Available'}</span>
                    </span>
                  </div>

                  <div style={{ padding: '10px 12px', borderRadius: '10px', background: 'rgba(7, 10, 18, 0.6)', border: '1px solid rgba(255, 255, 255, 0.05)', marginBottom: '14px' }}>
                    <div style={{ fontSize: '10px', color: '#64748b', textTransform: 'uppercase' }}>Suite Category</div>
                    <div style={{ fontSize: '12px', fontWeight: 600, color: '#dfc471', marginTop: '2px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {rt?.name || "Standard Luxury Suite"}
                    </div>
                    {rt?.base_price && (
                      <div style={{ fontSize: '11px', color: '#94a3b8', fontFamily: 'monospace', marginTop: '2px' }}>
                        ${parseFloat(rt.base_price).toLocaleString()} / night
                      </div>
                    )}
                  </div>
                </div>

                {/* Status Switcher & Actions */}
                <div style={{ borderTop: '1px solid rgba(255, 255, 255, 0.06)', paddingTop: '10px' }}>
                  <div style={{ fontSize: '10px', color: '#64748b', textTransform: 'uppercase', fontWeight: 600, marginBottom: '6px' }}>
                    Quick Status Toggle:
                  </div>
                  <div className="portal-room-actions">
                    <button
                      type="button"
                      disabled={isUpdating || statusLower === 'available'}
                      onClick={() => handleStatusChange(room, 'available')}
                      className={`portal-room-act-btn ${statusLower === 'available' ? 'active-avail' : ''}`}
                    >
                      Clean
                    </button>
                    <button
                      type="button"
                      disabled={isUpdating || statusLower === 'occupied'}
                      onClick={() => handleStatusChange(room, 'occupied')}
                      className={`portal-room-act-btn ${statusLower === 'occupied' ? 'active-occ' : ''}`}
                    >
                      Occupied
                    </button>
                    <button
                      type="button"
                      disabled={isUpdating || statusLower === 'maintenance'}
                      onClick={() => handleStatusChange(room, 'maintenance')}
                      className={`portal-room-act-btn ${statusLower === 'maintenance' ? 'active-maint' : ''}`}
                    >
                      Service
                    </button>
                  </div>

                  {canManage && (
                    <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '8px' }}>
                      <button
                        type="button"
                        onClick={() => handleDeleteRoom(room)}
                        style={{ fontSize: '11px', color: '#f87171', background: 'none', border: 'none', padding: 0, cursor: 'pointer' }}
                      >
                        Delete Room
                      </button>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Add Room Modal */}
      {addModalOpen && (
        <div className="portal-modal-backdrop">
          <div className="portal-modal-box" style={{ maxWidth: '440px' }}>
            <div className="portal-modal-header">
              <div>
                <h3 className="portal-card-title" style={{ fontSize: '1.25rem' }}>Add Physical Room</h3>
                <p className="portal-card-subtitle">
                  Property: <span style={{ color: '#dfc471' }}>{hotel?.name}</span>
                </p>
              </div>
              <button
                type="button"
                onClick={() => setAddModalOpen(false)}
                className="portal-modal-close"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateRoom} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div className="portal-form-group">
                <label className="portal-label">
                  Room / Door Number *
                </label>
                <input
                  type="text"
                  required
                  placeholder="e.g. 101, 204, Penthouse A"
                  value={newRoomNumber}
                  onChange={(e) => setNewRoomNumber(e.target.value)}
                  className="portal-input"
                  style={{ fontFamily: 'monospace' }}
                />
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div className="portal-form-group">
                  <label className="portal-label">
                    Floor Level *
                  </label>
                  <input
                    type="number"
                    min="1"
                    max="100"
                    required
                    value={newFloor}
                    onChange={(e) => setNewFloor(e.target.value)}
                    className="portal-input"
                    style={{ fontFamily: 'monospace' }}
                  />
                </div>
                <div className="portal-form-group">
                  <label className="portal-label">
                    Initial Status
                  </label>
                  <select
                    value={newStatus}
                    onChange={(e) => setNewStatus(e.target.value)}
                    className="portal-select"
                  >
                    <option value="available">Clean / Available</option>
                    <option value="occupied">Occupied</option>
                    <option value="maintenance">Maintenance</option>
                  </select>
                </div>
              </div>

              <div className="portal-form-group">
                <label className="portal-label">
                  Suite Category *
                </label>
                <select
                  value={newRoomTypeId}
                  onChange={(e) => setNewRoomTypeId(e.target.value)}
                  required
                  className="portal-select"
                >
                  <option value="" disabled>Select Suite Type</option>
                  {roomTypes.map(rt => (
                    <option key={rt.id} value={rt.id}>
                      {rt.name} (${parseFloat(rt.base_price).toLocaleString()}/night)
                    </option>
                  ))}
                </select>
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', paddingTop: '16px', borderTop: '1px solid rgba(255, 255, 255, 0.08)' }}>
                <button
                  type="button"
                  onClick={() => setAddModalOpen(false)}
                  className="portal-btn-secondary"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="portal-btn-gold"
                >
                  {submitting ? "Adding..." : "Add Room"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
