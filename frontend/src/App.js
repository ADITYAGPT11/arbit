import { useEffect, useState, useRef, useCallback } from "react";
import { BrowserRouter, Routes, Route, Navigate, useLocation, useNavigate } from "react-router-dom";
import axios from "axios";
import { Toaster, toast } from "sonner";
import "./App.css";

// Pages
import Dashboard from "./pages/Dashboard";
import ArbitrageScanner from "./pages/ArbitrageScanner";
import CashCarryArbitrage from "./pages/CashCarryArbitrage";
import SyntheticArbitrage from "./pages/SyntheticArbitrage";
import CalendarSpread from "./pages/CalendarSpread";
import StatisticalArbitrage from "./pages/StatisticalArbitrage";
import PerformanceAnalytics from "./pages/PerformanceAnalytics";
import RiskManagement from "./pages/RiskManagement";
import AlertsConfig from "./pages/AlertsConfig";
import Backtesting from "./pages/Backtesting";
import OptionChain from "./pages/OptionChain";
import IVAnalytics from "./pages/IVAnalytics";
import Login from "./pages/Login";
import Layout from "./components/Layout";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

// Auth Context
import { createContext, useContext } from "react";

const AuthContext = createContext(null);

export const useAuth = () => useContext(AuthContext);

// Auth Provider
const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const checkAuth = useCallback(async () => {
    // CRITICAL: If returning from OAuth callback, skip the /me check.
    if (window.location.hash?.includes("session_id=")) {
      setLoading(false);
      return;
    }

    try {
      const response = await axios.get(`${API}/auth/me`, {
        withCredentials: true,
      });
      setUser(response.data);
    } catch (error) {
      // User not logged in - that's fine for public pages
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  const login = (userData) => {
    setUser(userData);
  };

  const logout = async () => {
    try {
      await axios.post(`${API}/auth/logout`, {}, { withCredentials: true });
    } catch (error) {
      console.error("Logout error:", error);
    }
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, checkAuth }}>
      {children}
    </AuthContext.Provider>
  );
};

// Auth Callback Component
const AuthCallback = () => {
  const navigate = useNavigate();
  const { login } = useAuth();
  const hasProcessed = useRef(false);

  useEffect(() => {
    if (hasProcessed.current) return;
    hasProcessed.current = true;

    const processAuth = async () => {
      const hash = window.location.hash;
      const sessionId = hash.split("session_id=")[1]?.split("&")[0];

      if (sessionId) {
        try {
          const response = await axios.post(
            `${API}/auth/session`,
            { session_id: sessionId },
            { withCredentials: true }
          );
          login(response.data);
          toast.success("Login successful!");
          navigate("/dashboard", { replace: true, state: { user: response.data } });
        } catch (error) {
          console.error("Auth error:", error);
          toast.error("Authentication failed");
          navigate("/dashboard", { replace: true });
        }
      } else {
        navigate("/dashboard", { replace: true });
      }
    };

    processAuth();
  }, [navigate, login]);

  return (
    <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center">
      <div className="text-white text-xl">Authenticating...</div>
    </div>
  );
};

// Protected Route - Only for user-specific features (alerts, watchlist)
const ProtectedRoute = ({ children }) => {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0a0a0a] flex items-center justify-center">
        <div className="text-white text-xl">Loading...</div>
      </div>
    );
  }

  if (!user) {
    toast.info("Please login to access this feature");
    return <Navigate to="/dashboard" replace />;
  }

  return children;
};

// App Router - Most features are public, only alerts/watchlist need auth
function AppRouter() {
  const location = useLocation();

  // Check URL fragment for session_id synchronously during render
  if (location.hash?.includes("session_id=")) {
    return <AuthCallback />;
  }

  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      {/* All analysis features are public */}
      <Route path="/" element={<Layout />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<Dashboard />} />
        <Route path="option-chain" element={<OptionChain />} />
        <Route path="iv-analytics" element={<IVAnalytics />} />
        <Route path="arbitrage" element={<ArbitrageScanner />} />
        <Route path="cash-carry" element={<CashCarryArbitrage />} />
        <Route path="synthetic" element={<SyntheticArbitrage />} />
        <Route path="calendar-spread" element={<CalendarSpread />} />
        <Route path="statistical" element={<StatisticalArbitrage />} />
        <Route path="performance" element={<PerformanceAnalytics />} />
        <Route path="risk" element={<RiskManagement />} />
        <Route path="backtest" element={<Backtesting />} />
        {/* Only alerts require login (user-specific) */}
        <Route path="alerts" element={<ProtectedRoute><AlertsConfig /></ProtectedRoute>} />
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Toaster position="top-right" richColors />
        <AppRouter />
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
