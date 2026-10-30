import React, { useState } from 'react';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';
const FALLBACK_ROOM_IMG = "https://images.unsplash.com/photo-1590490360182-c33d57733427?auto=format&fit=crop&w=800&q=80";

export default function BookingModal({ 
  hotel, 
  roomType, 
  initialCheckin, 
  initialCheckout, 
  onClose, 
  onBookingSuccess 
}) {
  const { user, token } = useAuth();

  const [checkin, setCheckin] = useState(() => {
    if (initialCheckin) return initialCheckin;
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    return tomorrow.toISOString().split('T')[0];
  });

  const [checkout, setCheckout] = useState(() => {
    if (initialCheckout) return initialCheckout;
    const end = new Date();
    end.setDate(end.getDate() + 4);
    return end.toISOString().split('T')[0];
  });

  const [specialRequests, setSpecialRequests] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [confirmation, setConfirmation] = useState(null);

  if (!hotel || !roomType) return null;

  // Nights calculation
  const inDate = new Date(checkin);
  const outDate = new Date(checkout);
  const diffTime = outDate.getTime() - inDate.getTime();
  const nights = Math.max(1, Math.ceil(diffTime / (1000 * 60 * 60 * 24)));
  const nightlyRate = parseFloat(roomType.base_price || 0);
  const totalAmount = nights * nightlyRate;

  // Dynamic image loaded from PostgreSQL media table
  const roomImg = roomType.imageUrl || hotel.heroImage || FALLBACK_ROOM_IMG;

  const handleConfirm = async (e) => {
    e.preventDefault();
    setError('');

    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const selectedIn = new Date(checkin + "T00:00:00");

    if (selectedIn < today) {
      setError("Check-in date cannot be in the past. Please select today or a future date.");
      return;
    }

    if (outDate <= inDate) {
      setError("Check-out date must be strictly after check-in date.");
      return;
    }

    setSubmitting(true);
    try {
      const payload = {
        hotel_id: hotel.id,
        checkin_date: checkin,
        checkout_date: checkout,
        total_amount: totalAmount,
        special_requests: specialRequests.trim() || undefined,
        status: "confirmed",
        items: [
          {
            room_type_id: roomType.id,
            quantity: 1,
            unit_price: nightlyRate
          }
        ]
      };

      const res = await api.createBooking(payload, token);
      const bookingData = res.data;
      setConfirmation({
        id: bookingData.id,
        checkin,
        checkout,
        nights,
        totalAmount,
        hotelName: hotel.name,
        roomName: roomType.name
      });
      onBookingSuccess?.(bookingData);
    } catch (err) {
      setError(err.message || "Failed to finalize reservation. Please try again.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay" data-lenis-prevent onClick={onClose}>
      <div className="modal-card" data-lenis-prevent style={{ maxWidth: '580px' }} onClick={(e) => e.stopPropagation()}>
        <button type="button" className="modal-close-btn" onClick={onClose}>✕</button>

        <div style={{ padding: '32px' }}>
          {confirmation ? (
            /* Confirmation Voucher View */
            <div style={{ textAlign: 'center', padding: '16px 0' }}>
              <div style={{
                width: '60px',
                height: '60px',
                borderRadius: '50%',
                background: 'var(--success-bg)',
                color: 'var(--success)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '28px',
                margin: '0 auto 16px',
                border: '1px solid #bbf7d0'
              }}>
                ✓
              </div>
              <h2 style={{ fontSize: '1.8rem', color: 'var(--navy-950)', marginBottom: '6px' }}>
                Reservation Confirmed!
              </h2>
              <p style={{ fontSize: '0.92rem', marginBottom: '24px' }}>
                Your stay at <strong>{confirmation.hotelName}</strong> has been secured. A confirmation has been added to your guest profile.
              </p>

              {/* Luxury Voucher Card */}
              <div style={{
                background: 'var(--cream-50)',
                border: '1px solid rgba(197, 155, 39, 0.3)',
                borderRadius: 'var(--radius-lg)',
                padding: '20px',
                textAlign: 'left',
                marginBottom: '24px',
                boxShadow: 'var(--shadow-xs)'
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #e2e8f0', paddingBottom: '12px', marginBottom: '12px' }}>
                  <div>
                    <div style={{ fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase', fontWeight: 700 }}>Hotel</div>
                    <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--navy-950)' }}>{confirmation.hotelName}</div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '11px', color: '#94a3b8', textTransform: 'uppercase', fontWeight: 700 }}>Suite</div>
                    <div style={{ fontSize: '15px', fontWeight: 600, color: 'var(--gold-700)' }}>{confirmation.roomName}</div>
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '12px', fontSize: '13px' }}>
                  <div>
                    <span style={{ color: '#64748b', fontSize: '11px', display: 'block' }}>Check-in</span>
                    <strong>{confirmation.checkin}</strong>
                  </div>
                  <div>
                    <span style={{ color: '#64748b', fontSize: '11px', display: 'block' }}>Check-out</span>
                    <strong>{confirmation.checkout}</strong>
                  </div>
                  <div>
                    <span style={{ color: '#64748b', fontSize: '11px', display: 'block' }}>Total Paid</span>
                    <strong style={{ color: 'var(--navy-950)' }}>${confirmation.totalAmount.toFixed(2)}</strong>
                  </div>
                </div>
              </div>

              <button
                type="button"
                className="btn-primary"
                style={{ width: '100%', padding: '12px' }}
                onClick={onClose}
              >
                Close & Return to Browsing
              </button>
            </div>
          ) : (
            /* Booking Checkout Form */
            <div>
              <div style={{ marginBottom: '22px' }}>
                <span style={{
                  fontSize: '11px',
                  fontWeight: 700,
                  letterSpacing: '0.08em',
                  textTransform: 'uppercase',
                  color: 'var(--gold-600)'
                }}>
                  Luxury Stay Checkout
                </span>
                <h2 style={{ fontSize: '1.6rem', color: 'var(--navy-950)', marginTop: '2px' }}>
                  Finalize Reservation
                </h2>
              </div>

              {/* Suite Summary Header */}
              <div style={{
                display: 'flex',
                gap: '16px',
                padding: '14px',
                borderRadius: 'var(--radius-md)',
                background: 'var(--cream-100)',
                border: '1px solid var(--surface-border)',
                marginBottom: '22px',
                alignItems: 'center'
              }}>
                <img 
                  src={roomImg} 
                  alt={roomType.name} 
                  style={{ width: '80px', height: '64px', borderRadius: 'var(--radius-sm)', objectFit: 'cover' }} 
                />
                <div>
                  <div style={{ fontSize: '1.05rem', fontWeight: 700, color: 'var(--navy-950)' }}>{roomType.name}</div>
                  <div style={{ fontSize: '0.84rem', color: 'var(--text-secondary)' }}>{hotel.name} • {hotel.city}</div>
                  <div style={{ fontSize: '0.82rem', color: 'var(--gold-700)', fontWeight: 600, marginTop: '2px' }}>
                    ${nightlyRate.toFixed(2)} / night
                  </div>
                </div>
              </div>

              {error && (
                <div style={{
                  background: 'var(--error-bg)',
                  color: 'var(--error)',
                  padding: '10px 14px',
                  borderRadius: 'var(--radius-md)',
                  fontSize: '0.84rem',
                  marginBottom: '18px',
                  border: '1px solid #fecaca'
                }}>
                  ⚠️ {error}
                </div>
              )}

              <form onSubmit={handleConfirm} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {/* Dates */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px' }}>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: '5px' }}>
                      Check-in Date *
                    </label>
                    <input
                      type="date"
                      required
                      value={checkin}
                      onChange={(e) => setCheckin(e.target.value)}
                      style={{
                        width: '100%',
                        padding: '10px 12px',
                        borderRadius: 'var(--radius-md)',
                        border: '1px solid var(--surface-border)',
                        fontSize: '0.9rem',
                        outline: 'none'
                      }}
                    />
                  </div>
                  <div>
                    <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: '5px' }}>
                      Check-out Date *
                    </label>
                    <input
                      type="date"
                      required
                      value={checkout}
                      onChange={(e) => setCheckout(e.target.value)}
                      style={{
                        width: '100%',
                        padding: '10px 12px',
                        borderRadius: 'var(--radius-md)',
                        border: '1px solid var(--surface-border)',
                        fontSize: '0.9rem',
                        outline: 'none'
                      }}
                    />
                  </div>
                </div>

                {/* Special Requests */}
                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: '5px' }}>
                    Special Preferences / Requests
                  </label>
                  <textarea
                    rows={2}
                    placeholder="e.g. High floor, anniversary celebration, late evening check-in..."
                    value={specialRequests}
                    onChange={(e) => setSpecialRequests(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '10px 12px',
                      borderRadius: 'var(--radius-md)',
                      border: '1px solid var(--surface-border)',
                      fontSize: '0.88rem',
                      outline: 'none',
                      resize: 'none'
                    }}
                  />
                </div>

                {/* Live Financial Calculation Breakdown */}
                <div style={{
                  background: 'var(--cream-50)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--surface-border)',
                  padding: '16px 18px'
                }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.86rem', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                    <span>${nightlyRate.toFixed(2)} × {nights} {nights === 1 ? 'Night' : 'Nights'}</span>
                    <span>${(nightlyRate * nights).toFixed(2)}</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.86rem', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                    <span>Resort Concierge & Amenities Fee</span>
                    <span style={{ color: 'var(--success)' }}>Complimentary</span>
                  </div>
                  <div style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    fontSize: '1.1rem',
                    fontWeight: 700,
                    color: 'var(--navy-950)',
                    borderTop: '1px solid #e2e8f0',
                    paddingTop: '10px',
                    marginTop: '6px'
                  }}>
                    <span>Estimated Total</span>
                    <span>${totalAmount.toFixed(2)}</span>
                  </div>
                </div>

                {/* Guest Account Info */}
                <div style={{ fontSize: '0.78rem', color: '#64748b', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <span>✓ Booking under verified customer account:</span>
                  <strong>{user?.name || user?.email}</strong>
                </div>

                {/* Submit Action */}
                <button
                  type="submit"
                  disabled={submitting}
                  className="btn-primary"
                  style={{
                    width: '100%',
                    padding: '13px',
                    fontSize: '0.95rem',
                    opacity: submitting ? 0.7 : 1
                  }}
                >
                  {submitting ? "Securing Reservation..." : `Confirm & Reserve ($${totalAmount.toFixed(2)})`}
                </button>
              </form>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
