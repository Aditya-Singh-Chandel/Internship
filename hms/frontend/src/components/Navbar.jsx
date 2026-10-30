import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';

export default function Navbar({ onOpenAuth, onOpenMyTrips, onOpenConcierge, onOpenPortal }) {
  const { user, isAuthenticated, logout } = useAuth();
  const [dropdownOpen, setDropdownOpen] = useState(false);

  const rawRole = (typeof user?.role === 'object' ? user?.role?.name : user?.role) || '';
  const role = rawRole.toLowerCase();
  const hasOperationsAccess = ['admin', 'owner', 'manager', 'receptionist', 'staff'].includes(role);

  const getPortalInfo = () => {
    switch(role) {
      case 'admin':
        return { label: 'Admin Operations', icon: '👑', color: '#ef4444', bg: 'rgba(239, 68, 68, 0.12)' };
      case 'owner':
        return { label: 'Owner Portal', icon: '🏢', color: '#a855f7', bg: 'rgba(168, 85, 247, 0.12)' };
      case 'manager':
        return { label: 'Manager Hub', icon: '👔', color: '#0ea5e9', bg: 'rgba(14, 165, 233, 0.12)' };
      case 'receptionist':
      case 'staff':
      default:
        return { label: 'Staff Front Desk', icon: '🛎️', color: '#10b981', bg: 'rgba(16, 185, 129, 0.12)' };
    }
  };

  const portalInfo = getPortalInfo();

  return (
    <header className="navbar-header">
      <div className="max-width-wrapper navbar-inner">
        {/* Brand Emblem */}
        <div 
          className="brand-emblem" 
          onClick={() => {
            if (window.lenis) {
              window.lenis.scrollTo(0, { duration: 1.2 });
            } else {
              window.scrollTo({ top: 0, behavior: 'smooth' });
            }
          }}
        >
          <div className="brand-icon">⚜</div>
          <div className="brand-text-wrap">
            <span className="brand-title">GrandStay</span>
            <span className="brand-subtitle">Hotels & Resorts</span>
          </div>
        </div>

        {/* Navigation Links */}
        <nav className="nav-links">
          <a 
            href="#destinations" 
            className="nav-link-item active"
            onClick={(e) => {
              e.preventDefault();
              if (window.lenis) {
                window.lenis.scrollTo('#destinations', { offset: -20, duration: 1.4 });
              } else {
                const el = document.getElementById('destinations');
                if (el) el.scrollIntoView({ behavior: 'smooth' });
              }
            }}
          >
            Explore Properties
          </a>
          <button 
            type="button" 
            className="nav-link-item" 
            onClick={onOpenConcierge}
          >
            AI Concierge ✦
          </button>
          {isAuthenticated && (
            <button 
              type="button" 
              className="nav-link-item" 
              onClick={onOpenMyTrips}
            >
              My Reservations
            </button>
          )}
          {hasOperationsAccess && (
            <button 
              type="button" 
              className="nav-link-item" 
              style={{ color: portalInfo.color, fontWeight: 600 }}
              onClick={onOpenPortal}
            >
              {portalInfo.icon} {portalInfo.label}
            </button>
          )}
        </nav>

        {/* Action Controls */}
        <div className="nav-actions">
          {hasOperationsAccess && (
            <button 
              type="button"
              onClick={onOpenPortal}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '6px',
                padding: '7px 14px',
                borderRadius: '9999px',
                fontSize: '12px',
                fontWeight: 600,
                color: portalInfo.color,
                background: portalInfo.bg,
                border: `1px solid ${portalInfo.color}30`,
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                boxShadow: '0 2px 6px rgba(0,0,0,0.06)'
              }}
              title="Launch Operations Management Hub"
            >
              <span>{portalInfo.icon}</span>
              <span>{portalInfo.label}</span>
            </button>
          )}

          <button 
            type="button"
            className="btn-concierge-pill" 
            onClick={onOpenConcierge}
          >
            <span>Ask Concierge</span>
            <span style={{ color: 'var(--gold-400)', fontSize: '11px' }}>AI</span>
          </button>

          {isAuthenticated ? (
            <div style={{ position: 'relative' }}>
              <div 
                className="user-menu-trigger" 
                onClick={() => setDropdownOpen(!dropdownOpen)}
              >
                <div className="user-avatar-circle">
                  {(user?.name || user?.email || "G")[0].toUpperCase()}
                </div>
                <span className="user-name-label">
                  {user?.name ? user.name.split(' ')[0] : 'Guest'}
                </span>
                <span style={{ fontSize: '11px', color: '#94a3b8' }}>▼</span>
              </div>

              {dropdownOpen && (
                <div style={{
                  position: 'absolute',
                  top: '115%',
                  right: 0,
                  width: '220px',
                  background: '#ffffff',
                  borderRadius: 'var(--radius-md)',
                  boxShadow: 'var(--shadow-xl)',
                  border: '1px solid var(--surface-border)',
                  padding: '8px',
                  zIndex: 110,
                  animation: 'slideUp 150ms ease-out'
                }}>
                  <div style={{ padding: '8px 12px', borderBottom: '1px solid #f1f5f9', marginBottom: '6px' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div style={{ fontSize: '13px', fontWeight: 600, color: 'var(--navy-950)' }}>
                        {user?.name || 'Customer'}
                      </div>
                      <span style={{
                        background: 'var(--gold-100)',
                        color: 'var(--gold-800)',
                        fontSize: '9px',
                        fontWeight: 700,
                        padding: '2px 6px',
                        borderRadius: '4px',
                        textTransform: 'uppercase'
                      }}>
                        {typeof user?.role === 'object' ? user?.role?.name : (user?.role || 'customer')}
                      </span>
                    </div>
                    <div style={{ fontSize: '11px', color: '#64748b', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {user?.email}
                    </div>
                  </div>

                  {hasOperationsAccess && (
                    <button
                      type="button"
                      style={{
                        width: '100%',
                        textAlign: 'left',
                        padding: '8px 12px',
                        fontSize: '13px',
                        fontWeight: 600,
                        color: portalInfo.color,
                        background: portalInfo.bg,
                        borderRadius: 'var(--radius-sm)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px',
                        marginBottom: '4px'
                      }}
                      onClick={() => { setDropdownOpen(false); onOpenPortal(); }}
                    >
                      <span>{portalInfo.icon}</span> {portalInfo.label}
                    </button>
                  )}

                  <button
                    type="button"
                    style={{
                      width: '100%',
                      textAlign: 'left',
                      padding: '8px 12px',
                      fontSize: '13px',
                      fontWeight: 500,
                      color: 'var(--navy-900)',
                      borderRadius: 'var(--radius-sm)',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px'
                    }}
                    onClick={() => { setDropdownOpen(false); onOpenMyTrips(); }}
                  >
                    <span>🧳</span> My Trips & Bookings
                  </button>
                  <button
                    type="button"
                    style={{
                      width: '100%',
                      textAlign: 'left',
                      padding: '8px 12px',
                      fontSize: '13px',
                      fontWeight: 500,
                      color: '#dc2626',
                      borderRadius: 'var(--radius-sm)',
                      display: 'flex',
                      alignItems: 'center',
                      gap: '8px',
                      marginTop: '4px'
                    }}
                    onClick={() => { setDropdownOpen(false); logout(); }}
                  >
                    <span>🚪</span> Sign Out
                  </button>
                </div>
              )}
            </div>
          ) : (
            <button 
              type="button"
              className="btn-primary" 
              onClick={onOpenAuth}
            >
              Sign In / Register
            </button>
          )}
        </div>
      </div>
    </header>
  );
}
