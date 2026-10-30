import React, { useState, useEffect } from 'react';
import { api } from './services/api';
import { useAuth } from './context/AuthContext';
import Navbar from './components/Navbar';
import HeroSearch from './components/HeroSearch';
import HotelCard from './components/HotelCard';
import HotelDetailModal from './components/HotelDetailModal';
import BookingModal from './components/BookingModal';
import MyTripsModal from './components/MyTripsModal';
import AuthModal from './components/AuthModal';
import ReviewModal from './components/ReviewModal';
import AIConcierge from './components/AIConcierge';
import Toast from './components/Toast';
import OperationsPortal from './components/portal/OperationsPortal';
import Lenis from 'lenis';
import 'lenis/dist/lenis.css';

export default function App() {
  const { isAuthenticated, user } = useAuth();

  // Portal State (Operations Hub for Admin, Owner, Manager, Staff)
  const [inPortal, setInPortal] = useState(false);

  // Hotel data & Search
  const [hotels, setHotels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [destination, setDestination] = useState('');
  const [cityFilter, setCityFilter] = useState('All');
  const [checkin, setCheckin] = useState(() => {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    return tomorrow.toISOString().split('T')[0];
  });
  const [checkout, setCheckout] = useState(() => {
    const end = new Date();
    end.setDate(end.getDate() + 4);
    return end.toISOString().split('T')[0];
  });
  const [guests, setGuests] = useState(2);

  // Modals & Active Selections
  const [activeHotel, setActiveHotel] = useState(null);
  const [bookingTarget, setBookingTarget] = useState(null); // { hotel, roomType }
  const [pendingBookingAfterAuth, setPendingBookingAfterAuth] = useState(null);
  const [authOpen, setAuthOpen] = useState(false);
  const [authNotice, setAuthNotice] = useState('');
  const [myTripsOpen, setMyTripsOpen] = useState(false);
  const [tripsRefreshKey, setTripsRefreshKey] = useState(0);
  const [reviewTarget, setReviewTarget] = useState(null); // { booking, hotel, existingReview }
  const [conciergeOpen, setConciergeOpen] = useState(false);
  const [conciergeScopedHotel, setConciergeScopedHotel] = useState(null);

  // Toast System
  const [toasts, setToasts] = useState([]);

  const isAnyModalOpen = Boolean(activeHotel || bookingTarget || authOpen || myTripsOpen || reviewTarget);

  // Manage Lenis smooth scroll: active ONLY on the guest marketing site, completely unmounted in Operations Hub
  useEffect(() => {
    if (inPortal) {
      if (window.lenis) {
        window.lenis.destroy();
        delete window.lenis;
      }
      window.scrollTo(0, 0);
      document.body.style.overflow = "hidden";
      return;
    }

    // Guest website: initialize Lenis with comprehensive modal prevention
    document.body.style.overflow = isAnyModalOpen ? "hidden" : "auto";
    const lenis = new Lenis({
      duration: 1.1,
      easing: (t) => Math.min(1, 1.001 - Math.pow(2, -10 * t)),
      orientation: 'vertical',
      gestureOrientation: 'vertical',
      smoothWheel: true,
      wheelMultiplier: 1.0,
      prevent: (node) => {
        return Boolean(
          node?.nodeType === 1 && (
            node.hasAttribute('data-lenis-prevent') ||
            node.closest?.('.modal-overlay, .modal-card, [data-lenis-prevent], .portal-shell, .portal-body, .portal-content, .concierge-drawer, .portal-modal-backdrop, .portal-modal-box')
          )
        );
      }
    });

    window.lenis = lenis;

    let rafId;
    function raf(time) {
      lenis.raf(time);
      rafId = requestAnimationFrame(raf);
    }
    rafId = requestAnimationFrame(raf);

    return () => {
      cancelAnimationFrame(rafId);
      lenis.destroy();
      delete window.lenis;
    };
  }, [inPortal, isAnyModalOpen]);

  // Lock body scroll whenever any guest modal is open
  useEffect(() => {
    if (!inPortal) {
      document.body.style.overflow = isAnyModalOpen ? "hidden" : "auto";
    }
  }, [isAnyModalOpen, inPortal]);

  const addToast = (message) => {
    const id = Date.now();
    setToasts(prev => [...prev, { id, message }]);
    setTimeout(() => {
      setToasts(prev => prev.filter(t => t.id !== id));
    }, 4000);
  };

  // Fetch initial hotels, PostgreSQL media, real room types, and verified reviews
  useEffect(() => {
    setLoading(true);
    Promise.all([
      api.getHotels(50).catch(() => []),
      api.getAllMedia().catch(() => []),
      api.getRoomTypes().catch(() => []),
      api.getReviews().catch(() => [])
    ])
      .then(([hotelsData, allMedia, allRoomTypes, allReviews]) => {
        // Pure dynamic data enrichment from PostgreSQL tables
        const enriched = (hotelsData || []).map(h => {
          const hotelMedia = (allMedia || []).filter(m => m.hotel_id === h.id);
          const primary = hotelMedia.find(m => !m.room_type_id && m.is_primary);
          const gallery = hotelMedia.filter(m => !m.room_type_id && !m.is_primary).map(m => m.image_url);
          const heroUrl = primary ? primary.image_url : (hotelMedia[0]?.image_url || null);

          // Real room types & minPrice
          const hRooms = (allRoomTypes || []).filter(rt => rt.hotel_id === h.id);
          const prices = hRooms
            .map(rt => parseFloat(rt.base_price))
            .filter(p => !isNaN(p) && p > 0);
          const minPrice = prices.length > 0 ? Math.min(...prices) : null;

          // Real reviews & average rating
          const hReviews = (allReviews || []).filter(r => r.hotel_id === h.id && (r.comment || "").length > 2);
          const ratings = hReviews.map(r => r.rating).filter(r => typeof r === 'number' && r > 0);
          const averageRating = ratings.length > 0
            ? (ratings.reduce((acc, curr) => acc + curr, 0) / ratings.length).toFixed(1)
            : null;
          const reviewCount = hReviews.length;

          return {
            ...h,
            media: hotelMedia,
            heroImage: heroUrl,
            gallery: gallery.length > 0 ? gallery : (heroUrl ? [heroUrl] : []),
            room_types: hRooms,
            minPrice,
            averageRating,
            reviewCount
          };
        });
        setHotels(enriched);
        setLoading(false);
      })
      .catch(err => {
        console.error("Failed to load hotels:", err);
        setLoading(false);
      });
  }, []);


  // Filter hotels based on destination search, guest capacity, and filter pills
  const filteredHotels = hotels.filter(h => {
    // Destination direct search box filter (Global by default)
    if (destination.trim()) {
      const q = destination.toLowerCase().trim();
      const haystack = `${h.name} ${h.city} ${h.state || ''} ${h.country || ''} ${h.description || ''}`.toLowerCase();
      if (!haystack.includes(q)) {
        return false;
      }
    }

    // Pill filter
    if (cityFilter !== 'All' && cityFilter !== 'All (Global)') {
      const pillQuery = cityFilter.toLowerCase();
      if (!(h.city || '').toLowerCase().includes(pillQuery)) {
        return false;
      }
    }

    // Guest capacity filter: ensure hotel has at least one published suite that accommodates requested guest count
    if (guests && guests > 1) {
      const hasAccommodatingSuite = (h.room_types || []).some(rt => (rt.guests_allowed || 2) >= guests);
      if (!hasAccommodatingSuite) {
        return false;
      }
    }

    return true;
  });

  // Dynamic distinct cities for filter pills from actual database
  const distinctCities = Array.from(new Set(hotels.map(h => h.city).filter(Boolean)));
  const cityPills = ['All (Global)', ...distinctCities];

  // Enforced Booking Guard: Users CANNOT book without login
  const handleInitiateBooking = (hotel, roomType) => {
    if (!isAuthenticated) {
      setPendingBookingAfterAuth({ hotel, roomType });
      setAuthNotice(`Please sign in or create a customer account to reserve ${roomType.name} at ${hotel.name}.`);
      setAuthOpen(true);
      return;
    }

    // User is logged in: proceed straight to checkout
    setActiveHotel(null); // close detail modal if open
    setBookingTarget({ hotel, roomType });
  };

  // Resume booking or enter operations portal when authentication succeeds
  const handleAuthSuccess = (loggedUser) => {
    const activeUser = loggedUser || user;
    const rawRole = (typeof activeUser?.role === 'object' ? activeUser?.role?.name : activeUser?.role) || '';
    const role = rawRole.toLowerCase();

    addToast(`✓ Signed in as ${activeUser?.name || 'User'} (${role.toUpperCase()})`);

    if (['admin', 'owner', 'manager', 'receptionist', 'staff'].includes(role) && !pendingBookingAfterAuth) {
      setInPortal(true);
    } else if (pendingBookingAfterAuth) {
      setBookingTarget(pendingBookingAfterAuth);
      setPendingBookingAfterAuth(null);
      setAuthNotice('');
    }
  };

  // Enforce Portal Guard: Only authenticated users with operational roles can be in the portal
  useEffect(() => {
    if (inPortal) {
      if (!isAuthenticated || !user) {
        setInPortal(false);
        return;
      }
      const rawRole = (typeof user?.role === 'object' ? user?.role?.name : user?.role) || '';
      const role = rawRole.toLowerCase();
      const hasPortalAccess = ['admin', 'owner', 'manager', 'receptionist', 'staff'].includes(role);
      if (!hasPortalAccess) {
        setInPortal(false);
      }
    }
  }, [inPortal, isAuthenticated, user]);

  // If in operations portal and authenticated as staff/management, render the Operations Portal workspace
  if (inPortal && isAuthenticated && user) {
    return <OperationsPortal onExit={() => setInPortal(false)} />;
  }

  return (
    <div className="app-container">
      {/* 1. Master Navbar */}
      <Navbar 
        onOpenAuth={() => { setAuthNotice(''); setAuthOpen(true); }}
        onOpenMyTrips={() => setMyTripsOpen(true)}
        onOpenConcierge={() => setConciergeOpen(true)}
        onOpenPortal={() => setInPortal(true)}
      />

      <main className="main-content">
        {/* 2. Hero Section & Search Bar */}
        <HeroSearch 
          destination={destination}
          setDestination={setDestination}
          checkin={checkin}
          setCheckin={setCheckin}
          checkout={checkout}
          setCheckout={setCheckout}
          guests={guests}
          setGuests={setGuests}
          hotels={hotels}
          onSearch={() => {
            if (window.lenis) {
              window.lenis.scrollTo('#destinations', { offset: -20, duration: 1.4 });
            } else {
              const el = document.getElementById('destinations');
              if (el) el.scrollIntoView({ behavior: 'smooth' });
            }
          }}
        />

        {/* 3. Catalog Section */}
        <section id="destinations" className="catalog-section max-width-wrapper">
          <div className="section-head-bar">
            <div>
              <span style={{ fontSize: '11px', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--gold-600)' }}>
                World-Class Portfolio
              </span>
              <h2 className="section-title">Explore Luxury Properties</h2>
              <p className="section-subtitle">
                {filteredHotels.length} {filteredHotels.length === 1 ? 'sanctuary' : 'sanctuaries'} available for your bespoke getaway.
              </p>
            </div>

            {/* City Filter Pills */}
            <div className="filter-pills-bar">
              {cityPills.map(city => {
                const isActive = (cityFilter === city) || (cityFilter === 'All' && city === 'All (Global)');
                return (
                  <button
                    key={city}
                    type="button"
                    className={`filter-pill ${isActive ? 'active' : ''}`}
                    onClick={() => setCityFilter(city === 'All (Global)' ? 'All' : city)}
                  >
                    {city}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Hotels Grid */}
          {loading ? (
            <div style={{ textAlign: 'center', padding: '80px', color: '#94a3b8' }}>
              <div style={{ fontSize: '32px', marginBottom: '12px' }}>⚜</div>
              <p>Curating luxury accommodations...</p>
            </div>
          ) : filteredHotels.length === 0 ? (
            <div style={{
              textAlign: 'center',
              padding: '60px',
              background: 'var(--surface-white)',
              borderRadius: 'var(--radius-lg)',
              border: '1px solid var(--surface-border)'
            }}>
              <h3 style={{ fontSize: '1.25rem', color: 'var(--navy-950)', marginBottom: '8px' }}>
                No luxury properties match your search
              </h3>
              <p style={{ color: 'var(--text-secondary)', marginBottom: '20px' }}>
                Try clearing your search query or selecting "All Destinations".
              </p>
              <button 
                type="button"
                className="btn-primary" 
                onClick={() => { setDestination(''); setCityFilter('All'); }}
              >
                Reset Filters
              </button>
            </div>
          ) : (
            <div className="hotels-grid">
              {filteredHotels.map(h => (
                <HotelCard 
                  key={h.id} 
                  hotel={h} 
                  onSelectHotel={(hotel) => setActiveHotel(hotel)} 
                />
              ))}
            </div>
          )}
        </section>

        {/* 4. Brand Highlight Banner */}
        <section style={{
          background: 'var(--cream-100)',
          borderTop: '1px solid var(--surface-border)',
          borderBottom: '1px solid var(--surface-border)',
          padding: '60px 24px',
          textAlign: 'center'
        }}>
          <div className="max-width-wrapper">
            <span style={{ fontSize: '11px', fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--gold-600)' }}>
              The GrandStay Standard
            </span>
            <h2 style={{ fontSize: '2rem', margin: '10px 0 16px', color: 'var(--navy-950)' }}>
              Hospitality Powered by Precision & Intelligence
            </h2>
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
              gap: '24px',
              marginTop: '40px'
            }}>
              <div style={{ background: '#fff', padding: '24px', borderRadius: 'var(--radius-lg)', boxShadow: 'var(--shadow-xs)' }}>
                <div style={{ fontSize: '28px', marginBottom: '8px' }}>🛎️</div>
                <h4 style={{ fontSize: '1.1rem', marginBottom: '6px' }}>White-Glove Concierge Care</h4>
                <p style={{ fontSize: '0.84rem' }}>Every suite includes dedicated private concierge assistance and personalized stay arrangements.</p>
              </div>
              <div style={{ background: '#fff', padding: '24px', borderRadius: 'var(--radius-lg)', boxShadow: 'var(--shadow-xs)' }}>
                <div style={{ fontSize: '28px', marginBottom: '8px' }}>✦</div>
                <h4 style={{ fontSize: '1.1rem', marginBottom: '6px' }}>AI Concierge Suite</h4>
                <p style={{ fontSize: '0.84rem' }}>Instant answers on dining menus, pool cabanas, quiet hours, and live refund policies.</p>
              </div>
              <div style={{ background: '#fff', padding: '24px', borderRadius: 'var(--radius-lg)', boxShadow: 'var(--shadow-xs)' }}>
                <div style={{ fontSize: '28px', marginBottom: '8px' }}>🛡️</div>
                <h4 style={{ fontSize: '1.1rem', marginBottom: '6px' }}>Transparent Refund Policies</h4>
                <p style={{ fontSize: '0.84rem' }}>Deterministic cancellation refunds clearly calculated prior to booking confirmation.</p>
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* Footer */}
      <footer style={{
        background: 'var(--navy-950)',
        color: '#ffffff',
        padding: '50px 24px',
        textAlign: 'center'
      }}>
        <div className="max-width-wrapper">
          <div style={{ fontSize: '24px', color: 'var(--gold-400)', marginBottom: '10px' }}>⚜</div>
          <div style={{ fontFamily: 'var(--font-serif)', fontSize: '1.4rem', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: '6px' }}>
            GrandStay Hotels & Resorts
          </div>
          <p style={{ color: 'rgba(255,255,255,0.6)', fontSize: '0.84rem', maxWidth: '500px', margin: '0 auto 24px' }}>
            Delivering sanctuary living across {distinctCities.length > 0 ? distinctCities.join(', ') : 'luxury destinations worldwide'}.
          </p>
          <div style={{ fontSize: '0.78rem', color: 'rgba(255,255,255,0.4)', borderTop: '1px solid rgba(255,255,255,0.1)', paddingTop: '20px' }}>
            © {new Date().getFullYear()} GrandStay HMS Inc. Customer Experience Portal.
          </div>
        </div>
      </footer>

      {/* ==========================================================================
          MODALS & OVERLAYS
          ========================================================================== */}

      {/* Hotel Detail Modal */}
      {activeHotel && (
        <HotelDetailModal 
          hotel={activeHotel}
          checkin={checkin}
          checkout={checkout}
          guests={guests}
          onClose={() => setActiveHotel(null)}
          onBookRoom={(hotel, roomType) => handleInitiateBooking(hotel, roomType)}
          onOpenConcierge={() => {
            setConciergeScopedHotel(activeHotel);
            setConciergeOpen(true);
          }}
        />
      )}

      {/* Booking Checkout Modal */}
      {bookingTarget && (
        <BookingModal 
          hotel={bookingTarget.hotel}
          roomType={bookingTarget.roomType}
          initialCheckin={checkin}
          initialCheckout={checkout}
          onClose={() => setBookingTarget(null)}
          onBookingSuccess={(bookingData) => {
            addToast("✓ Reservation confirmed! Booking voucher issued.");
          }}
        />
      )}

      {/* Customer Auth Modal (Sign In / Register) */}
      <AuthModal 
        isOpen={authOpen}
        initialNotice={authNotice}
        onClose={() => { setAuthOpen(false); setAuthNotice(''); }}
        onSuccess={handleAuthSuccess}
      />

      {/* "My Trips & Bookings" Modal */}
      <MyTripsModal 
        isOpen={myTripsOpen}
        hotels={hotels}
        refreshKey={tripsRefreshKey}
        onClose={() => setMyTripsOpen(false)}
        onOpenReview={(booking, hotel, existingReview = null) => {
          setReviewTarget({ booking, hotel, existingReview });
        }}
        onOpenConcierge={() => setConciergeOpen(true)}
      />

      {/* Review Modal */}
      {reviewTarget && (
        <ReviewModal 
            isOpen={Boolean(reviewTarget)}
            booking={reviewTarget.booking}
            hotel={reviewTarget.hotel}
            existingReview={reviewTarget.existingReview}
            onClose={() => setReviewTarget(null)}
            onReviewSubmitted={() => {
              setTripsRefreshKey(k => k + 1);
              addToast("✓ Review saved successfully! Thank you for your feedback.");
            }}
        />
      )}

      {/* Floating AI Concierge */}
      <AIConcierge 
        isOpen={conciergeOpen}
        onClose={() => setConciergeOpen(false)}
        onToggle={() => setConciergeOpen(prev => !prev)}
        hotels={hotels}
        scopedHotel={conciergeScopedHotel}
      />

      {/* Toast Notifications */}
      <Toast toasts={toasts} />
    </div>
  );
}
