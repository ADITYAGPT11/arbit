import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { useNavigate } from "react-router-dom";
import { API } from "../App";
import {
  Wifi,
  WifiOff,
  Plug,
  RefreshCw,
  Clock,
  Radio,
  Power,
} from "lucide-react";

export default function BrokerStatus() {
  const navigate = useNavigate();
  const [status, setStatus] = useState(null);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/market/broker-status`);
      setStatus(res.data);
    } catch {
      setStatus(null);
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 15000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  const handleConnect = () => {
    navigate("/connect-broker");
  };

  if (!status) {
    return (
      <div className="broker-status-card" data-testid="broker-status">
        <div className="broker-status-dot disconnected" />
        <span className="broker-status-text">Loading...</span>
      </div>
    );
  }

  const { broker, market, data_mode } = status;
  const isConnected = broker.is_connected;
  const isMarketOpen = market.is_market_open;

  // Determine overall state color
  let stateColor = "disconnected"; // red
  let stateLabel = "Disconnected";
  if (isConnected && isMarketOpen) {
    stateColor = "live";
    stateLabel = "Live";
  } else if (isConnected && !isMarketOpen) {
    stateColor = "connected";
    stateLabel = "Connected";
  }

  return (
    <div className="broker-panel" data-testid="broker-status">
      {/* Connection State */}
      <div className="broker-connection-row">
        <div className={`broker-status-dot ${stateColor}`} />
        <div className="broker-connection-info">
          <span className="broker-label">Angel One</span>
          <span className={`broker-state-text ${stateColor}`}>{stateLabel}</span>
        </div>
        {isConnected ? (
          <button
            onClick={fetchStatus}
            className="broker-action-btn"
            title="Refresh status"
            data-testid="broker-refresh-btn"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        ) : (
          <button
            onClick={handleConnect}
            className="broker-connect-btn"
            data-testid="broker-connect-btn"
            title="Connect a broker"
          >
            <Power className="w-3.5 h-3.5" />
          </button>
        )}
      </div>

      {/* Market Session */}
      <div className="broker-market-row" data-testid="market-session">
        <div className="broker-market-session">
          <Clock className="w-3 h-3 text-zinc-500" />
          <span className="broker-market-label">{market.session_label}</span>
        </div>
        {isMarketOpen && (
          <div className="broker-live-pulse" data-testid="live-indicator">
            <Radio className="w-3 h-3" />
            <span>LIVE</span>
          </div>
        )}
      </div>

      {/* Data Mode Indicator */}
      <div className="broker-data-row" data-testid="data-mode">
        {data_mode === "live" ? (
          <>
            <Wifi className="w-3 h-3 text-green-500" />
            <span className="text-[11px] text-green-500">Live Market Data</span>
          </>
        ) : (
          <>
            <WifiOff className="w-3 h-3 text-yellow-500" />
            <span className="text-[11px] text-yellow-500">Simulated Data</span>
          </>
        )}
      </div>

      {/* Session Details (when connected) */}
      {isConnected && broker.time_remaining && (
        <div className="broker-session-detail" data-testid="session-time">
          <span className="text-[10px] text-zinc-600">
            Session: {broker.time_remaining.split(".")[0]} remaining
          </span>
        </div>
      )}

      {/* Error State */}
      {broker.last_error && !broker.last_error.toLowerCase().includes("direct login disabled") && (
        <div className="broker-error" data-testid="broker-error">
          <span className="text-[10px] text-red-400 leading-tight">
            {broker.last_error.length > 60
              ? broker.last_error.substring(0, 60) + "..."
              : broker.last_error}
          </span>
        </div>
      )}

      {/* Not Connected - Prompt */}
      {!isConnected && (
        <button
          onClick={handleConnect}
          className="broker-connect-full-btn"
          data-testid="broker-connect-full-btn"
        >
          <Plug className="w-3.5 h-3.5" />
          Connect Broker
        </button>
      )}
    </div>
  );
}
