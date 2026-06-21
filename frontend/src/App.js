import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
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
import ConnectBroker from "./pages/ConnectBroker";
import Layout from "./components/Layout";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

// App Router — all pages public, no auth required
function AppRouter() {
  return (
    <Routes>
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
        <Route path="alerts" element={<AlertsConfig />} />
        <Route path="backtest" element={<Backtesting />} />
        <Route path="connect-broker" element={<ConnectBroker />} />
      </Route>
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <BrowserRouter>
      <Toaster position="top-right" richColors />
      <AppRouter />
    </BrowserRouter>
  );
}

export default App;
