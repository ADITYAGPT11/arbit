import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { API } from "../App";
import {
  TrendingUp,
  TrendingDown,
  RefreshCw,
  Activity,
  ArrowUpRight,
  ArrowDownRight,
  Wifi,
  WifiOff,
  Database,
} from "lucide-react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
} from "recharts";
import { toast } from "sonner";

export default function Dashboard() {
  const [indices, setIndices] = useState([]);
  const [stocks, setStocks] = useState([]);
  const [arbitrageOpps, setArbitrageOpps] = useState([]);
  const [loading, setLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [dataSource, setDataSource] = useState(null);
  const [brokerStatus, setBrokerStatus] = useState(null);

  const fetchDataSource = useCallback(async () => {
    try {
      const [dsRes, bsRes] = await Promise.all([
        axios.get(`${API}/market/data-source`),
        axios.get(`${API}/market/broker-status`),
      ]);
      setDataSource(dsRes.data);
      setBrokerStatus(bsRes.data);
    } catch (error) {
      console.error("Error fetching data source:", error);
    }
  }, []);

  const fetchData = useCallback(async () => {
    // Load indices first (fastest)
    try {
      const indicesRes = await axios.get(`${API}/market/indices`, { timeout: 30000 });
      setIndices(indicesRes.data);
    } catch (error) {
      console.error("Error fetching indices:", error);
      setIndices([]);
    }
    
    // Then load stocks
    try {
      const stocksRes = await axios.get(`${API}/market/stocks`, { timeout: 30000 });
      setStocks(stocksRes.data.filter((s) => s.price !== null && s.price > 0).slice(0, 20));
    } catch (error) {
      console.error("Error fetching stocks:", error);
      setStocks([]);
    }
    
    // Finally arbitrage (may take longer)
    try {
      const arbRes = await axios.get(`${API}/arbitrage/cross-exchange?symbols=RELIANCE,TCS,INFY,HDFCBANK,SBIN`, { timeout: 30000 });
      setArbitrageOpps(arbRes.data.slice(0, 10));
    } catch (error) {
      console.error("Error fetching arbitrage:", error);
      setArbitrageOpps([]);
    }
    
    setLastUpdate(new Date());
    setLoading(false);
  }, []);

  const connectAngelOne = async () => {
    try {
      toast.info("Connecting to Angel One...");
      const response = await axios.post(`${API}/market/angel-one/login`);
      toast.success("Angel One connected successfully!");
      fetchDataSource();
      fetchData();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Failed to connect to Angel One");
    }
  };

  useEffect(() => {
    fetchDataSource();
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData, fetchDataSource]);

  const formatPrice = (price) => {
    if (price === null || price === undefined) return "—";
    return new Intl.NumberFormat("en-IN", {
      style: "currency",
      currency: "INR",
      minimumFractionDigits: 2,
    }).format(price);
  };

  const formatChange = (change) => {
    if (change === undefined || change === null) return "—";
    const sign = change >= 0 ? "+" : "";
    return `${sign}${change.toFixed(2)}%`;
  };

  const formatIndexValue = (value) => {
    if (value === null || value === undefined) return "—";
    return value.toLocaleString("en-IN", { maximumFractionDigits: 2 });
  };

  // Generate mock chart data for indices
  const generateChartData = (baseValue) => {
    const data = [];
    let value = baseValue * 0.98;
    for (let i = 0; i < 24; i++) {
      value = value + (Math.random() - 0.48) * (baseValue * 0.002);
      data.push({ time: `${i}:00`, value: Math.round(value * 100) / 100 });
    }
    return data;
  };

  if (loading) {
    return (
      <div className="page-container">
        <div className="flex flex-col items-center justify-center min-h-[400px]">
          <div className="loading-spinner mb-4"></div>
          <p className="text-zinc-400">Loading live market data from Angel One...</p>
          <p className="text-xs text-zinc-500 mt-2">This may take a few seconds</p>
        </div>
      </div>
    );
  }

  return (
    <div className="page-container" data-testid="dashboard">
      {/* Connection Error Alert */}
      {dataSource?.session_status?.last_error && (
        <div className="mb-4 p-4 bg-red-900/20 border border-red-900/50 rounded-lg">
          <div className="flex items-start gap-3">
            <WifiOff className="w-5 h-5 text-red-500 mt-0.5" />
            <div>
              <h3 className="font-medium text-red-500">Angel One Connection Failed</h3>
              <p className="text-sm text-zinc-400 mt-1">{dataSource.session_status.last_error}</p>
              <p className="text-xs text-zinc-500 mt-2">
                Please check your API credentials at{" "}
                <a href="https://smartapi.angelbroking.com/" target="_blank" rel="noopener noreferrer" className="text-blue-500 underline">
                  smartapi.angelbroking.com
                </a>
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-2xl font-bold">Market Dashboard</h1>
          <p className="text-zinc-500 text-sm">
            Real-time Indian market overview
            {brokerStatus?.market?.current_time_ist && (
              <span className="ml-2 text-zinc-600">
                ({brokerStatus.market.current_time_ist})
              </span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-4">
          {/* Data Source Status */}
          <div className="flex items-center gap-2 px-3 py-1.5 bg-zinc-900 rounded-lg border border-zinc-800">
            {brokerStatus?.broker?.is_connected ? (
              <>
                <Wifi className="w-4 h-4 text-green-500" />
                <span className="text-xs text-green-500">Angel One Live</span>
                {brokerStatus?.market?.is_market_open && (
                  <span className="ml-1 text-[10px] text-green-400 font-bold tracking-wider animate-pulse">LIVE</span>
                )}
              </>
            ) : dataSource?.session_status?.last_error ? (
              <>
                <WifiOff className="w-4 h-4 text-red-500" />
                <span className="text-xs text-red-500">Connection Error</span>
              </>
            ) : (
              <>
                <Database className="w-4 h-4 text-yellow-500" />
                <span className="text-xs text-yellow-500">Simulated Data</span>
                {dataSource?.angel_one_available && (
                  <button
                    onClick={connectAngelOne}
                    className="ml-2 text-xs text-blue-500 hover:underline"
                    data-testid="connect-angel-btn"
                  >
                    Connect Live
                  </button>
                )}
              </>
            )}
          </div>
          {/* Market Session Badge */}
          {brokerStatus?.market && (
            <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border ${
              brokerStatus.market.is_market_open
                ? "bg-green-900/20 border-green-900/50 text-green-500"
                : "bg-zinc-900 border-zinc-800 text-zinc-400"
            }`} data-testid="market-session-badge">
              <Activity className="w-3.5 h-3.5" />
              <span className="text-xs font-medium">{brokerStatus.market.session_label}</span>
            </div>
          )}
          <span className="text-xs text-zinc-500">
            Last updated:{" "}
            {lastUpdate ? lastUpdate.toLocaleTimeString() : "—"}
          </span>
          <button
            onClick={fetchData}
            className="btn btn-secondary flex items-center gap-2"
            data-testid="refresh-btn"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        </div>
      </div>

      {/* Indices */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
        {indices.map((index) => (
          <div
            key={index.index}
            className="card"
            data-testid={`index-${index.index}`}
          >
            <div className="flex justify-between items-start mb-2">
              <span className="text-xs text-zinc-500 font-medium">
                {index.index}
              </span>
              {index.data_source === 'angel_one_live' && (
                <span className="text-[10px] text-green-500">● LIVE</span>
              )}
            </div>
            <div className="font-mono text-xl font-bold">
              {formatIndexValue(index.value)}
            </div>
            {index.change !== null && (
              <div
                className={`flex items-center gap-1 text-sm ${
                  index.change >= 0 ? "text-green-500" : "text-red-500"
                }`}
              >
                {index.change >= 0 ? (
                  <ArrowUpRight className="w-4 h-4" />
                ) : (
                  <ArrowDownRight className="w-4 h-4" />
                )}
                <span>{index.change?.toFixed(2) || "—"}</span>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Stock Prices */}
        <div className="lg:col-span-2 card" data-testid="stock-prices-table">
          <div className="card-header">
            <span className="card-title">F&O Stocks - NSE vs BSE</span>
            <Activity className="w-4 h-4 text-zinc-500" />
          </div>
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Exchange</th>
                  <th>Price</th>
                  <th>Change</th>
                  <th>Volume</th>
                </tr>
              </thead>
              <tbody>
                {stocks.slice(0, 15).map((stock, idx) => (
                  <tr key={`${stock.symbol}-${stock.exchange}-${idx}`}>
                    <td className="font-medium">{stock.symbol}</td>
                    <td>
                      <span
                        className={`badge ${
                          stock.exchange === "NSE"
                            ? "badge-blue"
                            : "badge-yellow"
                        }`}
                      >
                        {stock.exchange}
                      </span>
                    </td>
                    <td>{formatPrice(stock.price)}</td>
                    <td
                      className={
                        stock.change_pct >= 0 ? "price-up" : "price-down"
                      }
                    >
                      {formatChange(stock.change_pct)}
                    </td>
                    <td>{stock.volume?.toLocaleString("en-IN") || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Arbitrage Opportunities */}
        <div className="card" data-testid="arbitrage-opps">
          <div className="card-header">
            <span className="card-title">Arbitrage Opportunities</span>
            <span className="badge badge-green">Live</span>
          </div>
          {arbitrageOpps.length > 0 ? (
            <div className="space-y-3">
              {arbitrageOpps.map((opp, idx) => (
                <div
                  key={idx}
                  className="p-3 bg-zinc-900 rounded-lg border border-zinc-800"
                >
                  <div className="flex justify-between items-start mb-2">
                    <span className="font-medium">{opp.symbol}</span>
                    <span className="badge badge-green">
                      {opp.spread_pct?.toFixed(2)}%
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div>
                      <span className="text-zinc-500">NSE:</span>
                      <span className="ml-2 font-mono">
                        {formatPrice(opp.nse_price)}
                      </span>
                    </div>
                    <div>
                      <span className="text-zinc-500">BSE:</span>
                      <span className="ml-2 font-mono">
                        {formatPrice(opp.bse_price)}
                      </span>
                    </div>
                  </div>
                  <div className="mt-2 text-xs text-green-500">
                    Net Profit: {formatPrice(opp.net_profit_per_share)}/share
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="empty-state">
              <p>No significant arbitrage opportunities detected</p>
              <p className="text-xs mt-2">
                Opportunities appear when spread &gt; 0.1%
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
        {indices.slice(0, 2).map((index) => (
          <div key={index.index} className="card" data-testid={`chart-${index.index}`}>
            <div className="card-header">
              <span className="card-title">{index.index} - Intraday</span>
              <span
                className={
                  index.change >= 0 ? "text-green-500" : "text-red-500"
                }
              >
                {formatChange(index.change_pct)}
              </span>
            </div>
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={generateChartData(index.value || 20000)}>
                  <defs>
                    <linearGradient id={`gradient-${index.index}`} x1="0" y1="0" x2="0" y2="1">
                      <stop
                        offset="5%"
                        stopColor={index.change >= 0 ? "#22c55e" : "#ef4444"}
                        stopOpacity={0.3}
                      />
                      <stop
                        offset="95%"
                        stopColor={index.change >= 0 ? "#22c55e" : "#ef4444"}
                        stopOpacity={0}
                      />
                    </linearGradient>
                  </defs>
                  <XAxis
                    dataKey="time"
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: "#71717a", fontSize: 10 }}
                  />
                  <YAxis
                    domain={["auto", "auto"]}
                    axisLine={false}
                    tickLine={false}
                    tick={{ fill: "#71717a", fontSize: 10 }}
                    tickFormatter={(v) => v.toLocaleString()}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "#1a1a1a",
                      border: "1px solid #262626",
                      borderRadius: "8px",
                    }}
                    labelStyle={{ color: "#a1a1aa" }}
                  />
                  <Area
                    type="monotone"
                    dataKey="value"
                    stroke={index.change >= 0 ? "#22c55e" : "#ef4444"}
                    fill={`url(#gradient-${index.index})`}
                    strokeWidth={2}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        ))}
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6">
        <div className="stat-card" data-testid="stat-total-opps">
          <div className="stat-label">Active Opportunities</div>
          <div className="stat-value text-green-500">{arbitrageOpps.length}</div>
        </div>
        <div className="stat-card" data-testid="stat-symbols">
          <div className="stat-label">Symbols Tracked</div>
          <div className="stat-value">{stocks.length}</div>
        </div>
        <div className="stat-card" data-testid="stat-indices">
          <div className="stat-label">Indices</div>
          <div className="stat-value">{indices.length}</div>
        </div>
        <div className="stat-card" data-testid="stat-market-status">
          <div className="stat-label">Market Status</div>
          <div className={`stat-value ${
            brokerStatus?.market?.is_market_open ? "text-green-500" : "text-zinc-400"
          }`}>
            {brokerStatus?.market?.is_market_open ? "OPEN" : 
             brokerStatus?.market?.session === "pre_open" ? "PRE-OPEN" :
             brokerStatus?.market?.session === "post_market" ? "POST-MKT" : "CLOSED"}
          </div>
        </div>
      </div>
    </div>
  );
}
