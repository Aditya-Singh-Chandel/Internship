import React from 'react';
import { useAuth } from '../../context/AuthContext';

export default function PortalHeader({ 
  hotels = [], 
  activeHotelId, 
  onSelectHotel, 
  onExitPortal 
}) {
  const { user, logout } = useAuth();
  const rawRole = (typeof user?.role === 'object' ? user?.role?.name : user?.role) || '';
  const role = rawRole.toLowerCase();

  const activeHotel = hotels.find(h => h.id === activeHotelId) || (hotels.length > 0 ? hotels[0] : null);
  const canSwitchHotels = (role === 'admin' || role === 'owner') && hotels.length > 0;

  const handleSignOut = () => {
    logout();
    if (onExitPortal) {
      onExitPortal();
    }
  };

  const getRoleBadge = () => {
    switch(role) {
      case 'admin':
        return { label: 'System Admin', icon: '👑', badgeClass: 'portal-badge-red' };
      case 'owner':
        return { label: 'Property Owner', icon: '🏢', badgeClass: 'portal-badge-purple' };
      case 'manager':
        return { label: 'General Manager', icon: '👔', badgeClass: 'portal-badge-blue' };
      case 'receptionist':
      case 'staff':
        return { label: 'Front Desk Staff', icon: '🛎️', badgeClass: 'portal-badge-green' };
      default:
        return { label: 'Authorized Staff', icon: '🛎️', badgeClass: 'portal-badge-gray' };
    }
  };

  const badge = getRoleBadge();

  return (
    <header className="portal-header">
      {/* Left: Brand & Scope */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
        <div className="portal-brand-wrap" onClick={onExitPortal} title="Return to guest website">
          <div className="portal-brand-emblem">⚜</div>
          <div className="portal-brand-text">
            <h1>GrandStay</h1>
            <span>Operations Hub</span>
          </div>
        </div>

        <div className="portal-divider-v" />

        {/* Hotel Selector Scoping */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '11px', fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            Property:
          </span>

          {canSwitchHotels ? (
            <select
              value={activeHotelId || ''}
              onChange={(e) => {
                const target = hotels.find(h => h.id === e.target.value);
                if (target && onSelectHotel) {
                  onSelectHotel(target);
                }
              }}
              className="portal-scope-select"
            >
              {hotels.map(h => (
                <option key={h.id} value={h.id}>
                  🏨 {h.name} ({h.city})
                </option>
              ))}
            </select>
          ) : activeHotel ? (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 12px',
              background: 'rgba(255, 255, 255, 0.05)',
              borderRadius: '10px',
              border: '1px solid rgba(255, 255, 255, 0.1)',
              fontSize: '13px',
              fontWeight: 600,
              color: '#ffffff'
            }}>
              <span>📍</span>
              <span>{activeHotel.name}</span>
              <span style={{ fontSize: '11px', color: '#94a3b8' }}>({activeHotel.city})</span>
            </div>
          ) : (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '6px 12px',
              background: 'rgba(239, 68, 68, 0.15)',
              borderRadius: '10px',
              border: '1px solid rgba(239, 68, 68, 0.35)',
              fontSize: '12px',
              fontWeight: 600,
              color: '#fca5a5'
            }}>
              <span>⚠️</span>
              <span>No Property Assigned</span>
            </div>
          )}
        </div>
      </div>

      {/* Right: Role Badge, Guest Website Toggle, User & Logout */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        {/* Role Badge */}
        <div className={`portal-badge ${badge.badgeClass}`}>
          <span>{badge.icon}</span>
          <span>{badge.label}</span>
        </div>

        {/* Exit to Customer Website */}
        <button
          type="button"
          onClick={onExitPortal}
          className="portal-btn-secondary"
          title="Return to the public guest experience website"
        >
          <span>🌐</span>
          <span>Guest Experience</span>
        </button>

        {/* User Avatar & Logout */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', paddingLeft: '10px', borderLeft: '1px solid rgba(255, 255, 255, 0.1)' }}>
          <div style={{
            width: '34px',
            height: '34px',
            borderRadius: '50%',
            background: 'linear-gradient(135deg, #dfc471, #c59b27)',
            color: '#070a12',
            fontWeight: 700,
            fontSize: '13px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 2px 8px rgba(197, 155, 39, 0.3)'
          }}>
            {(user?.name || user?.email || "U")[0].toUpperCase()}
          </div>
          <div style={{ textAlign: 'left', lineHeight: 1.1 }}>
            <div style={{ fontSize: '13px', fontWeight: 600, color: '#ffffff' }}>
              {user?.name ? user.name.split(' ')[0] : (user?.email ? user.email.split('@')[0] : 'User')}
            </div>
            <button
              type="button"
              onClick={handleSignOut}
              style={{
                fontSize: '11px',
                color: '#f87171',
                background: 'none',
                border: 'none',
                padding: 0,
                cursor: 'pointer',
                fontWeight: 500
              }}
            >
              Sign Out
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}
