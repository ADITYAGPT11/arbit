import { Outlet, NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../App";
import {
  LayoutDashboard,
  ArrowLeftRight,
  TrendingUp,
  BarChart3,
  Shield,
  Bell,
  History,
  LogOut,
  Calculator,
  GitCompare,
  Calendar,
  LineChart,
  User,
} from "lucide-react";

const navItems = [
  { path: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { path: "/arbitrage", label: "Cross-Exchange Arb", icon: ArrowLeftRight },
  { path: "/cash-carry", label: "Cash & Carry", icon: Calculator },
  { path: "/synthetic", label: "Synthetic Futures", icon: GitCompare },
  { path: "/calendar-spread", label: "Calendar Spread", icon: Calendar },
  { path: "/statistical", label: "Statistical Arb", icon: LineChart },
  { path: "/performance", label: "Performance", icon: TrendingUp },
  { path: "/risk", label: "Risk Management", icon: Shield },
  { path: "/alerts", label: "Alerts", icon: Bell },
  { path: "/backtest", label: "Backtesting", icon: History },
];

export default function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  return (
    <div className="flex min-h-screen bg-[#0a0a0a]">
      {/* Sidebar */}
      <aside className="sidebar" data-testid="sidebar">
        <div className="sidebar-header">
          <div className="sidebar-logo" data-testid="logo">
            ARBIT<span className="text-white">PRO</span>
          </div>
          <div className="text-xs text-zinc-500 mt-1">Indian Markets</div>
        </div>

        <nav className="sidebar-nav">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
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

        <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-zinc-800">
          <div className="flex items-center gap-3 mb-3">
            {user?.picture ? (
              <img
                src={user.picture}
                alt={user.name}
                className="w-8 h-8 rounded-full"
              />
            ) : (
              <div className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center">
                <User className="w-4 h-4" />
              </div>
            )}
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium truncate">{user?.name}</div>
              <div className="text-xs text-zinc-500 truncate">{user?.email}</div>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="btn btn-secondary w-full flex items-center justify-center gap-2"
            data-testid="logout-btn"
          >
            <LogOut className="w-4 h-4" />
            Logout
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
