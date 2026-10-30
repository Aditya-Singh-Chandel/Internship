import React from 'react';

const FALLBACK_HERO = "https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=1200&q=80";

export default function HotelCard({ hotel, onSelectHotel }) {
  // Dynamic media loaded directly from PostgreSQL media table
  const heroImage = hotel.heroImage || 
                    hotel.media?.find(m => m.is_primary)?.image_url || 
                    hotel.media?.[0]?.image_url || 
                    FALLBACK_HERO;

  const rating = hotel.averageRating ? parseFloat(hotel.averageRating) : null;
  const reviewCount = hotel.reviewCount || 0;
  const minPrice = hotel.minPrice ? Math.round(hotel.minPrice) : null;

  // Curated amenity tags based on property keywords & features
  const getTags = () => {
    const text = (hotel.name + " " + (hotel.description || "") + " " + hotel.city).toLowerCase();
    const tags = [];
    if (text.includes("ocean") || text.includes("beach") || text.includes("cabana")) tags.push("Oceanfront Access", "Private Cabanas");
    if (text.includes("ski") || text.includes("snow") || text.includes("chalet") || text.includes("aspen")) tags.push("Ski-in/Ski-out", "Alpine Fireplaces");
    if (text.includes("paris") || text.includes("haussmann")) tags.push("Haussmann Balconies", "Courtyard Salons");
    if (text.includes("tokyo") || text.includes("onsen") || text.includes("fuji")) tags.push("Hinoki Onsen", "Mount Fuji Views");
    if (text.includes("new york") || text.includes("park") || text.includes("skyline")) tags.push("Central Park Views", "White Glove Concierge");
    if (text.includes("london") || text.includes("mayfair")) tags.push("Savile Row Concierge", "Heritage Tea Salon");
    if (text.includes("santorini") || text.includes("caldera")) tags.push("Caldera Infinity Pool", "Volcanic Cave Suites");
    if (text.includes("bali") || text.includes("zen") || text.includes("rainforest")) tags.push("Jungle Plunge Villas", "Ayurvedic Sanctuary");
    if (tags.length === 0) tags.push("Michelin Dining", "Private Concierge", "Luxury Spa");
    return tags.slice(0, 3);
  };

  return (
    <div className="hotel-card">
      <div className="hotel-card-media">
        <img 
          src={heroImage} 
          alt={hotel.name} 
          className="hotel-card-img" 
          loading="lazy"
          onError={(e) => {
            e.target.onerror = null;
            e.target.src = FALLBACK_HERO;
          }}
        />
        <div className="hotel-badge-city">
          📍 {hotel.city}, {hotel.country || "USA"}
        </div>
        <div className="hotel-badge-rating">
          {rating ? (
            <>
              <span style={{ color: '#eab308' }}>★</span>
              <span>{rating.toFixed(1)}</span>
              <span style={{ color: '#94a3b8', fontSize: '11px', fontWeight: 500 }}>({reviewCount})</span>
            </>
          ) : (
            <>
              <span style={{ color: 'var(--gold-400)' }}>✦</span>
              <span style={{ fontSize: '11px', fontWeight: 600 }}>Sanctuary</span>
            </>
          )}
        </div>
      </div>

      <div className="hotel-card-body">
        <h3 className="hotel-card-title">{hotel.name}</h3>
        <p className="hotel-card-desc">
          {hotel.description || "A masterfully curated sanctuary delivering timeless luxury, bespoke concierge hospitality, and Michelin-caliber dining."}
        </p>

        <div className="hotel-amenities-tags">
          {getTags().map((tag, idx) => (
            <span key={idx} className="amenity-tag">✦ {tag}</span>
          ))}
        </div>

        <div className="hotel-card-footer">
          <div className="hotel-price-block">
            <span className="price-eyebrow">Rates From</span>
            {minPrice ? (
              <div className="price-amount">
                ${minPrice} <span>/ night</span>
              </div>
            ) : (
              <div className="price-amount" style={{ fontSize: '0.95rem', color: 'var(--gold-600)' }}>
                View Available Suites
              </div>
            )}
          </div>

          <button 
            type="button"
            className="btn-primary"
            style={{ padding: '8px 18px', fontSize: '0.84rem' }}
            onClick={() => onSelectHotel(hotel)}
          >
            Explore Suites
          </button>
        </div>
      </div>
    </div>
  );
}
