import React, { useState, useEffect, useRef } from "react";
import { useAuth } from "../../context/AuthContext";
import { api } from "../../services/api";

import PortalHeader from "./PortalHeader";
import PortalSidebar from "./PortalSidebar";
import PortalOverview from "./PortalOverview";
import PortalFrontDesk from "./PortalFrontDesk";
import PortalRooms from "./PortalRooms";
import PortalRoomTypes from "./PortalRoomTypes";
import PortalPolicies from "./PortalPolicies";
import PortalKnowledge from "./PortalKnowledge";
import PortalMedia from "./PortalMedia";
import PortalStaff from "./PortalStaff";
import PortalHotels from "./PortalHotels";
import "./portal.css";

export default function OperationsPortal({ onExit }) {
  const { user, token } = useAuth();

  // If user signed out or token is cleared, immediately exit to landing page
  useEffect(() => {
    if (!user || !token) {
      onExit?.();
    }
  }, [user, token, onExit]);

  if (!user || !token) {
    return null;
  }

  const rawRole = (typeof user?.role === "object" ? user?.role?.name : user?.role) || "";
  const role = rawRole.toLowerCase();

  const [activeTab, setActiveTab] = useState("overview");
  const [hotels, setHotels] = useState([]);
  const [activeHotel, setActiveHotel] = useState(null);

  // Scoped Data State
  const [rooms, setRooms] = useState([]);
  const [roomTypes, setRoomTypes] = useState([]);
  const [policies, setPolicies] = useState([]);
  const [bookings, setBookings] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  // Ref to the scrollable main content area
  const mainScrollRef = useRef(null);

  // Global Portal Toast Notifications
  const [toasts, setToasts] = useState([]);
  const addToast = (type, message) => {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, type, message }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  };

  // Reset scroll position on mount and whenever activeTab changes
  useEffect(() => {
    window.scrollTo(0, 0);
    if (mainScrollRef.current) {
      mainScrollRef.current.scrollTo({ top: 0, behavior: "instant" });
    }
  }, [activeTab]);

  // 1. Initial Load: Fetch Hotels list scoped strictly by role
  useEffect(() => {
    const loadInitialHotels = async () => {
      setIsLoading(true);
      try {
        const hotelList = await api.getHotels();
        let accessibleHotels = [];

        if (role === "admin") {
          accessibleHotels = hotelList || [];
        } else if (role === "owner") {
          accessibleHotels = (hotelList || []).filter(
            (h) => h.owner_id === user?.id || (user?.owned_hotel_ids && user.owned_hotel_ids.includes(h.id))
          );
        } else if (["manager", "receptionist", "staff"].includes(role)) {
          if (user?.hotel_id) {
            const myHotel = (hotelList || []).find((h) => h.id === user.hotel_id);
            accessibleHotels = myHotel ? [myHotel] : [];
          } else {
            accessibleHotels = [];
          }
        }

        setHotels(accessibleHotels);
        if (accessibleHotels.length > 0) {
          setActiveHotel(accessibleHotels[0]);
        } else {
          setActiveHotel(null);
        }
      } catch (err) {
        console.error("Failed to load hotels in Operations Hub", err);
        addToast("error", "Failed to retrieve hotel list.");
      } finally {
        setIsLoading(false);
      }
    };

    loadInitialHotels();
  }, [user?.hotel_id, user?.id, role]);

  // 2. Fetch Scoped Data whenever activeHotel changes
  const fetchScopedData = async () => {
    if (!activeHotel?.id) return;
    setIsLoading(true);

    try {
      const [roomsData, roomTypesData, policiesData, bookingsData] = await Promise.all([
        api.getRooms({ hotel_id: activeHotel.id, limit: 100 }, token).catch(() => []),
        api.getRoomTypes(activeHotel.id).catch(() => []),
        api.getPolicies(activeHotel.id).catch(() => []),
        api.getAllBookings({ hotel_id: activeHotel.id, limit: 100 }, token).catch(() => [])
      ]);

      setRooms(roomsData || []);
      setRoomTypes(roomTypesData || []);
      setPolicies(policiesData || []);
      setBookings(bookingsData || []);
    } catch (err) {
      console.error("Error loading hotel operational data", err);
      addToast("error", "Error loading hotel operational data.");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchScopedData();
    if (mainScrollRef.current) {
      mainScrollRef.current.scrollTo({ top: 0, behavior: "instant" });
    }
  }, [activeHotel?.id, token]);

  const handleSelectHotel = (hotelOrId) => {
    const hotel = typeof hotelOrId === "object" ? hotelOrId : hotels.find((h) => h.id === hotelOrId);
    if (hotel) {
      setActiveHotel(hotel);
      addToast("info", `Switched active operations to ${hotel.name}`);
    }
  };

  const handleTabChange = (tabId) => {
    setActiveTab(tabId);
    if (mainScrollRef.current) {
      mainScrollRef.current.scrollTo({ top: 0, behavior: "instant" });
    }
  };

  return (
    <div className="portal-shell" data-lenis-prevent>
      {/* Fixed Sticky Header */}
      <PortalHeader
        hotels={hotels}
        activeHotelId={activeHotel?.id}
        onSelectHotel={handleSelectHotel}
        onExitPortal={onExit}
      />

      {/* Main Body with Fixed Sidebar + Scrollable Content */}
      <div className="portal-body" data-lenis-prevent>
        {/* Role-Filtered Sidebar */}
        <PortalSidebar activeTab={activeTab} onSelectTab={handleTabChange} />

        {/* Dynamic Workspace Container */}
        <main
          ref={mainScrollRef}
          className="portal-content"
          data-lenis-prevent
        >
          {!activeHotel && !isLoading ? (
            <div className="portal-container" style={{ padding: "40px 20px" }}>
              <div
                style={{
                  background: "linear-gradient(135deg, rgba(239, 68, 68, 0.08) 0%, rgba(15, 23, 42, 0.6) 100%)",
                  border: "1px solid rgba(239, 68, 68, 0.3)",
                  borderRadius: 16,
                  padding: "48px 32px",
                  textAlign: "center",
                  maxWidth: 640,
                  margin: "60px auto"
                }}
              >
                <div style={{ fontSize: 52, marginBottom: 16 }}>🔒</div>
                <h2 style={{ fontFamily: "var(--font-serif)", fontSize: "1.6rem", color: "#fca5a5", marginBottom: 10 }}>
                  No Workplace Property Assigned
                </h2>
                <p style={{ color: "#cbd5e1", fontSize: "14px", lineHeight: 1.6, marginBottom: 20 }}>
                  Your account <strong>{user?.name}</strong> is currently not assigned to any luxury hotel property. 
                  Access to physical rooms, live bookings, operational policies, and staff rosters is strictly restricted to assigned properties.
                </p>
                <p style={{ color: "#94a3b8", fontSize: "12px", marginBottom: 24 }}>
                  Please contact a System Administrator or Property Owner to link your account to a hotel before accessing the Operations Hub.
                </p>
                <button
                  type="button"
                  onClick={onExit}
                  className="portal-btn-secondary"
                  style={{ borderColor: "rgba(239, 68, 68, 0.4)", color: "#fca5a5" }}
                >
                  Return to Guest Website
                </button>
              </div>
            </div>
          ) : isLoading && !rooms.length && !bookings.length ? (
            <div style={{ height: '360px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', color: '#94a3b8', gap: '12px' }}>
              <div style={{ width: '40px', height: '40px', border: '3px solid #dfc471', borderTopColor: 'transparent', borderRadius: '50%', animation: 'spin 0.8s linear infinite' }} />
              <div style={{ fontFamily: 'var(--font-serif)', fontSize: '1.2rem', color: '#ffffff', letterSpacing: '0.04em' }}>
                Synchronizing Property Operations...
              </div>
              <div style={{ fontSize: '12px', color: '#64748b' }}>
                Retrieving physical rooms, live bookings, policies, and suite inventory
              </div>
            </div>
          ) : (
            <div className="portal-container">
              {activeTab === "overview" && (
                <PortalOverview
                  hotel={activeHotel}
                  rooms={rooms}
                  bookings={bookings}
                  onNavigateTab={handleTabChange}
                />
              )}

              {activeTab === "frontdesk" && (
                <PortalFrontDesk
                  hotel={activeHotel}
                  bookings={bookings}
                  rooms={rooms}
                  roomTypes={roomTypes}
                  onRefreshData={fetchScopedData}
                  addToast={addToast}
                />
              )}

              {activeTab === "rooms" && (
                <PortalRooms
                  hotel={activeHotel}
                  rooms={rooms}
                  roomTypes={roomTypes}
                  onRefreshData={fetchScopedData}
                  addToast={addToast}
                />
              )}

              {activeTab === "roomtypes" && (
                <PortalRoomTypes
                  activeHotel={activeHotel}
                  roomTypes={roomTypes}
                  rooms={rooms}
                  token={token}
                  userRole={role}
                  onRefresh={fetchScopedData}
                />
              )}

              {activeTab === "policies" && (
                <PortalPolicies
                  activeHotel={activeHotel}
                  policies={policies}
                  token={token}
                  userRole={role}
                  onRefresh={fetchScopedData}
                  onNavigateTab={handleTabChange}
                />
              )}

              {activeTab === "knowledge" && (
                <PortalKnowledge
                  activeHotel={activeHotel}
                  token={token}
                  userRole={role}
                />
              )}

              {activeTab === "media" && (
                <PortalMedia
                  activeHotel={activeHotel}
                  roomTypes={roomTypes}
                  token={token}
                  userRole={role}
                />
              )}

              {activeTab === "staff" && (
                <PortalStaff
                  activeHotel={activeHotel}
                  hotels={hotels}
                  token={token}
                  userRole={role}
                  currentUserId={user?.id}
                />
              )}

              {activeTab === "hotels" && (
                <PortalHotels
                  hotels={hotels}
                  activeHotel={activeHotel}
                  onSelectHotel={handleSelectHotel}
                  token={token}
                  userRole={role}
                  onRefresh={async () => {
                    const hotelList = await api.getHotels();
                    setHotels(hotelList || []);
                  }}
                />
              )}
            </div>
          )}
        </main>
      </div>

      {/* Floating Toast Notification Stack */}
      <div className="fixed bottom-5 right-5 z-50 flex flex-col gap-2 pointer-events-none">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`px-4 py-3 rounded-xl shadow-2xl backdrop-blur-md border text-xs font-medium flex items-center gap-2 pointer-events-auto transform transition-all animate-bounce-in ${
              toast.type === "error"
                ? "bg-rose-950/90 text-rose-200 border-rose-500/40"
                : toast.type === "info"
                ? "bg-blue-950/90 text-blue-200 border-blue-500/40"
                : "bg-emerald-950/90 text-emerald-200 border-emerald-500/40"
            }`}
          >
            <span>
              {toast.type === "error" ? "❌" : toast.type === "info" ? "ℹ️" : "✓"}
            </span>
            <span>{toast.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
