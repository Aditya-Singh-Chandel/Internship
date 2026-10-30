import React, { useState, useEffect } from 'react';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';

export default function MyTripsModal({ 
  isOpen, 
  onClose, 
  hotels = [], 
  onOpenReview, 
  onOpenConcierge,
  refreshKey = 0
}) {
  const { token, user } = useAuth();
  const [bookings, setBookings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [cancellingId, setCancellingId] = useState(null);
  const [cancelModalBooking, setCancelModalBooking] = useState(null);
  const [cancelReason, setCancelReason] = useState('');
  const [cancelError, setCancelError] = useState('');
  const [actionMsg, setActionMsg] = useState('');

  const hotelMap = {};
  hotels.forEach(h => { hotelMap[h.id] = h; });

  const loadBookings = () => {
    if (!token) return;
    setLoading(true);
    api.getMyBookings(token)
      .then(data => {
        setBookings(data || []);
        setLoading(false);
      })
      .catch(() => {
        setBookings([]);
        setLoading(false);
      });
  };

  useEffect(() => {
    if (isOpen) {
      loadBookings();
      setActionMsg('');
      setCancelError('');
    }
  }, [isOpen, token, refreshKey]);

  if (!isOpen) return null;

  // Calculate live cancellation refund estimate
  const getRefundInfo = (b) => {
    const now = new Date();
    const checkinDate = new Date(b.checkin_date + "T14:00:00Z");
    const diffHours = (checkinDate - now) / (1000 * 60 * 60);
    const total = parseFloat(b.total_amount || 0);

    if (diffHours <= 0) {
      return { pct: 0, amount: 0, reason: "Stay has already commenced or check-in deadline passed." };
    } else if (diffHours >= 48) {
      return { pct: 100, amount: total, reason: `More than 48 hours notice (${diffHours.toFixed(1)}h remaining). Eligible for 100% full refund.` };
    } else if (diffHours >= 24) {
      return { pct: 50, amount: total * 0.5, reason: `Between 24 and 48 hours notice (${diffHours.toFixed(1)}h remaining). Eligible for 50% partial refund.` };
    } else {
      return { pct: 0, amount: 0, reason: `Less than 24 hours notice (${diffHours.toFixed(1)}h remaining). Non-refundable window.` };
    }
  };

  const executeCancel = async () => {
    if (!cancelModalBooking) return;
    setCancellingId(cancelModalBooking.id);
    setCancelError('');
    try {
      await api.cancelBooking(cancelModalBooking.id, cancelReason || "Customer cancelled via portal", token);
      setActionMsg(`✓ Reservation at ${hotelMap[cancelModalBooking.hotel_id]?.name || "Hotel"} was cancelled successfully.`);
      setCancelModalBooking(null);
      loadBookings();
    } catch (err) {
      setCancelError(err.message || "Cancellation request failed. Please check policy eligibility.");
    } finally {
      setCancellingId(null);
    }
  };

  return (
    <div className="modal-overlay" data-lenis-prevent onClick={onClose}>
      <div className="modal-card modal-lg" data-lenis-prevent onClick={(e) => e.stopPropagation()}>
        <button type="button" className="modal-close-btn" onClick={onClose}>✕</button>

        <div style={{ padding: '32px' }}>
          {/* Header */}
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
            <div>
              <span style={{ fontSize: '11px', fontWeight: 700, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--gold-600)' }}>
                Guest Portal
              </span>
              <h2 style={{ fontSize: '1.8rem', color: 'var(--navy-950)', marginTop: '2px' }}>
                My Trips & Reservations
              </h2>
              <p style={{ fontSize: '0.88rem' }}>
                Manage your active stays, review cancellation refunds, or share verified feedback.
              </p>
            </div>
            <button
              type="button"
              className="btn-concierge-pill"
              onClick={() => { onClose(); onOpenConcierge(); }}
              style={{ fontSize: '12px' }}
            >
              ✦ Ask AI Concierge
            </button>
          </div>

          {actionMsg && (
            <div style={{
              background: 'var(--success-bg)',
              color: 'var(--success)',
              padding: '12px 16px',
              borderRadius: 'var(--radius-md)',
              fontSize: '0.88rem',
              fontWeight: 500,
              marginBottom: '20px',
              border: '1px solid #bbf7d0'
            }}>
              {actionMsg}
            </div>
          )}

          {/* Bookings List */}
          {loading ? (
            <div style={{ textAlign: 'center', padding: '60px', color: '#94a3b8' }}>Loading your reservations...</div>
          ) : bookings.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '60px', color: '#94a3b8' }}>
              <div style={{ fontSize: '42px', marginBottom: '12px' }}>🧳</div>
              <h3 style={{ fontSize: '1.2rem', color: 'var(--navy-900)', marginBottom: '6px' }}>No reservations on file</h3>
              <p style={{ fontSize: '0.9rem', maxWidth: '400px', margin: '0 auto 20px' }}>
                You currently have no active or completed hotel bookings under <strong>{user?.email}</strong>.
              </p>
              <button type="button" className="btn-primary" onClick={onClose}>
                Browse Luxury Stays
              </button>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              {bookings.map((b) => {
                const hotel = hotelMap[b.hotel_id] || { name: "GrandStay Luxury Hotel", city: "Destination" };
                const isConfirmed = b.status === "confirmed";
                const isCancelled = b.status === "cancelled";
                const isCompleted = b.status === "completed" || new Date(b.checkout_date) < new Date();

                const refundInfo = getRefundInfo(b);

                return (
                  <div
                    key={b.id}
                    style={{
                      background: 'var(--surface-white)',
                      border: '1px solid var(--surface-border)',
                      borderRadius: 'var(--radius-lg)',
                      padding: '22px 24px',
                      boxShadow: 'var(--shadow-xs)',
                      display: 'grid',
                      gridTemplateColumns: '1.4fr 1fr auto',
                      gap: '20px',
                      alignItems: 'center'
                    }}
                  >
                    {/* Hotel & Booking details */}
                    <div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '6px' }}>
                        <h3 style={{ fontSize: '1.2rem', color: 'var(--navy-950)' }}>
                          {b.hotel?.name || hotel.name}
                        </h3>
                        <span style={{
                          fontSize: '11px',
                          fontWeight: 700,
                          textTransform: 'uppercase',
                          padding: '3px 10px',
                          borderRadius: 'var(--radius-full)',
                          background: isConfirmed ? 'var(--success-bg)' : isCancelled ? 'var(--error-bg)' : 'var(--cream-100)',
                          color: isConfirmed ? 'var(--success)' : isCancelled ? 'var(--error)' : 'var(--navy-900)',
                          border: isConfirmed ? '1px solid #bbf7d0' : isCancelled ? '1px solid #fecaca' : '1px solid #cbd5e1'
                        }}>
                          {b.status}
                        </span>
                      </div>
                      <div style={{ fontSize: '0.86rem', color: 'var(--text-secondary)' }}>
                        📍 {b.hotel?.city || hotel.city} • <strong>Dates:</strong> {b.checkin_date} to {b.checkout_date}
                      </div>
                      {/* Linked Suite Type if available */}
                      {b.booking_items?.[0] && (
                        <div style={{ fontSize: '0.82rem', color: 'var(--gold-700)', fontWeight: 600, marginTop: '4px' }}>
                          🛌 Reserved Suite: {b.booking_items[0].room_type?.name || 'Luxury Suite'}
                        </div>
                      )}
                      {b.booking_items?.[0]?.booking_rooms?.[0]?.room_number && (
                        <div style={{ fontSize: '0.8rem', color: '#10b981', fontWeight: 600, marginTop: '2px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                          <span>🚪 Assigned Suite:</span>
                          <span style={{ fontFamily: 'monospace' }}>Room {b.booking_items[0].booking_rooms[0].room_number} (Floor {b.booking_items[0].booking_rooms[0].floor || 1})</span>
                        </div>
                      )}
                      {b.special_requests && (
                        <div style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '4px', fontStyle: 'italic' }}>
                          Preference: "{b.special_requests}"
                        </div>
                      )}
                    </div>

                    {/* Total Amount & Price */}
                    <div>
                      <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase', fontWeight: 700 }}>Total Paid</span>
                      <div style={{ fontSize: '1.35rem', fontWeight: 700, color: 'var(--navy-950)' }}>
                        ${parseFloat(b.total_amount || 0).toFixed(2)}
                      </div>
                      <span style={{ fontSize: '0.76rem', color: '#64748b' }}>Includes all taxes & resort fees</span>
                    </div>

                    {/* Actions */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', minWidth: '150px' }}>
                      {isConfirmed && (
                        <button
                          type="button"
                          className="btn-secondary"
                          style={{
                            fontSize: '0.82rem',
                            padding: '8px 14px',
                            color: '#dc2626',
                            borderColor: '#fca5a5'
                          }}
                          onClick={() => setCancelModalBooking(b)}
                        >
                          Cancel Stay
                        </button>
                      )}

                      {isCompleted && (() => {
                        const existingReview = (b.reviews && b.reviews.length > 0) ? b.reviews[0] : null;
                        if (existingReview) {
                          return (
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', alignItems: 'stretch' }}>
                              <div style={{
                                display: 'inline-flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                gap: '5px',
                                fontSize: '0.78rem',
                                fontWeight: 700,
                                color: '#b45309',
                                background: '#fef3c7',
                                padding: '4px 10px',
                                borderRadius: 'var(--radius-full)',
                                border: '1px solid #fde68a'
                              }}>
                                <span>★ {existingReview.rating}/5</span>
                                <span>Reviewed</span>
                              </div>
                              <button
                                type="button"
                                className="btn-secondary"
                                style={{
                                  fontSize: '0.82rem',
                                  padding: '7px 12px',
                                  color: 'var(--navy-950)',
                                  borderColor: 'var(--gold-500)',
                                  background: '#fff'
                                }}
                                onClick={() => onOpenReview(b, b.hotel || hotel, existingReview)}
                              >
                                ✎ Edit Review
                              </button>
                            </div>
                          );
                        }
                        return (
                          <button
                            type="button"
                            className="btn-primary"
                            style={{ fontSize: '0.82rem', padding: '8px 14px' }}
                            onClick={() => onOpenReview(b, b.hotel || hotel, null)}
                          >
                            ★ Write Review
                          </button>
                        );
                      })()}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Cancellation Confirmation Dialog */}
        {cancelModalBooking && (
          <div className="modal-overlay" data-lenis-prevent style={{ zIndex: 250 }} onClick={() => setCancelModalBooking(null)}>
            <div className="modal-card" data-lenis-prevent style={{ maxWidth: '480px' }} onClick={(e) => e.stopPropagation()}>
              <div style={{ padding: '28px' }}>
                <h3 style={{ fontSize: '1.35rem', color: 'var(--navy-950)', marginBottom: '8px' }}>
                  Cancel Reservation?
                </h3>
                <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)', marginBottom: '18px' }}>
                  Hotel policy evaluation for <strong>{hotelMap[cancelModalBooking.hotel_id]?.name}</strong>:
                </p>

                {/* Refund Evaluation Card */}
                {(() => {
                  const refInfo = getRefundInfo(cancelModalBooking);
                  return (
                    <div style={{
                      background: 'var(--cream-50)',
                      border: '1px solid var(--surface-border)',
                      borderRadius: 'var(--radius-md)',
                      padding: '16px',
                      marginBottom: '18px'
                    }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                        <span style={{ fontSize: '0.85rem', color: '#64748b' }}>Eligible Refund:</span>
                        <strong style={{ fontSize: '1.1rem', color: refInfo.pct > 0 ? 'var(--success)' : 'var(--error)' }}>
                          ${refInfo.amount.toFixed(2)} ({refInfo.pct}%)
                        </strong>
                      </div>
                      <p style={{ fontSize: '0.82rem', color: 'var(--navy-900)' }}>
                        {refInfo.reason}
                      </p>
                    </div>
                  );
                })()}

                {cancelError && (
                  <div style={{
                    background: 'var(--error-bg)',
                    color: 'var(--error)',
                    padding: '10px 14px',
                    borderRadius: 'var(--radius-md)',
                    fontSize: '0.84rem',
                    marginBottom: '16px',
                    border: '1px solid #fecaca'
                  }}>
                    ⚠️ {cancelError}
                  </div>
                )}

                <div style={{ marginBottom: '18px' }}>
                  <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: '6px' }}>
                    Reason for cancellation (Optional)
                  </label>
                  <input
                    type="text"
                    placeholder="e.g. Schedule change, flight cancelled..."
                    value={cancelReason}
                    onChange={(e) => setCancelReason(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '10px 12px',
                      borderRadius: 'var(--radius-md)',
                      border: '1px solid var(--surface-border)',
                      fontSize: '0.88rem',
                      outline: 'none'
                    }}
                  />
                </div>

                <div style={{ display: 'flex', gap: '10px', justifyContent: 'flex-end' }}>
                  <button
                    type="button"
                    className="btn-secondary"
                    onClick={() => setCancelModalBooking(null)}
                  >
                    Keep Booking
                  </button>
                  <button
                    type="button"
                    className="btn-primary"
                    style={{ background: '#dc2626' }}
                    disabled={cancellingId !== null}
                    onClick={executeCancel}
                  >
                    {cancellingId ? "Cancelling..." : "Confirm Cancellation"}
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
