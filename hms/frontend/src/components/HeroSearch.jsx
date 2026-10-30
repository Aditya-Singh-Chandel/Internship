import React from 'react';

export default function HeroSearch({ 
  destination, 
  setDestination, 
  checkin, 
  setCheckin, 
  checkout, 
  setCheckout, 
  guests, 
  setGuests, 
  onSearch,
  hotels = []
}) {
  const [dateError, setDateError] = React.useState('');

  const getTodayStr = () => {
    const d = new Date();
    return d.toISOString().split('T')[0];
  };

  const getTomorrowStr = (baseStr) => {
    const d = baseStr ? new Date(baseStr + "T00:00:00") : new Date();
    d.setDate(d.getDate() + 1);
    return d.toISOString().split('T')[0];
  };

  const handleCheckinChange = (val) => {
    setDateError('');
    setCheckin(val);
    if (!val) return;
    
    // If checkout is empty or checkout <= new checkin, auto-advance checkout to checkin + 1 day
    if (!checkout || checkout <= val) {
      setCheckout(getTomorrowStr(val));
    }
  };

  const handleCheckoutChange = (val) => {
    setDateError('');
    setCheckout(val);
    if (checkin && val && val <= checkin) {
      setDateError('Check-out date must be after check-in date.');
    }
  };

  const handleSearchSubmit = () => {
    const today = getTodayStr();
    if (checkin && checkin < today) {
      setDateError('Check-in date cannot be in the past.');
      return;
    }
    if (checkin && checkout && checkout <= checkin) {
      setDateError('Check-out date must be at least 1 day after check-in date.');
      return;
    }
    setDateError('');
    onSearch?.();
  };

  // Derive quick destinations dynamically from real database hotels
  const distinctCities = Array.from(new Set((hotels || []).map(h => h.city).filter(Boolean)));
  const quickDestinations = [
    { label: "🌐 Global (All)", value: "" },
    ...distinctCities.map(city => ({ label: city, value: city }))
  ];


  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      handleSearchSubmit();
    }
  };

  const todayStr = getTodayStr();
  const minCheckoutStr = checkin ? getTomorrowStr(checkin) : getTomorrowStr(todayStr);

  return (
    <div className="hero-container-wrap">
      <section className="hero-section">
        <div className="hero-content">
          <div className="hero-eyebrow">
            <span>✦</span> Curated Luxury Hospitality
          </div>
          <h1 className="hero-headline">
            Immerse Yourself in <span>Unrivaled</span> Luxury.
          </h1>
          <p className="hero-subtext">
            Direct search across private oceanfront villas, alpine ski chalets, Parisian suites, and skyline penthouses worldwide with the GrandStay AI Concierge.
          </p>

          {/* Quick Destination Chips */}
          <div style={{
            display: 'flex',
            flexWrap: 'wrap',
            justifyContent: 'center',
            gap: '8px',
            marginBottom: '10px'
          }}>
            {quickDestinations.map((d, idx) => {
              const isSelected = (!destination && d.value === "") || (destination.toLowerCase() === d.value.toLowerCase());
              return (
                <button
                  key={idx}
                  type="button"
                  onClick={() => setDestination(d.value)}
                  style={{
                    padding: '6px 14px',
                    borderRadius: 'var(--radius-full)',
                    fontSize: '0.82rem',
                    fontWeight: 600,
                    cursor: 'pointer',
                    border: isSelected ? '1px solid var(--gold-400)' : '1px solid rgba(255, 255, 255, 0.25)',
                    background: isSelected ? 'rgba(197, 155, 39, 0.35)' : 'rgba(11, 17, 30, 0.6)',
                    color: isSelected ? '#ffffff' : 'rgba(255, 255, 255, 0.85)',
                    backdropFilter: 'blur(8px)',
                    transition: 'all var(--transition-fast)'
                  }}
                >
                  {d.label}
                </button>
              );
            })}
          </div>
        </div>
      </section>

      {/* Floating Direct Search Bar */}
      <div className="search-bar-floating-wrap max-width-wrapper">
        <div className="search-bar-card">
          {/* Friendly Date Error Banner */}
          {dateError && (
            <div style={{
              position: 'absolute',
              top: '-42px',
              left: '50%',
              transform: 'translateX(-50%)',
              background: '#b91c1c',
              color: '#ffffff',
              fontSize: '0.82rem',
              fontWeight: 600,
              padding: '6px 18px',
              borderRadius: 'var(--radius-full)',
              boxShadow: 'var(--shadow-lg)',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              whiteSpace: 'nowrap',
              zIndex: 30,
              animation: 'fadeIn 0.2s ease-in'
            }}>
              <span>⚠️</span> {dateError}
            </div>
          )}

          {/* Direct Text Search */}
          <div className="search-field-item">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span className="search-field-label">Search Destination / Hotel</span>
              {destination && (
                <button
                  type="button"
                  onClick={() => setDestination('')}
                  style={{
                    border: 'none',
                    background: 'none',
                    fontSize: '11px',
                    color: 'var(--gold-600)',
                    cursor: 'pointer',
                    fontWeight: 600
                  }}
                  title="Clear to show all global hotels"
                >
                  Clear (Global)
                </button>
              )}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '2px' }}>
              <span style={{ color: 'var(--gold-500)', fontSize: '1.1rem' }}>🔍</span>
              <input
                type="text"
                className="search-field-input"
                placeholder="Where to? (e.g. Miami, Paris, Tokyo, Aspen, London...)"
                value={destination}
                onChange={(e) => setDestination(e.target.value)}
                onKeyDown={handleKeyDown}
                style={{ width: '100%', fontSize: '0.94rem' }}
                autoComplete="off"
              />
            </div>
          </div>

          {/* Check-In */}
          <div className="search-field-item">
            <span className="search-field-label">Check-in</span>
            <input
              type="date"
              className="search-field-input"
              value={checkin}
              min={todayStr}
              onChange={(e) => handleCheckinChange(e.target.value)}
            />
          </div>

          {/* Check-Out */}
          <div className="search-field-item">
            <span className="search-field-label">Check-out</span>
            <input
              type="date"
              className="search-field-input"
              value={checkout}
              min={minCheckoutStr}
              onChange={(e) => handleCheckoutChange(e.target.value)}
            />
          </div>

          {/* Guests */}
          <div className="search-field-item">
            <span className="search-field-label">Guests</span>
            <select
              className="search-field-input"
              value={guests}
              onChange={(e) => setGuests(Number(e.target.value))}
              style={{ cursor: 'pointer' }}
            >
              <option value={1}>1 Guest</option>
              <option value={2}>2 Guests</option>
              <option value={3}>3 Guests</option>
              <option value={4}>4 Guests</option>
              <option value={5}>5+ Guests</option>
            </select>
          </div>

          {/* Search Action */}
          <div>
            <button
              type="button"
              className="btn-primary"
              style={{ padding: '14px 28px', fontSize: '0.95rem' }}
              onClick={handleSearchSubmit}
            >
              <span>Explore Stays</span>
              <span>→</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
