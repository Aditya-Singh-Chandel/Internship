import React, { useState, useEffect, useRef } from 'react';
import { api } from '../services/api';

const DEFAULT_FALLBACK_IMG = "https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=1200&q=80";

export default function HotelDetailModal({ 
  hotel, 
  checkin, 
  checkout, 
  guests, 
  onClose, 
  onBookRoom, 
  onOpenConcierge 
}) {
  const [activeTab, setActiveTab] = useState("rooms"); // 'rooms' | 'policies' | 'reviews' | 'gallery'
  const [roomTypes, setRoomTypes] = useState([]);
  const [policies, setPolicies] = useState([]);
  const [reviews, setReviews] = useState([]);
  const [hotelMedia, setHotelMedia] = useState([]);
  const [selectedGalleryImg, setSelectedGalleryImg] = useState(null);
  const [loading, setLoading] = useState(true);
  const modalCardRef = useRef(null);

  // Auto-scroll modal to top whenever hotel or tab changes
  useEffect(() => {
    if (modalCardRef.current) {
      modalCardRef.current.scrollTop = 0;
    }
  }, [hotel, activeTab]);

  useEffect(() => {
    if (!hotel) return;
    setLoading(true);

    Promise.all([
      api.getRoomTypes(hotel.id, checkin, checkout, 1, false).catch(() => []),
      api.getPolicies(hotel.id).catch(() => []),
      api.getReviews(hotel.id).catch(() => []),
      api.getMedia(hotel.id).catch(() => [])
    ]).then(([roomsData, policiesData, hotelReviews, mediaData]) => {
      setHotelMedia(mediaData || []);

      // Primary hero image from PostgreSQL media table
      const primaryMedia = mediaData.find(m => !m.room_type_id && m.is_primary);
      const fallbackHero = primaryMedia ? primaryMedia.image_url : (hotel.heroImage || DEFAULT_FALLBACK_IMG);
      setSelectedGalleryImg(fallbackHero);

      // Enrich room types with images from the PostgreSQL media table
      const enrichedRooms = roomsData.map(rt => {
        const roomMedia = mediaData.find(m => m.room_type_id === rt.id && m.is_primary)
                       || mediaData.find(m => m.room_type_id === rt.id);
        return {
          ...rt,
          imageUrl: roomMedia ? roomMedia.image_url : fallbackHero
        };
      });
      setRoomTypes(enrichedRooms);

      setPolicies(policiesData);

      // Filter verified guest reviews strictly for this hotel without mock fallbacks
      const matchedReviews = (hotelReviews || []).filter(r => {
        return r.hotel_id === hotel.id && (r.comment || "").length > 2;
      });
      setReviews(matchedReviews);

      setLoading(false);
    });
  }, [hotel, checkin, checkout]);

  if (!hotel) return null;

  // Active hero image from media table
  const heroImage = selectedGalleryImg || hotel.heroImage || DEFAULT_FALLBACK_IMG;
  const galleryImages = hotelMedia.filter(m => !m.room_type_id).map(m => m.image_url);

  const avgRating = reviews.length > 0 
    ? (reviews.reduce((acc, r) => acc + (r.rating || 5), 0) / reviews.length).toFixed(1) 
    : null;

  return (
    <div className="modal-overlay" data-lenis-prevent onClick={onClose}>
      <div 
        ref={modalCardRef}
        className="modal-card modal-lg" 
        data-lenis-prevent 
        onClick={(e) => e.stopPropagation()}
      >
        <button type="button" className="modal-close-btn" onClick={onClose}>✕</button>

        {/* Dynamic Hero Gallery Banner from PostgreSQL Media */}
        <div style={{ position: 'relative', height: '320px', overflow: 'hidden' }}>
          <img 
            src={heroImage} 
            alt={hotel.name} 
            style={{ width: '100%', height: '100%', objectFit: 'cover' }} 
            onError={(e) => {
              e.target.onerror = null;
              e.target.src = DEFAULT_FALLBACK_IMG;
            }}
          />
          <div style={{
            position: 'absolute',
            inset: 0,
            background: 'linear-gradient(180deg, rgba(7, 10, 18, 0.25) 0%, rgba(7, 10, 18, 0.88) 100%)',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'flex-end',
            padding: '28px 32px',
            color: '#ffffff'
          }}>
            <div style={{ display: 'flex', gap: '8px', marginBottom: '8px', flexWrap: 'wrap' }}>
              <span style={{
                background: 'rgba(197, 155, 39, 0.9)',
                color: '#fff',
                fontSize: '11px',
                fontWeight: 700,
                letterSpacing: '0.08em',
                textTransform: 'uppercase',
                padding: '4px 12px',
                borderRadius: 'var(--radius-full)'
              }}>
                Luxury Destination
              </span>
              <span style={{
                background: 'rgba(255, 255, 255, 0.2)',
                backdropFilter: 'blur(8px)',
                color: '#fff',
                fontSize: '11px',
                fontWeight: 600,
                padding: '4px 12px',
                borderRadius: 'var(--radius-full)'
              }}>
                📍 {hotel.city}, {hotel.country || "USA"}
              </span>
              <span style={{
                background: 'rgba(255, 255, 255, 0.2)',
                backdropFilter: 'blur(8px)',
                color: '#fff',
                fontSize: '11px',
                fontWeight: 600,
                padding: '4px 12px',
                borderRadius: 'var(--radius-full)'
              }}>
                ✦ Verified Luxury Sanctuary
              </span>
            </div>
            <h2 style={{ fontSize: '2.2rem', color: '#ffffff', marginBottom: '6px' }}>{hotel.name}</h2>
            <p style={{ color: 'rgba(255, 255, 255, 0.88)', fontSize: '0.9rem' }}>
              {hotel.address_line1} • Phone: {hotel.phone || "+1 (800) 555-HOTEL"} • Email: {hotel.email || "concierge@grandstay.com"}
            </p>
          </div>
        </div>

        {/* Dynamic Gallery Strip if multiple media items exist */}
        {galleryImages.length > 1 && (
          <div style={{
            display: 'flex',
            gap: '8px',
            padding: '10px 32px',
            background: 'var(--cream-100)',
            borderBottom: '1px solid var(--surface-border)',
            overflowX: 'auto'
          }}>
            <span style={{ fontSize: '11px', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-muted)', alignSelf: 'center', marginRight: '6px' }}>
              Property Photos:
            </span>
            {galleryImages.map((imgUrl, idx) => (
              <img
                key={idx}
                src={imgUrl}
                alt={`Property Photo ${idx + 1}`}
                onClick={() => setSelectedGalleryImg(imgUrl)}
                onError={(e) => {
                  e.target.style.display = 'none';
                }}
                style={{
                  width: '64px',
                  height: '44px',
                  borderRadius: 'var(--radius-sm)',
                  objectFit: 'cover',
                  cursor: 'pointer',
                  border: selectedGalleryImg === imgUrl ? '2px solid var(--gold-500)' : '1px solid var(--surface-border)',
                  opacity: selectedGalleryImg === imgUrl ? 1 : 0.7,
                  transition: 'all var(--transition-fast)'
                }}
              />
            ))}
          </div>
        )}

        {/* Navigation Tabs */}
        <div style={{
          display: 'flex',
          borderBottom: '1px solid var(--surface-border)',
          background: 'var(--surface-white)',
          padding: '0 32px'
        }}>
          <button
            type="button"
            style={{
              padding: '16px 20px',
              fontSize: '0.92rem',
              fontWeight: 600,
              color: activeTab === 'rooms' ? 'var(--navy-950)' : 'var(--text-muted)',
              borderBottom: activeTab === 'rooms' ? '3px solid var(--gold-500)' : '3px solid transparent',
              cursor: 'pointer'
            }}
            onClick={() => setActiveTab('rooms')}
          >
            Suites & Accommodations ({roomTypes.length})
          </button>
          <button
            type="button"
            style={{
              padding: '16px 20px',
              fontSize: '0.92rem',
              fontWeight: 600,
              color: activeTab === 'policies' ? 'var(--navy-950)' : 'var(--text-muted)',
              borderBottom: activeTab === 'policies' ? '3px solid var(--gold-500)' : '3px solid transparent',
              cursor: 'pointer'
            }}
            onClick={() => setActiveTab('policies')}
          >
            Hotel Policies & Hours ({policies.length})
          </button>
          <button
            type="button"
            style={{
              padding: '16px 20px',
              fontSize: '0.92rem',
              fontWeight: 600,
              color: activeTab === 'reviews' ? 'var(--navy-950)' : 'var(--text-muted)',
              borderBottom: activeTab === 'reviews' ? '3px solid var(--gold-500)' : '3px solid transparent',
              cursor: 'pointer'
            }}
            onClick={() => setActiveTab('reviews')}
          >
            Verified Guest Reviews {avgRating ? `★ ${avgRating} (${reviews.length})` : `(${reviews.length})`}
          </button>
        </div>

        {/* Tab Body */}
        <div style={{ padding: '28px 32px' }}>
          {/* TAB 1: SUITES */}
          {activeTab === 'rooms' && (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
                <div>
                  <h3 style={{ fontSize: '1.25rem' }}>Available Suites & Rooms</h3>
                  <p style={{ fontSize: '0.86rem', color: '#64748b' }}>
                    {checkin && checkout ? (
                      <span>
                        Showing live availability for stay: <strong style={{ color: 'var(--navy-900)' }}>{checkin}</strong> to <strong style={{ color: 'var(--navy-900)' }}>{checkout}</strong> ({guests || 2} Guest{(guests || 2) > 1 ? 's' : ''})
                      </span>
                    ) : (
                      "Signature accommodations designed for exceptional comfort and tranquility."
                    )}
                  </p>
                </div>
                <button 
                  type="button"
                  className="btn-concierge-pill"
                  onClick={() => { onClose(); onOpenConcierge(); }}
                  style={{ fontSize: '12px' }}
                >
                  ✦ Ask AI About Suites
                </button>
              </div>

              {loading ? (
                <div style={{ textAlign: 'center', padding: '40px', color: '#94a3b8' }}>Loading suites from database...</div>
              ) : roomTypes.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '40px', color: '#94a3b8' }}>No suites currently published for this hotel.</div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '18px' }}>
                  {roomTypes.map((rt) => {
                    const price = parseFloat(rt.base_price || 0).toFixed(2);
                    return (
                      <div 
                        key={rt.id} 
                        style={{
                          display: 'grid',
                          gridTemplateColumns: '220px 1fr auto',
                          gap: '20px',
                          border: '1px solid var(--surface-border)',
                          borderRadius: 'var(--radius-lg)',
                          overflow: 'hidden',
                          background: 'var(--surface-white)',
                          boxShadow: 'var(--shadow-xs)',
                          alignItems: 'center'
                        }}
                      >
                        <img 
                          src={rt.imageUrl} 
                          alt={rt.name} 
                          style={{ width: '100%', height: '150px', objectFit: 'cover' }} 
                          onError={(e) => {
                            e.target.onerror = null;
                            e.target.src = DEFAULT_FALLBACK_IMG;
                          }}
                        />
                        <div style={{ padding: '12px 0' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px', flexWrap: 'wrap' }}>
                            <h4 style={{ fontSize: '1.15rem', color: 'var(--navy-950)', margin: 0 }}>
                              {rt.name}
                            </h4>
                            {rt.is_sold_out ? (
                              <span style={{
                                background: '#fee2e2',
                                color: '#b91c1c',
                                border: '1px solid #fca5a5',
                                padding: '2px 8px',
                                borderRadius: '4px',
                                fontSize: '10px',
                                fontWeight: 700,
                                letterSpacing: '0.04em'
                              }}>
                                SOLD OUT FOR DATES
                              </span>
                            ) : (
                              rt.available_rooms_count !== undefined && rt.available_rooms_count !== null && rt.available_rooms_count <= 2 ? (
                                <span style={{
                                  background: '#fef3c7',
                                  color: '#b45309',
                                  border: '1px solid #fde68a',
                                  padding: '2px 8px',
                                  borderRadius: '4px',
                                  fontSize: '10px',
                                  fontWeight: 700
                                }}>
                                  🔥 ONLY {rt.available_rooms_count} LEFT
                                </span>
                              ) : (
                                <span style={{
                                  background: '#ecfdf5',
                                  color: '#047857',
                                  border: '1px solid #a7f3d0',
                                  padding: '2px 8px',
                                  borderRadius: '4px',
                                  fontSize: '10px',
                                  fontWeight: 700
                                }}>
                                  ✓ AVAILABLE
                                </span>
                              )
                            )}
                          </div>
                          <p style={{ fontSize: '0.84rem', color: 'var(--text-secondary)', marginBottom: '8px' }}>
                            {rt.description || "Spacious luxury sanctuary featuring plush bedding, Italian marble bathroom, and panoramic scenic views."}
                          </p>
                          <div style={{ display: 'flex', gap: '10px', fontSize: '0.78rem', color: '#64748b', flexWrap: 'wrap', alignItems: 'center' }}>
                            <span>👥 Up to {rt.guests_allowed || 2} Guests</span>
                            <span>•</span>
                            <span>✨ Dedicated Private Concierge</span>
                            <span>•</span>
                            <span>📶 High-Speed WiFi</span>
                            {guests && rt.guests_allowed && guests > rt.guests_allowed && (
                              <span style={{ color: '#dc2626', fontWeight: 600 }}>
                                (⚠️ Max {rt.guests_allowed} guests allowed)
                              </span>
                            )}
                          </div>
                        </div>
                        <div style={{ padding: '0 24px', textAlign: 'right', display: 'flex', flexDirection: 'column', gap: '8px', minWidth: '160px' }}>
                          <div>
                            <span style={{ fontSize: '1.35rem', fontWeight: 700, color: 'var(--navy-950)' }}>${price}</span>
                            <span style={{ fontSize: '0.8rem', color: '#64748b' }}> / night</span>
                          </div>
                          {rt.is_sold_out ? (
                            <button
                              type="button"
                              disabled
                              style={{
                                padding: '8px 18px',
                                fontSize: '0.85rem',
                                background: '#f1f5f9',
                                color: '#94a3b8',
                                border: '1px solid #cbd5e1',
                                borderRadius: 'var(--radius-md)',
                                cursor: 'not-allowed',
                                fontWeight: 600
                              }}
                              title="No physical rooms available for the selected dates."
                            >
                              Sold Out
                            </button>
                          ) : (
                            <button
                              type="button"
                              className="btn-primary"
                              style={{ padding: '8px 18px', fontSize: '0.85rem' }}
                              onClick={() => onBookRoom(hotel, rt)}
                            >
                              Book This Room
                            </button>
                          )}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* TAB 2: POLICIES */}
          {activeTab === 'policies' && (
            <div>
              <div style={{ marginBottom: '20px' }}>
                <h3 style={{ fontSize: '1.25rem' }}>Hotel Operational Policies & Timings</h3>
                <p style={{ fontSize: '0.86rem' }}>Essential guidelines to ensure your stay is comfortable and seamless.</p>
              </div>

              {policies.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '40px', color: '#94a3b8' }}>No policies documented for this hotel.</div>
              ) : (
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '16px' }}>
                  {policies.map((p) => {
                    const cleanType = (p.policy_type || "GENERAL").replace(/_/g, " ").toUpperCase();
                    return (
                      <div 
                        key={p.id}
                        style={{
                          background: 'var(--cream-50)',
                          border: '1px solid var(--surface-border)',
                          borderRadius: 'var(--radius-md)',
                          padding: '16px 18px'
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                          <span style={{
                            fontSize: '11px',
                            fontWeight: 700,
                            letterSpacing: '0.06em',
                            color: 'var(--gold-700)',
                            background: 'var(--gold-100)',
                            padding: '3px 8px',
                            borderRadius: 'var(--radius-sm)'
                          }}>
                            {cleanType}
                          </span>
                        </div>
                        <p style={{ fontSize: '0.86rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                          {p.description}
                        </p>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* TAB 3: VERIFIED REVIEWS */}
          {activeTab === 'reviews' && (
            <div>
              <div style={{ marginBottom: '20px' }}>
                <h3 style={{ fontSize: '1.25rem' }}>Authentic Guest Experiences</h3>
                <p style={{ fontSize: '0.86rem' }}>Verified ratings and feedback submitted by guests who completed stays.</p>
              </div>

              {reviews.length === 0 ? (
                <div style={{ textAlign: 'center', padding: '48px 20px', background: 'var(--cream-50)', borderRadius: 'var(--radius-lg)', border: '1px solid var(--surface-border)' }}>
                  <div style={{ fontSize: '32px', marginBottom: '8px' }}>📝</div>
                  <h4 style={{ color: 'var(--navy-900)', fontSize: '1.1rem', marginBottom: '4px' }}>No Verified Reviews Yet</h4>
                  <p style={{ fontSize: '0.86rem', color: 'var(--text-secondary)', maxWidth: '420px', margin: '0 auto' }}>
                    Be among the first distinguished travelers to experience this sanctuary and share your impressions after your stay.
                  </p>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
                  {reviews.map((r, idx) => (
                    <div
                      key={idx}
                      style={{
                        background: 'var(--surface-white)',
                        border: '1px solid var(--surface-border)',
                        borderRadius: 'var(--radius-md)',
                        padding: '18px 20px',
                        boxShadow: 'var(--shadow-xs)'
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                          <div style={{
                            width: '32px',
                            height: '32px',
                            borderRadius: '50%',
                            background: 'linear-gradient(135deg, var(--gold-400), var(--gold-600))',
                            color: '#fff',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            fontSize: '12px',
                            fontWeight: 700
                          }}>
                            {(r.guest_name || "G")[0]}
                          </div>
                          <div>
                            <div style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--navy-950)' }}>
                              {r.guest_name || "Distinguished Guest"}
                            </div>
                            <div style={{ fontSize: '0.74rem', color: 'var(--text-muted)' }}>
                              Verified Completed Stay
                            </div>
                          </div>
                        </div>
                        <div style={{ color: '#eab308', fontSize: '15px' }}>
                          {'★'.repeat(r.rating || 5)}{'☆'.repeat(5 - (r.rating || 5))}
                        </div>
                      </div>
                      <p style={{ fontSize: '0.88rem', color: 'var(--text-secondary)', fontStyle: 'italic', margin: 0 }}>
                        "{r.comment}"
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
