import React, { createContext, useContext, useState, useEffect } from 'react';
import { api } from '../services/api';

const AuthContext = createContext(null);

const TOKEN_KEY = "grandstay_customer_token";
const USER_KEY = "grandstay_customer_user";

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY));
  const [user, setUser] = useState(() => {
    try {
      const saved = localStorage.getItem(USER_KEY);
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });
  const [loading, setLoading] = useState(false);

  // Sync access token changes to localStorage
  useEffect(() => {
    if (token) {
      localStorage.setItem(TOKEN_KEY, token);
    } else {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
      setUser(null);
    }
  }, [token]);

  // Listen to background token rotation and logout events from apiFetch
  useEffect(() => {
    const handleTokenRefreshed = (e) => {
      if (e.detail?.token) {
        setToken(e.detail.token);
      }
    };

    const handleAuthLogout = () => {
      setToken(null);
      setUser(null);
    };

    window.addEventListener("grandstay_token_refreshed", handleTokenRefreshed);
    window.addEventListener("grandstay_auth_logout", handleAuthLogout);
    return () => {
      window.removeEventListener("grandstay_token_refreshed", handleTokenRefreshed);
      window.removeEventListener("grandstay_auth_logout", handleAuthLogout);
    };
  }, []);

  // Validate session on load: verify active user profile or rotate refresh token via HttpOnly cookie
  useEffect(() => {
    const activeToken = token || localStorage.getItem(TOKEN_KEY);

    if (activeToken) {
      api.getCurrentUser(activeToken)
        .then(userData => {
          setUser(userData);
          localStorage.setItem(USER_KEY, JSON.stringify(userData));
        })
        .catch(async () => {
          // Access token expired on load: attempt silent refresh using the HttpOnly cookie
          try {
            const refreshRes = await api.refreshToken();
            const newAccess = refreshRes.data?.access_token || refreshRes.access_token;
            if (newAccess) {
              localStorage.setItem(TOKEN_KEY, newAccess);
              setToken(newAccess);
              const userProfile = await api.getCurrentUser(newAccess);
              setUser(userProfile);
              localStorage.setItem(USER_KEY, JSON.stringify(userProfile));
              return;
            }
          } catch {
            // Refresh cookie also expired or invalid
          }

          // Session invalid/expired: purge session
          setToken(null);
          setUser(null);
          localStorage.removeItem(TOKEN_KEY);
          localStorage.removeItem(USER_KEY);
        });
    }
  }, []);

  const login = async (email, password) => {
    setLoading(true);
    try {
      const res = await api.login(email, password);
      const accessToken = res.data?.access_token || res.access_token;

      if (!accessToken) {
        throw new Error("Login failed: missing access token from server.");
      }
      localStorage.setItem(TOKEN_KEY, accessToken);
      setToken(accessToken);

      // Fetch user profile
      const userProfile = await api.getCurrentUser(accessToken);
      setUser(userProfile);
      localStorage.setItem(USER_KEY, JSON.stringify(userProfile));
      return userProfile;
    } finally {
      setLoading(false);
    }
  };

  const register = async (name, email, password, phone) => {
    setLoading(true);
    try {
      await api.registerCustomer(name, email, password, phone);
      // Auto-login after registration
      return await login(email, password);
    } finally {
      setLoading(false);
    }
  };

  const logout = () => {
    const savedToken = token || localStorage.getItem(TOKEN_KEY);
    api.logout(savedToken).catch(() => {});
    setToken(null);
    setUser(null);
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
  };

  return (
    <AuthContext.Provider value={{
      user,
      token,
      isAuthenticated: Boolean(token && user),
      loading,
      login,
      register,
      logout
    }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
