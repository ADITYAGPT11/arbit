import { useState } from "react";
import { Outlet, NavLink, useLocation } from "react-router-dom";
import BrokerStatus from "./BrokerStatus";
import {
  LayoutDashboard,
  ArrowLeftRight,
  TrendingUp,
  Shield,
  Bell,
  History,
  Calculator,
  GitCompare,
  Calendar,
  LineChart,
  Grid3x3,
  Menu,
  X,
  Gauge,
  Plug,
} from "lucide-react";

const navItems = [
  { path: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { path: "/option-chain", label: "Option Chain", icon: Grid3x3 },
  { path: "/iv-analytics", label: "IV Analytics", icon: Gauge },
  { path: "/arbitrage", label: "Cross-Exchange Arb", icon: ArrowLeftRight },
  { path: "/cash-carry", label: "Cash & Carry", icon: Calculator },
  { path: "/synthetic", label: "Synthetic Futures", icon: GitCompare },
  { path: "/calendar-spread", label: "Calendar Spread", icon: Calendar },
  { path: "/statistical", label: "Statistical Arb", icon: LineChart },
  { path: "/performance", label: "Performance", icon: TrendingUp },
  { path: "/risk", label: "Risk Management", icon: Shield },
  { path: "/alerts", label: "Alerts", icon: Bell },
  { path: "/backtest", label: "Backtesting", icon: History },
  { path: "/connect-broker", label: "Connect Broker", icon: Plug },
];

export default function Layout() {
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const closeSidebar = () => setSidebarOpen(false);

  const currentPage = navItems.find((i) => location.pathname.startsWith(i.path))?.label || "Dashboard";

  return (
    <div className="flex min-h-screen bg-[#0a0a0a]">
      {/* Mobile Overlay */}
      {sidebarOpen && (
        <div
          className="sidebar-overlay"
          onClick={closeSidebar}
          data-testid="sidebar-overlay"
        />
      )}

      {/* Mobile Header */}
      <header className="mobile-header" data-testid="mobile-header">
        <button
          onClick={() => setSidebarOpen(!sidebarOpen)}
          className="mobile-menu-btn"
          data-testid="mobile-menu-btn"
          aria-label="Toggle menu"
        >
          {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
        </button>
        <div className="mobile-header-logo" data-testid="mobile-logo">
          ARBIT<span className="text-white">PRO</span>
        </div>
        <span className="mobile-header-page">{currentPage}</span>
      </header>

      {/* Sidebar */}
      <aside
        className={`sidebar ${sidebarOpen ? "sidebar-open" : ""}`}
        data-testid="sidebar"
      >
        <div className="sidebar-header">
          <div className="flex items-center justify-between">
            <div className="sidebar-logo" data-testid="logo">
              ARBIT<span className="text-white">PRO</span>
            </div>
            <button
              onClick={closeSidebar}
              className="sidebar-close-btn"
              aria-label="Close menu"
            >
              <X className="w-5 h-5" />
            </button>
          </div>
          <div className="text-xs text-zinc-500 mt-1">Indian Markets</div>
        </div>

        <nav className="sidebar-nav">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              onClick={closeSidebar}
              className={({ isActive }) =>
                `nav-item ${isActive ? "active" : ""}`
              }
              data-testid={`nav-${item.path.slice(1)}`}
            >
              <item.icon className="nav-icon" />
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <BrokerStatus />

        <div className="sidebar-footer">
          <div className="text-xs text-zinc-600 text-center">
            ArbitPRO v1.0
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
