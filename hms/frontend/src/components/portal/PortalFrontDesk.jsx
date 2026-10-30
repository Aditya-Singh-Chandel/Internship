import React, { useState } from 'react';
import { api } from '../../services/api';
import { useAuth } from '../../context/AuthContext';

export default function PortalFrontDesk({ 
  hotel, 
  bookings = [], 
  rooms = [], 
  roomTypes = [], 
  onRefreshData, 
  addToast 
}) {
  const { token } = useAuth();
  const [filterTab, setFilterTab] = useState('all'); // 'all' | 'arrivals' | 'departures' | 'in_house' | 'cancelled'
  const [searchQuery, setSearchQuery] = useState('');
  
  // Room Allocation Modal State
  const [allocatingBooking, setAllocatingBooking] = useState(null);
  const [selectedRoomId, setSelectedRoomId] = useState('');
  const [assigning, setAssigning] = useState(false);

  // Status updating
  const [updatingId, setUpdatingId] = useState(null);

  const todayStr = new Date().toISOString().split('T')[0];

  // Filtering bookings based on tab and search (including Guest Name, Email, and Phone)
  const filteredBookings = bookings.filter(b => {
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      const matchId = b.id?.toLowerCase().includes(q);
      const matchSpecial = b.special_requests?.toLowerCase().includes(q);
      const matchCheckin = b.checkin_date?.includes(q);
      const matchCheckout = b.checkout_date?.includes(q);
      const matchGuestName = b.guest?.name?.toLowerCase().includes(q);
      const matchGuestEmail = b.guest?.email?.toLowerCase().includes(q);
      const matchGuestPhone = b.guest?.phone?.toLowerCase().includes(q);
      if (!matchId && !matchSpecial && !matchCheckin && !matchCheckout && !matchGuestName && !matchGuestEmail && !matchGuestPhone) return false;
    }

    if (filterTab === 'arrivals') {
      return b.checkin_date === todayStr && b.status !== 'cancelled';
    }
    if (filterTab === 'departures') {
      return b.checkout_date === todayStr && b.status !== 'cancelled';
    }
    if (filterTab === 'in_house') {
      return b.status === 'in_house';
    }
    if (filterTab === 'cancelled') {
      return b.status === 'cancelled';
    }
    return true;
  });

  // Action: Express Check-in
  const handleCheckIn = async (booking) => {
    setUpdatingId(booking.id);
    try {
      await api.updateBooking(booking.id, { status: 'in_house' }, token);
      addToast?.('success', `✓ Guest checked in! Stay #${booking.id.substring(0, 8).toUpperCase()} is now In-House.`);
      onRefreshData?.();
    } catch (err) {
      addToast?.('error', `⚠️ Failed to check in: ${err.message}`);
    } finally {
      setUpdatingId(null);
    }
  };

  // Action: Express Check-out
  const handleCheckOut = async (booking) => {
    setUpdatingId(booking.id);
    try {
      await api.updateBooking(booking.id, { status: 'completed' }, token);
      addToast?.('success', `✓ Guest checked out! Stay #${booking.id.substring(0, 8).toUpperCase()} completed.`);
      onRefreshData?.();
    } catch (err) {
      addToast?.('error', `⚠️ Failed to check out: ${err.message}`);
    } finally {
      setUpdatingId(null);
    }
  };

  // Action: Cancel Booking
  const handleCancel = async (booking) => {
    if (!window.confirm(`Are you sure you want to cancel reservation #${booking.id.substring(0, 8).toUpperCase()}?`)) {
      return;
    }
    setUpdatingId(booking.id);
    try {
      await api.cancelBooking(booking.id, "Front desk cancellation", token);
      addToast?.('success', `✓ Reservation cancelled successfully.`);
      onRefreshData?.();
    } catch (err) {
      addToast?.('error', `⚠️ Cancellation error: ${err.message}`);
    } finally {
      setUpdatingId(null);
    }
  };

  // Action: Assign Physical Room
  const handleConfirmRoomAssignment = async (e) => {
    e.preventDefault();
    if (!allocatingBooking || !selectedRoomId) {
      addToast?.('error', "Please select an available physical room number.");
      return;
    }

    setAssigning(true);
    try {
      const item = allocatingBooking.booking_items?.[0];
      const payload = {
        booking_id: allocatingBooking.id,
        room_id: selectedRoomId,
        guest_id: allocatingBooking.guest_id,
        status: "confirmed"
      };
      if (item) {
        payload.booking_item_id = item.id;
      }

      await api.assignBookingRoom(payload, token);
      
      // Update physical room status to occupied
      await api.updateRoom(selectedRoomId, { status: "occupied" }, token).catch(() => {});

      addToast?.('success', `✓ Physical room assigned to reservation #${allocatingBooking.id.substring(0, 8).toUpperCase()}`);
      setAllocatingBooking(null);
      setSelectedRoomId('');
      onRefreshData?.();
    } catch (err) {
      addToast?.('error', `⚠️ Room assignment failed: ${err.message}`);
    } finally {
      setAssigning(false);
    }
  };

  // Available physical rooms for modal allocation
  const availableCleanRooms = rooms.filter(r => (r.status || '').toLowerCase() === 'available');

  const getStatusBadge = (status) => {
    switch(status) {
      case 'in_house':
        return { label: 'In-House Resident', badgeClass: 'portal-badge-blue', icon: '🛎️' };
      case 'confirmed':
        return { label: 'Confirmed Stay', badgeClass: 'portal-badge-green', icon: '✓' };
      case 'completed':
        return { label: 'Completed Stay', badgeClass: 'portal-badge-purple', icon: '✨' };
      case 'cancelled':
        return { label: 'Cancelled', badgeClass: 'portal-badge-red', icon: '✕' };
      default:
        return { label: status || 'Pending', badgeClass: 'portal-badge-gray', icon: '•' };
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '22px' }}>
      {/* Top Banner & Search Controls */}
      <div className="portal-banner">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#dfc471', display: 'inline-block' }} />
            <span style={{ fontSize: '11px', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#dfc471' }}>
              Front Desk Concierge
            </span>
          </div>
          <h1 className="portal-banner-title">
            Guest Stays & Room Allocation
          </h1>
          <p className="portal-banner-subtitle">
            Real-time check-in, key handover, physical door number assignment, and checkout operations
          </p>
        </div>

        {/* Search */}
        <div style={{ width: '100%', maxWidth: '320px' }}>
          <input
            type="text"
            placeholder="Search guest name, email, phone, stay #..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="portal-input"
            style={{ paddingLeft: '14px' }}
          />
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="portal-tabs-bar">
        {[
          { id: 'all', label: `All Stays (${bookings.length})` },
          { id: 'arrivals', label: `Today's Arrivals` },
          { id: 'in_house', label: `In-House` },
          { id: 'departures', label: `Today's Departures` },
          { id: 'cancelled', label: `Cancelled` },
        ].map(tab => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setFilterTab(tab.id)}
            className={`portal-tab-pill ${filterTab === tab.id ? 'active' : ''}`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Bookings Stays Grid */}
      {filteredBookings.length === 0 ? (
        <div className="portal-card" style={{ textAlign: 'center', padding: '60px 20px' }}>
          <div style={{ fontSize: '3rem', marginBottom: '12px' }}>🛎️</div>
          <h3 className="portal-card-title">No Reservations In This View</h3>
          <p style={{ fontSize: '13px', color: '#64748b', marginTop: '6px' }}>
            Bookings will appear here as guests make reservations online or through the front desk.
          </p>
        </div>
      ) : (
        <div className="portal-grid-2">
          {filteredBookings.map(b => {
            const badge = getStatusBadge(b.status);
            const isTodayArrival = b.checkin_date === todayStr;
            const isTodayDeparture = b.checkout_date === todayStr;

            // Check if physical room was assigned directly from booking items/rooms or rooms state
            let allocatedNumber = null;
            let allocatedFloor = null;
            let allocatedRoomId = null;

            for (const bi of b.booking_items || []) {
              for (const br of bi.booking_rooms || []) {
                if (br.room_number) {
                  allocatedNumber = br.room_number;
                  allocatedFloor = br.floor;
                  allocatedRoomId = br.room_id;
                  break;
                }
              }
              if (allocatedNumber) break;
            }

            const assignedRoom = rooms.find(r => 
              r.id === allocatedRoomId ||
              b.booking_rooms?.some(br => br.room_id === r.id) ||
              b.booking_items?.some(bi => bi.booking_rooms?.some(br => br.room_id === r.id))
            );

            const displayRoomNumber = assignedRoom?.room_number || allocatedNumber;
            const displayFloor = assignedRoom?.floor || allocatedFloor || 1;
            const effectiveRoomId = assignedRoom?.id || allocatedRoomId;

            // Resolve suite category directly from eager-loaded database models
            const bookedSuite = 
              b.booking_items?.[0]?.room_type ||
              roomTypes.find(rt => b.booking_items?.some(bi => bi.room_type_id === rt.id));

            return (
              <div key={b.id} className="portal-card" style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
                <div>
                  {/* Card Header */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px', paddingBottom: '14px', borderBottom: '1px solid rgba(255, 255, 255, 0.08)' }}>
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{ fontFamily: 'monospace', fontWeight: 700, fontSize: '15px', color: '#ffffff' }}>
                          #{b.id.substring(0, 8).toUpperCase()}
                        </span>
                        <span className={`portal-badge ${badge.badgeClass}`}>
                          <span>{badge.icon}</span>
                          <span>{badge.label}</span>
                        </span>
                      </div>

                      {/* Linked Guest Name & Contact */}
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '6px', flexWrap: 'wrap' }}>
                        <span style={{ fontSize: '13px', fontWeight: 600, color: '#f8fafc' }}>
                          👤 {b.guest?.name || 'Verified Resident'}
                        </span>
                        {b.guest?.email && (
                          <span style={{ fontSize: '11px', color: '#94a3b8', fontFamily: 'monospace' }}>
                            ({b.guest.email})
                          </span>
                        )}
                        {b.guest?.phone && (
                          <span style={{ fontSize: '11px', color: '#64748b', fontFamily: 'monospace' }}>
                            • {b.guest.phone}
                          </span>
                        )}
                      </div>

                      {/* Linked Suite Type */}
                      <div style={{ fontSize: '12px', color: '#dfc471', fontWeight: 600, marginTop: '4px' }}>
                        🛌 Category: {bookedSuite ? bookedSuite.name : 'Luxury Suite'}
                      </div>

                      {b.special_requests && (
                        <div style={{ fontSize: '11px', color: '#94a3b8', fontStyle: 'italic', marginTop: '4px' }}>
                          Preference: "{b.special_requests}"
                        </div>
                      )}

                      <div style={{ fontSize: '11px', color: '#94a3b8', marginTop: '6px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span>Booked: {new Date(b.created_at).toLocaleDateString()}</span>
                        {isTodayArrival && (
                          <span className="portal-badge portal-badge-gold" style={{ fontSize: '10px', padding: '2px 8px' }}>
                            ARRIVING TODAY
                          </span>
                        )}
                        {isTodayDeparture && (
                          <span className="portal-badge portal-badge-blue" style={{ fontSize: '10px', padding: '2px 8px' }}>
                            DEPARTING TODAY
                          </span>
                        )}
                      </div>
                    </div>

                    <div style={{ textAlign: 'right' }}>
                      <div style={{ fontFamily: 'monospace', fontWeight: 700, fontSize: '1.25rem', color: '#ffffff' }}>
                        ${parseFloat(b.total_amount).toLocaleString()}
                      </div>
                      <div style={{ fontSize: '10px', color: '#64748b', textTransform: 'uppercase' }}>
                        Total Amount
                      </div>
                    </div>
                  </div>

                  {/* Dates & Room Info */}
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px', marginBottom: '16px' }}>
                    <div style={{ padding: '12px', borderRadius: '12px', background: 'rgba(7, 10, 18, 0.6)', border: '1px solid rgba(255, 255, 255, 0.05)' }}>
                      <div style={{ fontSize: '10px', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Check-In Date</div>
                      <div style={{ fontFamily: 'monospace', fontSize: '13px', color: '#ffffff', marginTop: '4px' }}>📅 {b.checkin_date}</div>
                    </div>
                    <div style={{ padding: '12px', borderRadius: '12px', background: 'rgba(7, 10, 18, 0.6)', border: '1px solid rgba(255, 255, 255, 0.05)' }}>
                      <div style={{ fontSize: '10px', color: '#64748b', textTransform: 'uppercase', fontWeight: 600 }}>Check-Out Date</div>
                      <div style={{ fontFamily: 'monospace', fontSize: '13px', color: '#ffffff', marginTop: '4px' }}>📅 {b.checkout_date}</div>
                    </div>
                  </div>

                  {/* Assigned Room Door */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 14px', borderRadius: '12px', background: 'rgba(7, 10, 18, 0.8)', border: '1px solid rgba(255, 255, 255, 0.06)', marginBottom: '16px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '13px' }}>
                      <span style={{ color: '#94a3b8' }}>Physical Suite:</span>
                      {displayRoomNumber ? (
                        <span style={{ fontFamily: 'monospace', fontWeight: 700, color: '#dfc471', display: 'flex', alignItems: 'center', gap: '4px' }}>
                          <span>🚪</span>
                          <span>Room {displayRoomNumber} (Floor {displayFloor})</span>
                        </span>
                      ) : (
                        <span style={{ color: '#f87171', fontWeight: 600, fontSize: '12px' }}>
                          ⚠️ No Door Assigned
                        </span>
                      )}
                    </div>

                    {b.status !== 'cancelled' && b.status !== 'completed' && (
                      <button
                        type="button"
                        onClick={() => {
                          setAllocatingBooking(b);
                          setSelectedRoomId(effectiveRoomId || '');
                        }}
                        className="portal-btn-sm portal-btn-secondary"
                        style={{ color: '#dfc471' }}
                      >
                        {displayRoomNumber ? "Re-assign" : "🔑 Allocate Room"}
                      </button>
                    )}
                  </div>

                  {/* Special Requests */}
                  {b.special_requests && (
                    <div style={{ padding: '10px 14px', borderRadius: '10px', background: 'rgba(255, 255, 255, 0.03)', border: '1px solid rgba(255, 255, 255, 0.05)', marginBottom: '16px', fontSize: '12px', color: '#cbd5e1' }}>
                      <strong style={{ color: '#94a3b8' }}>Guest Notes: </strong>
                      {b.special_requests}
                    </div>
                  )}
                </div>

                {/* Action Buttons */}
                <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', paddingTop: '14px', borderTop: '1px solid rgba(255, 255, 255, 0.08)' }}>
                  {b.status === 'confirmed' && (
                    <button
                      type="button"
                      disabled={updatingId === b.id}
                      onClick={() => handleCheckIn(b)}
                      className="portal-btn-sm portal-btn-gold"
                    >
                      {updatingId === b.id ? "Checking in..." : "🛎️ Express Check-In"}
                    </button>
                  )}

                  {b.status === 'in_house' && (
                    <button
                      type="button"
                      disabled={updatingId === b.id}
                      onClick={() => handleCheckOut(b)}
                      className="portal-btn-sm portal-btn-secondary"
                      style={{ color: '#38bdf8', borderColor: 'rgba(14, 165, 233, 0.3)' }}
                    >
                      {updatingId === b.id ? "Checking out..." : "🚪 Express Check-Out"}
                    </button>
                  )}

                  {b.status !== 'cancelled' && b.status !== 'completed' && (
                    <button
                      type="button"
                      disabled={updatingId === b.id}
                      onClick={() => handleCancel(b)}
                      className="portal-btn-sm portal-btn-danger"
                    >
                      Cancel Stay
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Allocate Room Modal */}
      {allocatingBooking && (
        <div className="portal-modal-backdrop">
          <div className="portal-modal-box">
            <div className="portal-modal-header">
              <div>
                <h3 className="portal-card-title" style={{ fontSize: '1.25rem' }}>
                  Allocate Physical Suite Door
                </h3>
                <p className="portal-card-subtitle">
                  Reservation #{allocatingBooking.id.substring(0, 8).toUpperCase()} • {allocatingBooking.checkin_date} to {allocatingBooking.checkout_date}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setAllocatingBooking(null)}
                className="portal-modal-close"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleConfirmRoomAssignment} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div>
                <label className="portal-label">
                  Select Clean & Available Room Door *
                </label>
                {availableCleanRooms.length === 0 ? (
                  <div style={{ padding: '14px', borderRadius: '12px', background: 'rgba(239, 68, 68, 0.1)', border: '1px solid rgba(239, 68, 68, 0.25)', color: '#f87171', fontSize: '12px' }}>
                    ⚠️ No clean available rooms in inventory. Please set a room to 'Available' in the Room Matrix tab first.
                  </div>
                ) : (
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', maxHeight: '240px', overflowY: 'auto', padding: '4px' }}>
                    {availableCleanRooms.map(r => {
                      const isSelected = selectedRoomId === r.id;
                      const rt = roomTypes.find(t => t.id === r.room_type_id);

                      return (
                        <div
                          key={r.id}
                          onClick={() => setSelectedRoomId(r.id)}
                          style={{
                            padding: '12px',
                            borderRadius: '12px',
                            cursor: 'pointer',
                            border: isSelected ? '1px solid #dfc471' : '1px solid rgba(255, 255, 255, 0.1)',
                            background: isSelected ? 'rgba(197, 155, 39, 0.2)' : '#060910',
                            transition: 'all 0.15s'
                          }}
                        >
                          <div style={{ display: 'flex', justifyContent: 'space-between', fontFamily: 'monospace', fontWeight: 700, fontSize: '14px', color: '#ffffff' }}>
                            <span>🚪 {r.room_number}</span>
                            <span style={{ fontSize: '11px', color: '#64748b' }}>Fl {r.floor || 1}</span>
                          </div>
                          <div style={{ fontSize: '11px', color: '#dfc471', marginTop: '4px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {rt?.name || "Suite"}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '12px', paddingTop: '16px', borderTop: '1px solid rgba(255, 255, 255, 0.08)' }}>
                <button
                  type="button"
                  onClick={() => setAllocatingBooking(null)}
                  className="portal-btn-secondary"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={assigning || !selectedRoomId}
                  className="portal-btn-gold"
                >
                  {assigning ? "Assigning..." : "Confirm Door Allocation"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
