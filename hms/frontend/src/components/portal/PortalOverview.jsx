import React from 'react';

export default function PortalOverview({ 
  hotel, 
  rooms = [], 
  bookings = [], 
  onNavigateTab 
}) {
  const totalRooms = rooms.length;
  const availableRooms = rooms.filter(r => (r.status || '').toLowerCase() === 'available').length;
  const occupiedRooms = rooms.filter(r => ['occupied', 'in_house'].includes((r.status || '').toLowerCase())).length;
  const maintenanceRooms = rooms.filter(r => (r.status || '').toLowerCase() === 'maintenance').length;
  
  const occupancyRate = totalRooms > 0 ? Math.round((occupiedRooms / totalRooms) * 100) : 0;

  const todayStr = new Date().toISOString().split('T')[0];
  const todayArrivals = bookings.filter(b => b.checkin_date === todayStr && b.status !== 'cancelled');
  const todayDepartures = bookings.filter(b => b.checkout_date === todayStr && b.status !== 'cancelled');
  const inHouseBookings = bookings.filter(b => b.status === 'in_house');

  const statCards = [
    {
      label: 'Occupancy Rate',
      value: `${occupancyRate}%`,
      sub: `${occupiedRooms} of ${totalRooms} suites occupied`,
      icon: '📈',
      color: '#dfc471',
      iconBg: 'rgba(197, 155, 39, 0.15)',
      iconColor: '#dfc471'
    },
    {
      label: "Today's Arrivals",
      value: todayArrivals.length,
      sub: 'Pending check-ins',
      icon: '🛬',
      color: '#34d399',
      iconBg: 'rgba(16, 185, 129, 0.15)',
      iconColor: '#34d399'
    },
    {
      label: "Today's Departures",
      value: todayDepartures.length,
      sub: 'Scheduled check-outs',
      icon: '🛫',
      color: '#818cf8',
      iconBg: 'rgba(99, 102, 241, 0.15)',
      iconColor: '#818cf8'
    },
    {
      label: 'Active In-House Stays',
      value: inHouseBookings.length,
      sub: 'Currently in residence',
      icon: '🛎️',
      color: '#38bdf8',
      iconBg: 'rgba(14, 165, 233, 0.15)',
      iconColor: '#38bdf8'
    },
    {
      label: 'Clean Ready Rooms',
      value: availableRooms,
      sub: `${maintenanceRooms} in maintenance`,
      icon: '✨',
      color: '#2dd4bf',
      iconBg: 'rgba(20, 184, 166, 0.15)',
      iconColor: '#2dd4bf'
    }
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header Banner */}
      <div className="portal-banner">
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '4px' }}>
            <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#dfc471', display: 'inline-block' }} />
            <span style={{ fontSize: '11px', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: '#dfc471' }}>
              Operations Cockpit
            </span>
          </div>
          <h1 className="portal-banner-title">
            {hotel?.name || 'Hotel Property Overview'}
          </h1>
          <p className="portal-banner-subtitle">
            📍 {hotel?.city}, {hotel?.country || 'USA'} • Real-time room inventory, arrivals & guest stay management
          </p>
        </div>

        <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={() => onNavigateTab('frontdesk')}
            className="portal-btn-gold"
          >
            <span>🛎️</span>
            <span>Front Desk Hub</span>
          </button>
          <button
            type="button"
            onClick={() => onNavigateTab('rooms')}
            className="portal-btn-secondary"
          >
            <span>🛏️</span>
            <span>Room Matrix</span>
          </button>
          <button
            type="button"
            onClick={() => onNavigateTab('knowledge')}
            className="portal-btn-secondary"
            style={{ color: '#c084fc', borderColor: 'rgba(168, 85, 247, 0.3)' }}
          >
            <span>⚡</span>
            <span>AI Sync</span>
          </button>
        </div>
      </div>

      {/* KPI Stats Grid */}
      <div className="portal-kpi-grid">
        {statCards.map((card, i) => (
          <div key={i} className="portal-kpi-card">
            <div className="portal-kpi-top">
              <span className="portal-kpi-label">{card.label}</span>
              <span 
                className="portal-kpi-icon"
                style={{ background: card.iconBg, color: card.iconColor }}
              >
                {card.icon}
              </span>
            </div>
            <div>
              <div className="portal-kpi-value" style={{ color: card.color }}>
                {card.value}
              </div>
              <div className="portal-kpi-sub">
                {card.sub}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Main Grid: Active Stays Table + Readiness Panel */}
      <div className="portal-grid-2">
        {/* Left Column: Immediate Arrivals & Queue */}
        <div className="portal-card" style={{ padding: '24px 0' }}>
          <div style={{ padding: '0 24px 18px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid rgba(255, 255, 255, 0.08)' }}>
            <div>
              <h2 className="portal-card-title" style={{ fontSize: '1.15rem' }}>
                🛎️ Active Front Desk Stays
              </h2>
              <p className="portal-card-subtitle">
                Current bookings requiring check-in, room key allocation, or departure checkout
              </p>
            </div>
            <button
              onClick={() => onNavigateTab('frontdesk')}
              className="portal-btn-sm portal-btn-secondary"
              style={{ color: '#dfc471' }}
            >
              Full Desk →
            </button>
          </div>

          <div className="portal-table-wrap" style={{ border: 'none', borderRadius: 0, background: 'transparent' }}>
            <table className="portal-table">
              <thead>
                <tr>
                  <th>Stay #</th>
                  <th>Dates</th>
                  <th>Status</th>
                  <th style={{ textAlign: 'right' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {bookings.length === 0 ? (
                  <tr>
                    <td colSpan={4} style={{ textAlign: 'center', padding: '36px', color: '#64748b' }}>
                      No active bookings found for this property.
                    </td>
                  </tr>
                ) : (
                  bookings.slice(0, 6).map((b) => {
                    let badgeClass = "portal-badge-gray";
                    if (b.status === "in_house") badgeClass = "portal-badge-blue";
                    if (b.status === "confirmed") badgeClass = "portal-badge-green";
                    if (b.status === "completed") badgeClass = "portal-badge-purple";
                    if (b.status === "cancelled") badgeClass = "portal-badge-red";

                    return (
                      <tr key={b.id}>
                        <td style={{ fontFamily: 'monospace', fontWeight: 600, color: '#ffffff' }}>
                          #{b.id.substring(0, 8).toUpperCase()}
                        </td>
                        <td style={{ fontSize: '12px' }}>
                          <div>{b.checkin_date}</div>
                          <div style={{ color: '#64748b', fontSize: '11px' }}>to {b.checkout_date}</div>
                        </td>
                        <td>
                          <span className={`portal-badge ${badgeClass}`}>
                            {b.status}
                          </span>
                        </td>
                        <td style={{ textAlign: 'right' }}>
                          <button
                            onClick={() => onNavigateTab('frontdesk')}
                            className="portal-btn-sm portal-btn-secondary"
                            style={{ color: '#dfc471' }}
                          >
                            Manage
                          </button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Right Column: Physical Room Readiness & AI Knowledge */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {/* Readiness Card */}
          <div className="portal-card">
            <h3 className="portal-card-title" style={{ fontSize: '1.15rem', marginBottom: '14px' }}>
              🏨 Physical Room Readiness
            </h3>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 14px', borderRadius: '12px', background: 'rgba(7, 10, 18, 0.6)', border: '1px solid rgba(255, 255, 255, 0.06)' }}>
                <span style={{ color: '#34d399', fontWeight: 600, fontSize: '13px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#34d399' }} />
                  Clean & Available
                </span>
                <span style={{ fontFamily: 'monospace', fontWeight: 700, fontSize: '15px', color: '#ffffff' }}>
                  {availableRooms} Suites
                </span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 14px', borderRadius: '12px', background: 'rgba(7, 10, 18, 0.6)', border: '1px solid rgba(255, 255, 255, 0.06)' }}>
                <span style={{ color: '#38bdf8', fontWeight: 600, fontSize: '13px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#38bdf8' }} />
                  Currently Occupied
                </span>
                <span style={{ fontFamily: 'monospace', fontWeight: 700, fontSize: '15px', color: '#ffffff' }}>
                  {occupiedRooms} Suites
                </span>
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 14px', borderRadius: '12px', background: 'rgba(7, 10, 18, 0.6)', border: '1px solid rgba(255, 255, 255, 0.06)' }}>
                <span style={{ color: '#fbbf24', fontWeight: 600, fontSize: '13px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#fbbf24' }} />
                  Maintenance / Service
                </span>
                <span style={{ fontFamily: 'monospace', fontWeight: 700, fontSize: '15px', color: '#ffffff' }}>
                  {maintenanceRooms} Suites
                </span>
              </div>
            </div>

            <button
              onClick={() => onNavigateTab('rooms')}
              className="portal-btn-secondary"
              style={{ width: '100%', marginTop: '16px', justifyContent: 'center' }}
            >
              <span>🛏️</span>
              <span>Open Physical Room Grid</span>
            </button>
          </div>

          {/* AI Concierge Card */}
          <div className="portal-card">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
              <h3 className="portal-card-title" style={{ fontSize: '1.15rem' }}>
                🤖 AI Concierge RAG
              </h3>
              <span className="portal-badge portal-badge-purple">
                FastEmbed
              </span>
            </div>
            <p style={{ fontSize: '12px', color: '#94a3b8', lineHeight: 1.5, margin: '0 0 16px' }}>
              Real-time vector synchronization embeds hotel cancellation policies, suite rates, and custom manuals.
            </p>
            <button
              onClick={() => onNavigateTab('knowledge')}
              className="portal-btn-secondary"
              style={{ width: '100%', justifyContent: 'center', color: '#c084fc', borderColor: 'rgba(168, 85, 247, 0.3)' }}
            >
              <span>⚡</span>
              <span>Manage RAG Knowledge</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
