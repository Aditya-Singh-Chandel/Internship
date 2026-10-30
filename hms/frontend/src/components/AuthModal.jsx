import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';

export default function AuthModal({ isOpen, onClose, onSuccess, initialNotice }) {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const { login, register } = useAuth();

  if (!isOpen) return null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);

    try {
      let loggedUser = null;
      if (isRegister) {
        if (!name.trim()) throw new Error("Please enter your full name.");
        await register(name, email, password, phone);
      } else {
        loggedUser = await login(email, password);
      }
      onSuccess?.(loggedUser);
      onClose();
    } catch (err) {
      setError(err.message || "Authentication failed. Please verify your credentials.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay" data-lenis-prevent onClick={onClose}>
      <div className="modal-card" data-lenis-prevent style={{ maxWidth: '440px' }} onClick={(e) => e.stopPropagation()}>
        <button type="button" className="modal-close-btn" onClick={onClose}>✕</button>

        <div style={{ padding: '36px 32px 32px' }}>
          {/* Header */}
          <div style={{ textAlign: 'center', marginBottom: '24px' }}>
            <div style={{
              width: '44px',
              height: '44px',
              margin: '0 auto 12px',
              borderRadius: 'var(--radius-md)',
              background: 'linear-gradient(135deg, var(--gold-400), var(--gold-600))',
              color: '#fff',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '22px'
            }}>
              ⚜
            </div>
            <h2 style={{ fontSize: '1.6rem', color: 'var(--navy-950)', marginBottom: '6px' }}>
              {isRegister ? "Join GrandStay" : "Welcome Back"}
            </h2>
            <p style={{ fontSize: '0.88rem' }}>
              {isRegister 
                ? "Create your guest account to reserve luxury suites and unlock concierge benefits." 
                : "Sign in to manage reservations, check stay vouchers, and book."}
            </p>
          </div>

          {/* Booking Guard Notice Banner */}
          {initialNotice && (
            <div style={{
              background: 'var(--gold-50)',
              border: '1px solid var(--gold-300)',
              borderRadius: 'var(--radius-md)',
              padding: '12px 14px',
              marginBottom: '20px',
              fontSize: '0.82rem',
              color: 'var(--gold-800)',
              display: 'flex',
              alignItems: 'center',
              gap: '8px'
            }}>
              <span>🔒</span>
              <span>{initialNotice}</span>
            </div>
          )}

          {/* Mode Switcher Tabs */}
          <div style={{
            display: 'flex',
            background: 'var(--cream-100)',
            borderRadius: 'var(--radius-full)',
            padding: '4px',
            marginBottom: '22px'
          }}>
            <button
              type="button"
              style={{
                flex: 1,
                padding: '8px 12px',
                borderRadius: 'var(--radius-full)',
                fontSize: '0.85rem',
                fontWeight: 600,
                background: !isRegister ? '#ffffff' : 'transparent',
                color: !isRegister ? 'var(--navy-950)' : 'var(--text-muted)',
                boxShadow: !isRegister ? 'var(--shadow-xs)' : 'none',
                transition: 'all var(--transition-fast)'
              }}
              onClick={() => { setIsRegister(false); setError(''); }}
            >
              Sign In
            </button>
            <button
              type="button"
              style={{
                flex: 1,
                padding: '8px 12px',
                borderRadius: 'var(--radius-full)',
                fontSize: '0.85rem',
                fontWeight: 600,
                background: isRegister ? '#ffffff' : 'transparent',
                color: isRegister ? 'var(--navy-950)' : 'var(--text-muted)',
                boxShadow: isRegister ? 'var(--shadow-xs)' : 'none',
                transition: 'all var(--transition-fast)'
              }}
              onClick={() => { setIsRegister(true); setError(''); }}
            >
              Create Account
            </button>
          </div>

          {/* Error Message */}
          {error && (
            <div style={{
              background: 'var(--error-bg)',
              color: 'var(--error)',
              padding: '10px 14px',
              borderRadius: 'var(--radius-md)',
              fontSize: '0.84rem',
              marginBottom: '16px',
              border: '1px solid #fecaca'
            }}>
              ⚠️ {error}
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
            {isRegister && (
              <>
                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: '5px' }}>
                    Full Name *
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Eleanor Vance"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '10px 14px',
                      borderRadius: 'var(--radius-md)',
                      border: '1px solid var(--surface-border)',
                      fontSize: '0.9rem',
                      outline: 'none'
                    }}
                  />
                </div>
                <div>
                  <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: '5px' }}>
                    Mobile Phone (Optional)
                  </label>
                  <input
                    type="tel"
                    placeholder="+1 (305) 555-0199"
                    value={phone}
                    onChange={(e) => setPhone(e.target.value)}
                    style={{
                      width: '100%',
                      padding: '10px 14px',
                      borderRadius: 'var(--radius-md)',
                      border: '1px solid var(--surface-border)',
                      fontSize: '0.9rem',
                      outline: 'none'
                    }}
                  />
                </div>
              </>
            )}

            {!isRegister && (
              <div style={{
                background: '#f8fafc',
                border: '1px solid #e2e8f0',
                borderRadius: 'var(--radius-md)',
                padding: '10px 12px',
                marginBottom: '4px'
              }}>
                <div style={{ fontSize: '11px', fontWeight: 600, color: '#64748b', marginBottom: '8px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Quick Fill Demo Roles
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                  {[
                    { label: '👑 Admin', email: 'admin@hms.com', pass: 'Admin@123', color: '#ef4444' },
                    { label: '🏢 Owner', email: 'owner@hms.com', pass: 'Owner@123', color: '#a855f7' },
                    { label: '👔 Manager', email: 'manager@hms.com', pass: 'Manager@123', color: '#0ea5e9' },
                    { label: '🛎️ Front Desk', email: 'staff@hms.com', pass: 'Staff@123', color: '#10b981' },
                    { label: '👤 Guest', email: 'marcus.vance@techcorp.io', pass: 'Customer@123', color: '#64748b' }
                  ].map((demo) => (
                    <button
                      key={demo.email}
                      type="button"
                      onClick={() => {
                        setEmail(demo.email);
                        setPassword(demo.pass);
                        setError('');
                      }}
                      style={{
                        padding: '4px 8px',
                        borderRadius: '6px',
                        background: '#ffffff',
                        border: '1px solid #cbd5e1',
                        fontSize: '11px',
                        fontWeight: 600,
                        color: demo.color,
                        cursor: 'pointer',
                        transition: 'all 0.15s'
                      }}
                    >
                      {demo.label}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: '5px' }}>
                Email Address *
              </label>
              <input
                type="email"
                required
                placeholder="guest@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--surface-border)',
                  fontSize: '0.9rem',
                  outline: 'none'
                }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.75rem', fontWeight: 700, textTransform: 'uppercase', color: 'var(--text-secondary)', marginBottom: '5px' }}>
                Password *
              </label>
              <input
                type="password"
                required
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--surface-border)',
                  fontSize: '0.9rem',
                  outline: 'none'
                }}
              />
            </div>

            <button
              type="submit"
              disabled={submitting}
              className="btn-primary"
              style={{
                width: '100%',
                padding: '12px',
                fontSize: '0.92rem',
                marginTop: '10px',
                opacity: submitting ? 0.7 : 1
              }}
            >
              {submitting ? "Processing..." : isRegister ? "Create Customer Account" : "Sign In to Account"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
