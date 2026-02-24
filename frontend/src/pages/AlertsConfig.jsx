import { useState, useEffect } from "react";
import axios from "axios";
import { API, useAuth } from "../App";
import { Bell, Plus, Trash2, Send, CheckCircle, AlertCircle } from "lucide-react";
import { toast } from "sonner";

export default function AlertsConfig() {
  const { user } = useAuth();
  const [alerts, setAlerts] = useState([]);
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [newAlert, setNewAlert] = useState({
    alert_type: "arbitrage",
    symbol: "",
    threshold: "0.5",
  });
  const [telegramChatId, setTelegramChatId] = useState("");
  const [testingTelegram, setTestingTelegram] = useState(false);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [alertsRes, settingsRes] = await Promise.all([
        axios.get(`${API}/alerts`, { withCredentials: true }),
        axios.get(`${API}/settings`, { withCredentials: true }),
      ]);
      setAlerts(alertsRes.data);
      setSettings(settingsRes.data);
      setTelegramChatId(settingsRes.data?.telegram_chat_id || "");
    } catch (error) {
      console.error("Error loading data:", error);
    } finally {
      setLoading(false);
    }
  };

  const createAlert = async () => {
    if (!newAlert.threshold) {
      toast.error("Please set a threshold");
      return;
    }

    try {
      await axios.post(
        `${API}/alerts`,
        {
          alert_type: newAlert.alert_type,
          symbol: newAlert.symbol || null,
          threshold: parseFloat(newAlert.threshold),
          telegram_chat_id: telegramChatId || null,
          is_active: true,
        },
        { withCredentials: true }
      );
      toast.success("Alert created");
      setNewAlert({ alert_type: "arbitrage", symbol: "", threshold: "0.5" });
      loadData();
    } catch (error) {
      toast.error("Failed to create alert");
    }
  };

  const deleteAlert = async (alertId) => {
    try {
      await axios.delete(`${API}/alerts/${alertId}`, { withCredentials: true });
      toast.success("Alert deleted");
      loadData();
    } catch (error) {
      toast.error("Failed to delete alert");
    }
  };

  const saveTelegramSettings = async () => {
    try {
      await axios.put(
        `${API}/settings`,
        {
          telegram_chat_id: telegramChatId,
        },
        { withCredentials: true }
      );
      toast.success("Settings saved");
    } catch (error) {
      toast.error("Failed to save settings");
    }
  };

  const testTelegram = async () => {
    if (!telegramChatId) {
      toast.error("Please enter your Telegram Chat ID");
      return;
    }

    setTestingTelegram(true);
    try {
      const response = await axios.post(
        `${API}/alerts/test`,
        null,
        {
          params: { chat_id: telegramChatId },
          withCredentials: true,
        }
      );
      if (response.data.success) {
        toast.success("Test message sent! Check your Telegram");
      } else {
        toast.error("Failed to send test message");
      }
    } catch (error) {
      toast.error(
        error.response?.data?.detail || "Telegram not configured on server"
      );
    } finally {
      setTestingTelegram(false);
    }
  };

  const alertTypes = [
    { value: "arbitrage", label: "Cross-Exchange Arbitrage" },
    { value: "cash_carry", label: "Cash & Carry Spread" },
    { value: "synthetic", label: "Synthetic Mispricing" },
    { value: "statistical", label: "Statistical Arb Z-Score" },
    { value: "price", label: "Price Alert" },
  ];

  if (loading) {
    return (
      <div className="page-container">
        <div className="loading-container">
          <div className="loading-spinner"></div>
        </div>
      </div>
    );
  }

  return (
    <div className="page-container" data-testid="alerts-page">
      <div className="page-header">
        <h1 className="page-title">Alert Configuration</h1>
        <p className="page-subtitle">
          Set up Telegram alerts for arbitrage opportunities
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Telegram Setup */}
        <div className="card" data-testid="telegram-setup">
          <div className="card-header">
            <span className="card-title">Telegram Setup</span>
            <Send className="w-4 h-4 text-blue-500" />
          </div>

          <div className="space-y-4">
            <div className="p-4 bg-zinc-900 rounded-lg">
              <h4 className="font-medium mb-2">How to get your Chat ID:</h4>
              <ol className="text-sm text-zinc-400 list-decimal list-inside space-y-1">
                <li>Open Telegram and search for @userinfobot</li>
                <li>Start the bot and it will show your Chat ID</li>
                <li>Copy the number and paste it below</li>
              </ol>
            </div>

            <div>
              <label className="block text-sm text-zinc-500 mb-2">
                Your Telegram Chat ID
              </label>
              <input
                type="text"
                className="input"
                placeholder="e.g., 123456789"
                value={telegramChatId}
                onChange={(e) => setTelegramChatId(e.target.value)}
                data-testid="telegram-chat-id"
              />
            </div>

            <div className="flex gap-2">
              <button
                onClick={saveTelegramSettings}
                className="btn btn-primary flex-1"
                data-testid="save-telegram-btn"
              >
                Save Settings
              </button>
              <button
                onClick={testTelegram}
                className="btn btn-secondary flex items-center gap-2"
                disabled={testingTelegram}
                data-testid="test-telegram-btn"
              >
                {testingTelegram ? (
                  <span className="animate-spin">⏳</span>
                ) : (
                  <Send className="w-4 h-4" />
                )}
                Test
              </button>
            </div>

            <div className="p-3 bg-yellow-900/10 border border-yellow-900/30 rounded-lg">
              <div className="flex items-start gap-2">
                <AlertCircle className="w-4 h-4 text-yellow-500 mt-0.5" />
                <p className="text-xs text-zinc-400">
                  Note: Telegram alerts require the server to have a Telegram Bot
                  Token configured. Contact your admin if test alerts don't work.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Create Alert */}
        <div className="card" data-testid="create-alert">
          <div className="card-header">
            <span className="card-title">Create New Alert</span>
            <Plus className="w-4 h-4 text-green-500" />
          </div>

          <div className="space-y-4">
            <div>
              <label className="block text-sm text-zinc-500 mb-2">
                Alert Type
              </label>
              <select
                className="select"
                value={newAlert.alert_type}
                onChange={(e) =>
                  setNewAlert({ ...newAlert, alert_type: e.target.value })
                }
                data-testid="alert-type-select"
              >
                {alertTypes.map((type) => (
                  <option key={type.value} value={type.value}>
                    {type.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm text-zinc-500 mb-2">
                Symbol (optional)
              </label>
              <input
                type="text"
                className="input"
                placeholder="e.g., RELIANCE (leave empty for all)"
                value={newAlert.symbol}
                onChange={(e) =>
                  setNewAlert({ ...newAlert, symbol: e.target.value.toUpperCase() })
                }
                data-testid="alert-symbol"
              />
            </div>

            <div>
              <label className="block text-sm text-zinc-500 mb-2">
                Threshold (%)
              </label>
              <input
                type="number"
                className="input"
                value={newAlert.threshold}
                onChange={(e) =>
                  setNewAlert({ ...newAlert, threshold: e.target.value })
                }
                step="0.1"
                min="0"
                data-testid="alert-threshold"
              />
              <p className="text-xs text-zinc-500 mt-1">
                Alert when spread exceeds this percentage
              </p>
            </div>

            <button
              onClick={createAlert}
              className="btn btn-success w-full flex items-center justify-center gap-2"
              data-testid="create-alert-btn"
            >
              <Plus className="w-4 h-4" />
              Create Alert
            </button>
          </div>
        </div>
      </div>

      {/* Active Alerts */}
      <div className="card mt-6" data-testid="active-alerts">
        <div className="card-header">
          <span className="card-title">Active Alerts</span>
          <span className="badge badge-blue">{alerts.length} configured</span>
        </div>

        {alerts.length > 0 ? (
          <div className="space-y-3">
            {alerts.map((alert) => (
              <div
                key={alert.id}
                className="flex items-center justify-between p-4 bg-zinc-900 rounded-lg border border-zinc-800"
              >
                <div className="flex items-center gap-4">
                  <div
                    className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                      alert.is_active
                        ? "bg-green-900/20 text-green-500"
                        : "bg-zinc-800 text-zinc-500"
                    }`}
                  >
                    <Bell className="w-5 h-5" />
                  </div>
                  <div>
                    <div className="font-medium">
                      {alertTypes.find((t) => t.value === alert.alert_type)?.label ||
                        alert.alert_type}
                    </div>
                    <div className="text-sm text-zinc-500">
                      {alert.symbol || "All symbols"} • Threshold: {alert.threshold}%
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  {alert.is_active ? (
                    <span className="badge badge-green">Active</span>
                  ) : (
                    <span className="badge badge-red">Inactive</span>
                  )}
                  <button
                    onClick={() => deleteAlert(alert.id)}
                    className="p-2 hover:bg-zinc-800 rounded-lg text-red-500"
                    data-testid={`delete-alert-${alert.id}`}
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <Bell className="w-12 h-12 text-zinc-600 mx-auto mb-4" />
            <p>No alerts configured</p>
            <p className="text-xs mt-2">Create an alert above to get started</p>
          </div>
        )}
      </div>

      {/* Info Box */}
      <div className="card mt-6 bg-blue-900/10 border-blue-900/30">
        <div className="flex items-start gap-3">
          <CheckCircle className="w-5 h-5 text-blue-500 mt-0.5" />
          <div>
            <h3 className="font-medium text-blue-500 mb-1">Alert Triggers</h3>
            <ul className="text-sm text-zinc-400 list-disc list-inside space-y-1">
              <li>
                <strong>Cross-Exchange:</strong> When NSE vs BSE spread exceeds
                threshold
              </li>
              <li>
                <strong>Cash & Carry:</strong> When basis exceeds threshold
              </li>
              <li>
                <strong>Synthetic:</strong> When synthetic vs actual futures
                mispricing detected
              </li>
              <li>
                <strong>Statistical:</strong> When Z-score exceeds ±2
              </li>
              <li>
                <strong>Price:</strong> When stock moves more than threshold %
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
