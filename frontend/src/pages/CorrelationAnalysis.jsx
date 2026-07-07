import { useState, useEffect, useCallback, useMemo, Fragment } from "react";
import axios from "axios";
import { API } from "../App";
import {
  Activity, RefreshCw,
  Filter, ChevronDown, ChevronRight,
  Search, Info, HelpCircle, X, Loader2
} from "lucide-react";
import { toast } from "sonner";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer,
  ReferenceLine, AreaChart, Area, Scatter
} from "recharts";

import {
  TooltipProvider,
  Tooltip as ShadcnTooltip,
  TooltipTrigger,
  TooltipContent,
} from "../components/ui/tooltip";

const ALL_TIMEFRAMES = [5, 10, 20, 60, 126, 252];

// Determine which PVR mode drives the score for a given pair
function getActiveMode(p) {
  if (p.pvr_spread === undefined || p.pvr_hedge === undefined) return null;
  return p.pvr_spread >= p.pvr_hedge
    ? { label: "Sp", hint: "Spread (pairs trading) — long one, short the other" }
    : { label: "Hg", hint: "Hedge (buy-both) — cash market, no shorting" };
}

// Compute an actionable trade signal for a pair
function getActionSignal(p) {
  const mode = getActiveMode(p);
  if (!mode) return null;

  if (mode.label === 'Sp') {
    if (p.signal === "LONG_SPREAD") {
      return {
        text: `BUY ${p.sym1} / SELL ${p.sym2}`,
        brief: `↑ B ${p.sym1} / S ${p.sym2}`,
        type: "pairs_long",
        color: "text-green-400",
        bg: "bg-green-500/10",
        border: "border-green-500/30",
        desc: `${p.sym1} is oversold vs ${p.sym2} — buy the spread`,
        icon: "↑",
      };
    }
    if (p.signal === "SHORT_SPREAD") {
      return {
        text: `SELL ${p.sym1} / BUY ${p.sym2}`,
        brief: `↓ S ${p.sym1} / B ${p.sym2}`,
        type: "pairs_short",
        color: "text-red-400",
        bg: "bg-red-500/10",
        border: "border-red-500/30",
        desc: `${p.sym1} is overbought vs ${p.sym2} — sell the spread`,
        icon: "↓",
      };
    }
    return {
      text: "WATCH — no entry yet",
      brief: "WATCH",
      type: "watch",
      color: "text-zinc-400",
      bg: "bg-zinc-800/50",
      border: "border-zinc-700/30",
      desc: "No extreme z-score — wait for |z| > 2",
      icon: "—",
    };
  } else {
    let bonus = '';
    if (p.z_score < -1.5) bonus = ` — ${p.sym1} relatively cheap`;
    else if (p.z_score > 1.5) bonus = ` — ${p.sym2} relatively cheap`;
    return {
      text: `BUY BOTH ${p.sym1} + ${p.sym2}${bonus}`,
      brief: "⊕ BUY BOTH",
      type: "hedge",
      color: "text-yellow-400",
      bg: "bg-yellow-500/10",
      border: "border-yellow-500/30",
      desc: `Buy both in cash — no shorting needed${bonus}`,
      icon: "⊕",
    };
  }
}

export default function CorrelationAnalysis() {
  const [pairsData, setPairsData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [sectorFilter, setSectorFilter] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [showGuide, setShowGuide] = useState(false);
  const [expandedPair, setExpandedPair] = useState(null); // tracks which pair key is expanded

  // ── Fetch best pairs from BE (cached, pre-computed with backtest data) ──

  const fetchPairs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await axios.get(`${API}/correlation/pair-rankings`, {
        params: { max_days: 252, top_n: 0, limit: 50 },
        timeout: 300000,
      });
      setPairsData(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || "Failed to load pairs");
      toast.error("Failed to load correlation pairs.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchPairs(); }, [fetchPairs]);

  // ── Filtered + searched pairs ──

  const displayedPairs = useMemo(() => {
    if (!pairsData?.best_pairs) return [];
    let filtered = pairsData.best_pairs;

    if (sectorFilter !== "all") {
      filtered = filtered.filter(
        p => p.sym1_sector === sectorFilter || p.sym2_sector === sectorFilter
      );
    }

    if (searchQuery.trim()) {
      const q = searchQuery.toUpperCase();
      filtered = filtered.filter(
        p => p.sym1.includes(q) || p.sym2.includes(q)
      );
    }

    return filtered;
  }, [pairsData, sectorFilter, searchQuery]);

  const allSectors = useMemo(() => {
    if (!pairsData?.best_pairs) return [];
    const set = new Set();
    for (const p of pairsData.best_pairs) {
      if (p.sym1_sector) set.add(p.sym1_sector);
      if (p.sym2_sector) set.add(p.sym2_sector);
    }
    return Array.from(set).sort();
  }, [pairsData]);

  // ── Toggle row expansion ──

  const handleToggleRow = (pairKey) => {
    setExpandedPair(prev => prev === pairKey ? null : pairKey);
  };

  // ── Render ──

  return (
    <TooltipProvider>
    <div className="page-container" data-testid="correlation-page">
      {/* Header */}
      <div className="page-header flex flex-wrap items-start justify-between gap-4 mb-4">
        <div>
          <h1 className="page-title flex items-center gap-3">
            <Activity className="w-6 h-6 text-blue-500" />
            Correlation Analysis
          </h1>
          <p className="page-subtitle">
            Best actionable pairs from Nifty 50 — click any row to see backtest details & charts
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowGuide(prev => !prev)}
            className="flex items-center gap-1 text-[10px] px-2 py-1.5 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-blue-400 transition-colors"
          >
            <Info className="w-3 h-3" />
            Guide
          </button>
          <button
            onClick={fetchPairs}
            disabled={loading}
            className="flex items-center gap-1 text-[10px] px-2.5 py-1.5 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200 transition-colors"
          >
            <RefreshCw className={`w-3 h-3 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </button>
        </div>
      </div>

      {/* Guide panel */}
      {showGuide && (
        <CorrelationExplainer onClose={() => setShowGuide(false)} />
      )}

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-2 text-[10px] mb-3">
        <Filter className="w-3 h-3 text-zinc-500" />
        <span className="text-zinc-600 uppercase tracking-wider font-semibold">Filter:</span>

        <select
          value={sectorFilter}
          onChange={e => setSectorFilter(e.target.value)}
          className="bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-zinc-300 text-[10px] cursor-pointer"
        >
          <option value="all">All Sectors</option>
          {allSectors.map(s => (
            <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>
          ))}
        </select>

        <div className="flex items-center gap-1 ml-auto">
          <Search className="w-3 h-3 text-zinc-600" />
          <input
            type="text"
            placeholder="Search symbols..."
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            className="bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-zinc-300 text-[10px] w-28 placeholder:text-zinc-600"
          />
        </div>
      </div>

      {/* Loading badge */}
      {loading && (
        <div className="flex items-center justify-center gap-2 py-3">
          <Loader2 className="w-4 h-4 text-blue-400 animate-spin" />
          <span className="text-[11px] text-zinc-500">
            {pairsData?.cached
              ? "Loading best pairs..."
              : "Computing all 1,225 pairs in batches (first load)..."
            }
          </span>
        </div>
      )}

      {/* Error */}
      {error && !loading && (
        <div className="bg-red-900/20 border border-red-800/30 rounded-lg p-4 text-sm text-red-400">
          {error}
          <button onClick={fetchPairs} className="ml-3 underline hover:text-red-300">Retry</button>
        </div>
      )}

      {/* Table */}
      {pairsData && !loading && (
        <div className="overflow-x-auto rounded-lg border border-zinc-800">
          <table className="w-full text-[10px] font-mono">
            <thead>
              <tr className="bg-zinc-900 text-zinc-500 uppercase tracking-wider border-b border-zinc-800">
                <th className="text-left py-2 px-2 font-semibold sticky left-0 bg-zinc-900 z-10">#</th>
                <th className="text-left py-2 px-2 font-semibold sticky left-[24px] bg-zinc-900 z-10">Pair</th>
                <th className="text-left py-2 px-2 font-semibold">
                  <span className="flex items-center gap-1">
                    Signal
                    <ColumnTooltip tip="Actionable trade signal. ↑ = Buy spread (oversold), ↓ = Sell spread (overbought), ⊕ = Buy both as hedge, — = No entry yet." />
                  </span>
                </th>
                <th className="text-right py-2 px-1.5 font-semibold">
                  <span className="flex items-center justify-end gap-1">
                    Score
                    <ColumnTooltip tip="Portfolio Variance Reduction (PVR) score (0-100). Measures risk eliminated by pairing these stocks. 70+ = strong risk reduction." />
                  </span>
                </th>
                <th className="text-right py-2 px-1.5 font-semibold">
                  <span className="flex items-center justify-end gap-1">
                    Z-Score
                    <ColumnTooltip tip="How far the current price ratio is from its mean. |z| > 2 signals an extreme — entry opportunity." />
                  </span>
                </th>
                <th className="text-right py-2 px-1.5 font-semibold">
                  <span className="flex items-center justify-end gap-1">
                    PVR Sp
                    <ColumnTooltip tip="Portfolio Variance Reduction for spread mode (long-short pairs trading). Higher = tightly linked returns." />
                  </span>
                </th>
                <th className="text-right py-2 px-1.5 font-semibold">
                  <span className="flex items-center justify-end gap-1">
                    PVR Hg
                    <ColumnTooltip tip="Portfolio Variance Reduction for hedge mode (buy-both in cash). Higher = good diversification hedge." />
                  </span>
                </th>
                <th className="text-right py-2 px-1.5 font-semibold">
                  <span className="flex items-center justify-end gap-1">
                    Sharpe
                    <ColumnTooltip tip="Backtest Sharpe ratio (risk-adjusted return). >1 = good, >2 = excellent. Pre-computed on backend." />
                  </span>
                </th>
                <th className="text-right py-2 px-1.5 font-semibold">
                  <span className="flex items-center justify-end gap-1">
                    Return
                    <ColumnTooltip tip="Total backtest return % over 252 days. Pre-computed on backend with 0.05% transaction costs." />
                  </span>
                </th>
                <th className="text-right py-2 px-1.5 font-semibold">
                  <span className="flex items-center justify-end gap-1">
                    Win%
                    <ColumnTooltip tip="Backtest win rate — percentage of profitable trades." />
                  </span>
                </th>
                <th className="py-2 px-2" />
              </tr>
            </thead>
            <tbody>
              {displayedPairs.map((p, idx) => {
                const pairKey = `${p.sym1}-${p.sym2}`;
                const isExpanded = expandedPair === pairKey;
                const action = getActionSignal(p);
                const mode = getActiveMode(p);
                const sameSector = p.sym1_sector === p.sym2_sector;

                return (
                  <Fragment key={pairKey}>
                    {/* Main row */}
                    <tr
                      onClick={() => handleToggleRow(pairKey)}
                      className={`border-b border-zinc-800/30 transition-colors cursor-pointer ${
                        idx % 2 === 0 ? "bg-zinc-900/30" : "bg-transparent"
                      } hover:bg-zinc-800/40 ${isExpanded ? "bg-zinc-800/50" : ""}`}
                    >
                      <td className="py-1.5 px-2 text-zinc-600 sticky left-0 bg-inherit z-10">{idx + 1}</td>
                      <td className="py-1.5 px-2 sticky left-[24px] bg-inherit z-10">
                        <div className="flex items-center gap-1">
                          <span className="font-semibold text-blue-400">{p.sym1}</span>
                          <span className="text-zinc-700">/</span>
                          <span className="font-semibold text-orange-400">{p.sym2}</span>
                          {!sameSector && (
                            <span className="text-[8px] text-yellow-600 ml-0.5">✦</span>
                          )}
                        </div>
                        <div className="text-[8px] text-zinc-600 leading-none mt-0.5">
                          {sameSector
                            ? p.sym1_sector?.replace(/_/g, ' ')
                            : `${p.sym1_sector?.replace(/_/g, ' ')} / ${p.sym2_sector?.replace(/_/g, ' ')}`
                          }
                        </div>
                      </td>
                      <td className="py-1.5 px-2">
                        {action && (
                          <span
                            className={`inline-flex items-center gap-0.5 text-[9px] px-1.5 py-0.5 rounded font-bold ${action.bg} ${action.color} border ${action.border}`}
                            title={action.desc}
                          >
                            {action.icon} {action.brief}
                          </span>
                        )}
                      </td>
                      <td className={`py-1.5 px-1.5 text-right font-bold ${
                        p.score >= 70 ? 'text-green-400'
                          : p.score >= 50 ? 'text-yellow-400'
                          : p.score >= 30 ? 'text-orange-400'
                          : 'text-red-400'
                      }`}>
                        <span>{p.score}</span>
                        {mode && (
                          <span className={`ml-1 text-[8px] px-1 py-0.5 rounded font-mono font-bold ${
                            mode.label === 'Sp'
                              ? 'bg-green-500/15 text-green-400'
                              : 'bg-yellow-500/15 text-yellow-400'
                          }`} title={mode.hint}>
                            {mode.label}
                          </span>
                        )}
                      </td>
                      <td className={`py-1.5 px-1.5 text-right font-mono ${
                        Math.abs(p.z_score || 0) > 2 ? 'text-orange-400 font-bold'
                          : Math.abs(p.z_score || 0) > 1.5 ? 'text-yellow-400'
                          : 'text-zinc-400'
                      }`}>
                        {p.z_score?.toFixed(2) || '—'}
                      </td>
                      <td className={`py-1.5 px-1.5 text-right ${
                        (p.pvr_spread || 0) >= 70 ? 'text-green-400'
                          : (p.pvr_spread || 0) >= 40 ? 'text-yellow-400'
                          : 'text-zinc-500'
                      }`}>
                        {p.pvr_spread !== undefined ? `${p.pvr_spread.toFixed(0)}%` : '—'}
                      </td>
                      <td className={`py-1.5 px-1.5 text-right ${
                        (p.pvr_hedge || 0) >= 70 ? 'text-green-400'
                          : (p.pvr_hedge || 0) >= 40 ? 'text-yellow-400'
                          : 'text-zinc-500'
                      }`}>
                        {p.pvr_hedge !== undefined ? `${p.pvr_hedge.toFixed(0)}%` : '—'}
                      </td>
                      <td className={`py-1.5 px-1.5 text-right font-mono ${
                        p.bt_sharpe >= 1.5 ? 'text-green-400'
                          : p.bt_sharpe >= 0.5 ? 'text-yellow-400'
                          : 'text-zinc-500'
                      }`}>
                        {p.bt_sharpe?.toFixed(2) || '—'}
                      </td>
                      <td className={`py-1.5 px-1.5 text-right font-mono ${
                        (p.bt_return || 0) > 0 ? 'text-green-400'
                          : (p.bt_return || 0) < 0 ? 'text-red-400'
                          : 'text-zinc-500'
                      }`}>
                        {p.bt_return !== undefined ? `${p.bt_return > 0 ? '+' : ''}${p.bt_return.toFixed(1)}%` : '—'}
                      </td>
                      <td className={`py-1.5 px-1.5 text-right font-mono ${
                        (p.bt_win_rate || 0) > 60 ? 'text-green-400'
                          : (p.bt_win_rate || 0) > 40 ? 'text-yellow-400'
                          : 'text-zinc-500'
                      }`}>
                        {p.bt_win_rate !== undefined ? `${p.bt_win_rate.toFixed(0)}%` : '—'}
                      </td>
                      <td className="py-1.5 px-2 text-zinc-600">
                        {isExpanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
                      </td>
                    </tr>

                    {/* Expanded detail row */}
                    {isExpanded && (
                      <tr className="bg-zinc-900/60 border-b border-zinc-800">
                        <td colSpan={11} className="p-0">
                          <div className="px-3 py-3 space-y-3">
                            {/* Entry/Stop/Target levels */}
                            <div className="grid grid-cols-3 gap-2">
                              <div className="bg-zinc-900/80 rounded px-2.5 py-2 text-center border border-zinc-800/60">
                                <div className="text-[8px] text-zinc-600 uppercase tracking-wider mb-0.5">Entry Level</div>
                                <div className="font-mono text-[12px] font-bold text-blue-400">
                                  {p.signal === "LONG_SPREAD" ? p.entry_level_down?.toFixed(4) : p.entry_level_up?.toFixed(4)}
                                </div>
                                <div className="text-[8px] text-zinc-600">
                                  {p.signal === "LONG_SPREAD" ? "Buy when ratio ↓ here" : "Sell when ratio ↑ here"}
                                </div>
                              </div>
                              <div className="bg-zinc-900/80 rounded px-2.5 py-2 text-center border border-zinc-800/60">
                                <div className="text-[8px] text-zinc-600 uppercase tracking-wider mb-0.5">Target</div>
                                <div className="font-mono text-[12px] font-bold text-green-400">
                                  {p.mean_ratio?.toFixed(4)}
                                </div>
                                <div className="text-[8px] text-zinc-600">Exit when z-score ≈ 0</div>
                              </div>
                              <div className="bg-zinc-900/80 rounded px-2.5 py-2 text-center border border-zinc-800/60">
                                <div className="text-[8px] text-zinc-600 uppercase tracking-wider mb-0.5">Stop Loss</div>
                                <div className="font-mono text-[12px] font-bold text-red-400">
                                  {p.signal === "LONG_SPREAD" ? p.entry_level_up?.toFixed(4) : p.entry_level_down?.toFixed(4)}
                                </div>
                                <div className="text-[8px] text-zinc-600">Exit if ratio crosses here</div>
                              </div>
                            </div>

                            {/* Multi-timeframe correlations chip */}
                            <div className="flex flex-wrap gap-x-2 gap-y-0.5 text-[9px] text-zinc-600">
                              <span className="text-zinc-500 uppercase tracking-wider">Corr:</span>
                              {ALL_TIMEFRAMES.map(tf => {
                                const corr = p.correlations?.[`${tf}d`];
                                const isDefined = corr !== undefined && corr !== null;
                                return (
                                  <span key={tf} className={
                                    isDefined
                                      ? Math.abs(corr) > 0.7 ? 'text-green-400'
                                        : Math.abs(corr) > 0.4 ? 'text-yellow-400'
                                        : 'text-zinc-500'
                                      : 'text-zinc-700'
                                  }>
                                    {tf}: {isDefined ? `${corr >= 0 ? '+' : ''}${(corr * 100).toFixed(0)}%` : '—'}
                                  </span>
                                );
                              })}
                              <span className="text-zinc-700">·</span>
                              <span>Cst: {(p.consistency * 100).toFixed(0)}%</span>
                              {p.cointegrated && (
                                <>
                                  <span className="text-zinc-700">·</span>
                                  <span className="text-green-400">Coint ✓ (p={p.coint_pvalue})</span>
                                </>
                              )}
                              {p.half_life_days > 0 && (
                                <>
                                  <span className="text-zinc-700">·</span>
                                  <span>HL: {p.half_life_days}d</span>
                                </>
                              )}
                            </div>

                            {/* Backtest detail panel */}
                            <BacktestDetailPanel sym1={p.sym1} sym2={p.sym2} />
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                );
              })}
            </tbody>
          </table>

          {displayedPairs.length === 0 && !loading && (
            <div className="text-center py-8 text-zinc-600 text-xs">No pairs match the current filters</div>
          )}

          {pairsData && !loading && (
            <div className="text-center py-2 text-[9px] text-zinc-600 border-t border-zinc-800/50">
              All {pairsData?.total_pairs?.toLocaleString()} pairs computed · showing best {pairsData?.best_pairs?.length} by score
              {pairsData.cached && <span className="text-zinc-700 ml-2">· cached</span>}
            </div>
          )}
        </div>
      )}
    </div>
    </TooltipProvider>
  );
}

/* ════════════════════════════════════════════════
   Backtest Detail Panel — inline backtest with charts & trade log
   ════════════════════════════════════════════════ */

function BacktestDetailPanel({ sym1, sym2 }) {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchBacktest = useCallback(async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await axios.post(`${API}/correlation/backtest`, {
        sym1, sym2, days: 252,
        entry_z: 2.0, exit_z: 0.0, stop_z: 3.0,
        rolling_window: 20, use_hedge_ratio: true,
        beta_window: 60, require_cointegrated: false,
        transaction_cost_pct: 0.05,
      }, { timeout: 300000 });
      setResult(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || "Backtest failed");
    } finally {
      setLoading(false);
    }
  }, [sym1, sym2]);

  useEffect(() => { fetchBacktest(); }, [fetchBacktest]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-3 text-[10px] text-zinc-500">
        <div className="animate-spin w-3 h-3 border-2 border-purple-500 border-t-transparent rounded-full" />
        Running backtest over 252 days...
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-between bg-red-900/10 border border-red-800/20 rounded-lg p-2 text-[10px] text-red-400">
        <span>Backtest error: {error}</span>
        <button onClick={fetchBacktest} className="underline hover:text-red-300 ml-2 flex-shrink-0">Retry</button>
      </div>
    );
  }

  // ── Handle API success but error payload (e.g., not cointegrated, nselib fetch failed) ──
  if (result && !result.metrics) {
    const errMsg = result.error || "Backtest returned no metrics — pair may not be tradeable";
    return (
      <div className="flex items-center justify-between bg-amber-900/10 border border-amber-800/20 rounded-lg p-2 text-[10px] text-amber-400">
        <div className="flex items-center gap-2">
          <span>{errMsg}</span>
          {result.coint_info && (
            <span className="text-zinc-600">
              (p-value: {result.coint_info.coint_pvalue}, HL: {result.coint_info.half_life_days}d)
            </span>
          )}
        </div>
        <div className="flex items-center gap-1.5 flex-shrink-0">
          <button
            onClick={fetchBacktest}
            className="text-[9px] px-1.5 py-0.5 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-400 transition-colors"
          >
            ↻ Retry
          </button>
        </div>
      </div>
    );
  }

  if (!result) return null;

  const m = result.metrics;
  const markers = result.markers || [];
  const spreadSeries = result.spread_series || [];

  return (
    <div className="space-y-2">
      {/* Cointegration info banner */}
      {result.coint_info && (
        <div className={`text-[9px] flex items-center gap-1.5 px-2 py-1 rounded-lg ${
          result.coint_info.cointegrated
            ? "bg-green-900/15 text-green-400 border border-green-800/20"
            : "bg-yellow-900/15 text-yellow-400 border border-yellow-800/20"
        }`}>
          {result.coint_info.cointegrated ? "✓ Coint" : "⚠ Not coint"}
          <span className="text-zinc-600">p={result.coint_info.coint_pvalue}</span>
          {result.coint_info.half_life_days > 0 && <><span className="text-zinc-600">|</span>HL: {result.coint_info.half_life_days}d</>}
          {result.spread_stats?.avg_beta && <><span className="text-zinc-600">|</span>β={result.spread_stats.avg_beta}</>}
          <span className="text-zinc-600">|</span>
          <span>Cost: {result.params?.transaction_cost_pct || 0.05}%/side</span>
        </div>
      )}

      {/* Strategy summary — plain-English interpretation */}
      <StrategySummary result={result} />

      {/* Metrics grid */}
      <div className="grid grid-cols-4 gap-1.5">
        <BMC label="Return" value={`${m.total_return_pct > 0 ? '+' : ''}${m.total_return_pct}%`} color={m.total_return_pct > 0 ? "text-green-400" : "text-red-400"} />
        <BMC label="Sharpe" value={m.sharpe_ratio?.toFixed(2)} color={m.sharpe_ratio > 1 ? "text-green-400" : m.sharpe_ratio > 0 ? "text-yellow-400" : "text-red-400"} />
        <BMC label="Win Rate" value={`${m.win_rate}%`} color={m.win_rate > 50 ? "text-green-400" : "text-yellow-400"} />
        <BMC label="Max DD" value={`${m.max_drawdown_pct}%`} color={m.max_drawdown_pct < 15 ? "text-green-400" : m.max_drawdown_pct < 30 ? "text-yellow-400" : "text-red-400"} />
        <BMC label="Trades" value={m.total_trades} />
        <BMC label="Profit Factor" value={m.profit_factor == null ? '' : m.profit_factor?.toFixed(2)} isInfinity={m.profit_factor == null} color={m.profit_factor == null ? "text-green-400" : m.profit_factor > 1.5 ? "text-green-400" : m.profit_factor > 1 ? "text-yellow-400" : "text-red-400"} />
        <BMC label="Avg Win" value={`+${m.avg_win_pct}%`} color="text-green-400" />
        <BMC label="Avg Loss" value={`${m.avg_loss_pct}%`} color="text-red-400" />
      </div>

      {/* Price chart — candlestick with entry/exit overlays */}
      {result.price_data && result.trades?.length > 0 && (
        <PriceChart
          priceData={result.price_data}
          trades={result.trades}
          sym1={result.sym1}
          sym2={result.sym2}
        />
      )}

      {/* Spread chart with entry/exit markers */}
      {spreadSeries.length > 0 && (
        <BacktestCharts spreadSeries={spreadSeries} markers={markers} equityCurve={result.equity_curve} />
      )}

      {/* Trade log */}
      {result.trades?.length > 0 && (
        <details className="group">
          <summary className="text-[9px] text-zinc-500 cursor-pointer hover:text-zinc-300 transition-colors p-1 rounded hover:bg-zinc-800/30">
            Trade Log ({result.trades.length} trades)
          </summary>
          <div className="mt-1 max-h-28 overflow-y-auto space-y-0.5">
            {[...result.trades].reverse().map((t, i) => (
              <div key={i} className="flex items-center justify-between text-[9px] font-mono px-1.5 py-0.5 rounded hover:bg-zinc-800/40">
                <div className="flex items-center gap-1.5 min-w-0">
                  <span className={`w-1 h-1 rounded-full flex-shrink-0 ${t.pnl_pct > 0 ? "bg-green-500" : "bg-red-500"}`} />
                  <span className="text-zinc-600">{t.entry_date?.slice(5)}</span>
                  <span className={t.side === "LONG_SPREAD" ? "text-green-400" : "text-red-400"}>
                    {t.side === "LONG_SPREAD" ? "L" : "S"}
                  </span>
                  <span className="text-zinc-700">→ {t.exit_date?.slice(5)}</span>
                  {t.exit_reason !== "TARGET" && (
                    <span className={`text-[7px] px-0.5 rounded ${
                      t.exit_reason === "STOP_LOSS" ? "bg-red-900/30 text-red-400" : "bg-zinc-800 text-zinc-500"
                    }`}>
                      {t.exit_reason === "STOP_LOSS" ? "SL" : "END"}
                    </span>
                  )}
                </div>
                <span className={t.pnl_pct > 0 ? "text-green-400" : "text-red-400"}>
                  {t.pnl_pct > 0 ? '+' : ''}{t.pnl_pct}%
                </span>
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}

/* Tiny metric chip for backtest detail grid */
function BMC({ label, value, color, isInfinity }) {
  return (
    <div className="bg-zinc-900/70 border border-zinc-800/60 rounded px-1.5 py-1 text-center">
      <div className="text-[7px] text-zinc-600 uppercase tracking-wider">{label}</div>
      <div className={`font-mono text-[10px] font-bold ${color || 'text-zinc-300'}`}>
        {isInfinity ? '∞' : value}
      </div>
    </div>
  );
}

/* ════════════════════════════════════════════════
   Strategy Summary — plain-English interpretation of backtest results
   ════════════════════════════════════════════════ */

function StrategySummary({ result }) {
  const m = result.metrics;
  const ci = result.coint_info || {};
  const p = result.params || {};

  const isGood = m.sharpe_ratio > 1 && m.total_return_pct > 0;
  const isDecent = m.sharpe_ratio > 0 && m.total_return_pct > 0;
  const totalDays = result.days || p.days || '—';
  const numTrades = m.total_trades || 0;

  // Build a list of bullet points
  const points = [];
  points.push(`Tested over ${totalDays} trading days (~${Math.round(totalDays / 252 * 10) / 10} yr)`);
  points.push(`Entered ${numTrades} trades when z-score crossed ±${p.entry_z || 2.0}σ`);
  points.push(numTrades > 0
    ? `Won ${m.winning_trades || 0} / lost ${m.losing_trades || 0} (${m.win_rate || 0}% win rate)`
    : 'No trades triggered — try a lower entry z-score threshold'
  );
  if (m.sharpe_ratio != null) {
    points.push(m.sharpe_ratio > 1
      ? `Sharpe ${m.sharpe_ratio.toFixed(2)} — good risk-adjusted return (>1)`
      : m.sharpe_ratio > 0
        ? `Sharpe ${m.sharpe_ratio.toFixed(2)} — positive but below ideal (target >1)`
        : `Sharpe ${m.sharpe_ratio.toFixed(2)} — negative, strategy losing on risk-adjusted basis`
    );
  }
  if (m.profit_factor != null) {
    points.push(`Profit factor ${m.profit_factor.toFixed(2)} — you make ₹${m.profit_factor.toFixed(2)} for every ₹1 lost`);
  } else if (m.total_trades > 0) {
    points.push('Profit factor ∞ — no losing trades in this backtest period');
  }
  if (ci.cointegrated) {
    points.push(`Cointegrated ✓ (p=${ci.coint_pvalue}) — spread is mean-reverting, strategy has statistical edge`);
  }

  return (
    <div className="bg-zinc-900/50 border border-zinc-800/60 rounded-lg px-2.5 py-2">
      <div className="text-[8px] text-zinc-600 uppercase tracking-wider mb-1">
        Strategy: Mean-Reversion Pairs Trade
        <span className="text-zinc-700 ml-2">·</span>
        <span className="text-zinc-700 ml-2">{p.use_hedge_ratio ? 'β-Hedge' : 'Price Ratio'}</span>
        <span className="text-zinc-700 ml-2">·</span>
        <span className="text-zinc-700 ml-2">{p.transaction_cost_pct || 0.05}%/side cost</span>
      </div>
      <ul className="space-y-0.5">
        {points.map((pt, i) => (
          <li key={i} className="text-[9px] text-zinc-400 flex items-start gap-1">
            <span className={`mt-0.5 w-1 h-1 rounded-full flex-shrink-0 ${
              i === 0 ? 'bg-blue-400'
                : pt.includes('—') ? 'bg-zinc-600'
                : pt.includes('✓') || pt.includes('good') || pt.includes('∞') ? 'bg-green-400'
                : pt.includes('negative') || pt.includes('losing') ? 'bg-red-400'
                : 'bg-zinc-500'
            }`} />
            <span>{pt}</span>
          </li>
        ))}
      </ul>
      <div className={`mt-1.5 text-[9px] font-semibold ${
        isGood ? 'text-green-400' : isDecent ? 'text-yellow-400' : 'text-zinc-500'
      }`}>
        {isGood
          ? '✅ This pair shows a viable trading strategy with positive risk-adjusted returns.'
          : isDecent
            ? '⚠️ Marginally profitable — consider adjusting parameters or trying a different pair.'
            : numTrades > 0
              ? '❌ Strategy not profitable on this pair with current settings.'
              : 'ℹ️ No trades — the spread never reached the entry threshold. Try lowering entry_z.'
        }
      </div>
    </div>
  );
}


/* ════════════════════════════════════════════════
   Price Chart — candlestick-like chart with entry/exit markers overlaid
   Uses close price lines + shaded entry/exit zones for clarity
   ════════════════════════════════════════════════ */

function PriceChart({ priceData, trades, sym1, sym2 }) {
  // Merge both symbols' close prices into a single data array for Recharts
  const d1 = priceData.sym1 || {};
  const d2 = priceData.sym2 || {};
  const dates = d1.dates || d2.dates || [];
  const c1 = d1.close || [];
  const c2 = d2.close || [];

  // Build merged chart data
  const chartData = dates.map((date, i) => ({
    date,
    [sym1]: c1[i] || null,
    [sym2]: c2[i] || null,
  }));

  // Entry/exit marker annotations
  const markers = trades.flatMap(t => [
    { ...t, markerType: 'entry', date: t.entry_date },
    { ...t, markerType: 'exit', date: t.exit_date },
  ]);

  // Find min/max prices for Y-axis domain
  const allPrices = [...c1, ...c2].filter(p => p != null);
  const yMin = Math.min(...allPrices) * 0.98;
  const yMax = Math.max(...allPrices) * 1.02;

  if (!chartData.length) return null;

  // Enrich markers with actual stock price at their date for correct Y-axis positioning
  const enrichMarkers = (mkrs, priceKey) => mkrs.map(m => {
    const pt = chartData.find(d => d.date === m.date);
    return { ...m, price: pt?.[priceKey] || null };
  });

  return (
    <div>
      <h5 className="text-[8px] font-semibold text-zinc-600 uppercase tracking-wider mb-1">Stock Prices — entries (●) / exits (●)</h5>
      <div className="h-32 bg-zinc-950 rounded-lg p-1 border border-zinc-800 min-w-0">
        <ResponsiveContainer width="100%" height="100%" minWidth={0}>
          <LineChart data={chartData}>
            <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fill: "#52525b", fontSize: 7 }} tickFormatter={(v) => v?.slice(5) || ""} interval="preserveStartEnd" />
            <YAxis axisLine={false} tickLine={false} tick={{ fill: "#52525b", fontSize: 7 }} domain={[yMin, yMax]} width={42} tickFormatter={(v) => v.toFixed(0)} />
            <Tooltip content={<BTCustomTooltip />} />
            <Line type="monotone" dataKey={sym1} stroke="#3b82f6" strokeWidth={1} dot={false} name={sym1} />
            <Line type="monotone" dataKey={sym2} stroke="#f59e0b" strokeWidth={1} dot={false} name={sym2} />
            {/* Entry/exit markers positioned at the actual stock price (sym2) */}
            <Scatter data={enrichMarkers(markers.filter(m => m.markerType === 'entry'), sym2)} dataKey="price" fill="#f59e0b" r={3.5} name="Entry" />
            <Scatter data={enrichMarkers(markers.filter(m => m.markerType === 'exit'), sym2)} dataKey="price" fill="#a855f7" r={2.5} name="Exit" />
          </LineChart>
        </ResponsiveContainer>
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-0.5 text-[7px] text-zinc-600">
        <span className="flex items-center gap-1"><span className="w-2 h-0.5 bg-blue-500" /> {sym1}</span>
        <span className="flex items-center gap-1"><span className="w-2 h-0.5 bg-amber-500" /> {sym2}</span>
        <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-amber-400" /> Entry</span>
        <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-purple-500" /> Exit</span>
      </div>
    </div>
  );
}


/* Backtest charts: spread + z-score with entry/exit markers, equity curve */
function BacktestCharts({ spreadSeries, markers, equityCurve }) {
  const scatterData = markers.map(m => ({
    date: m.date,
    spread: m.spread,
    markerType: m.type,
    side: m.side,
    pnl: m.pnl_pct,
  }));

  const hasSpreadData = spreadSeries.length > 0;
  const hasEquityData = equityCurve?.length > 1;

  return (
    <div className="grid grid-cols-1 xl:grid-cols-2 gap-2">
      {hasSpreadData && (
        <div>
          <h5 className="text-[8px] font-semibold text-zinc-600 uppercase tracking-wider mb-1">Spread & Z-Score</h5>
          <div className="h-28 bg-zinc-950 rounded-lg p-1 border border-zinc-800 min-w-0">
            <ResponsiveContainer width="100%" height="100%" minWidth={0}>
              <LineChart data={spreadSeries}>
                <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fill: "#52525b", fontSize: 7 }} tickFormatter={(v) => v?.slice(5) || ""} interval="preserveStartEnd" />
                <YAxis yAxisId="left" axisLine={false} tickLine={false} tick={{ fill: "#52525b", fontSize: 7 }} domain={["auto", "auto"]} width={36} />
                <YAxis yAxisId="right" orientation="right" axisLine={false} tickLine={false} tick={{ fill: "#52525b", fontSize: 7 }} domain={[-4, 4]} width={26} />
                <Tooltip content={<BTCustomTooltip />} />
                <ReferenceLine y={2} yAxisId="right" stroke="#ef4444" strokeDasharray="2 2" strokeWidth={0.5} />
                <ReferenceLine y={-2} yAxisId="right" stroke="#22c55e" strokeDasharray="2 2" strokeWidth={0.5} />
                <ReferenceLine y={0} yAxisId="right" stroke="#52525b" strokeDasharray="1 1" strokeWidth={0.5} />
                <Line yAxisId="left" type="monotone" dataKey="spread" stroke="#3b82f6" strokeWidth={1} dot={false} name="Spread" />
                <Line yAxisId="right" type="monotone" dataKey="zscore" stroke="#a855f7" strokeWidth={0.5} dot={false} name="Z-Score" />
                <Scatter yAxisId="left" data={scatterData.filter(m => m.markerType === 'entry')} dataKey="spread" fill="#f59e0b" r={3} name="Entry" />
                <Scatter yAxisId="left" data={scatterData.filter(m => m.markerType === 'exit')} dataKey="spread" fill="#10b981" r={2} name="Exit" />
              </LineChart>
            </ResponsiveContainer>
          </div>
          <div className="flex flex-wrap gap-2 mt-0.5 text-[7px] text-zinc-600">
            <span className="flex items-center gap-1"><span className="w-2 h-0.5 bg-blue-500" /> Spread</span>
            <span className="flex items-center gap-1"><span className="w-2 h-0.5 bg-purple-500" /> Z-Score</span>
            <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-amber-400" /> Entry</span>
            <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-emerald-400" /> Exit</span>
            <span className="flex items-center gap-1"><span className="w-2 h-0.5 bg-red-500" /> +2σ</span>
            <span className="flex items-center gap-1"><span className="w-2 h-0.5 bg-green-500" /> -2σ</span>
          </div>
        </div>
      )}
      {hasEquityData && (
        <div>
          <h5 className="text-[8px] font-semibold text-zinc-600 uppercase tracking-wider mb-1">Equity Curve</h5>
          <div className="h-28 bg-zinc-950 rounded-lg p-1 border border-zinc-800 min-w-0">
            <ResponsiveContainer width="100%" height="100%" minWidth={0}>
              <AreaChart data={equityCurve}>
                <defs><linearGradient id="eqGrad2" x1="0" y1="0" x2="0" y2="1"><stop offset="5%" stopColor="#a855f7" stopOpacity={0.15} /><stop offset="95%" stopColor="#a855f7" stopOpacity={0} /></linearGradient></defs>
                <XAxis dataKey="date" axisLine={false} tickLine={false} tick={{ fill: "#52525b", fontSize: 7 }} tickFormatter={(v) => v?.slice(5) || ""} interval="preserveStartEnd" />
                <YAxis axisLine={false} tickLine={false} tick={{ fill: "#52525b", fontSize: 7 }} domain={["auto", "auto"]} width={36} tickFormatter={(v) => v.toFixed(0)} />
                <Tooltip content={<BTCustomTooltip />} />
                <ReferenceLine y={100} stroke="#52525b" strokeDasharray="1 1" strokeWidth={0.5} />
                <Area type="monotone" dataKey="equity" stroke="#a855f7" strokeWidth={1.5} fill="url(#eqGrad2)" dot={false} name="Equity" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
      {!hasSpreadData && !hasEquityData && (
        <div className="col-span-1 xl:col-span-2 text-center py-4 text-[9px] text-zinc-600">
          No chart data available — insufficient observations
        </div>
      )}
    </div>
  );
}

function BTCustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-zinc-900 border border-zinc-700 rounded-lg px-2 py-1 text-[9px] shadow-xl">
      <p className="text-zinc-400 mb-0.5">{label}</p>
      {payload.map((entry, i) => (
        <p key={i} style={{ color: entry.color }}>
          {entry.name}: {typeof entry.value === "number" ? entry.value.toFixed(4) : entry.value}
        </p>
      ))}
    </div>
  );
}

/* ════════════════════════════════════════════════
   Column Tooltip — uses shadcn/Radix portal so it's never clipped by overflow
   ════════════════════════════════════════════════ */

function ColumnTooltip({ tip }) {
  return (
    <ShadcnTooltip delayDuration={200}>
      <TooltipTrigger asChild>
        <span className="inline-flex items-center cursor-help">
          <HelpCircle className="w-2.5 h-2.5 text-zinc-700 hover:text-zinc-400 transition-colors" />
        </span>
      </TooltipTrigger>
      <TooltipContent side="top" align="center" className="max-w-56 bg-zinc-800 border-zinc-700 text-zinc-300 text-[10px] leading-relaxed">
        {tip}
      </TooltipContent>
    </ShadcnTooltip>
  );
}

/* ════════════════════════════════════════════════
   Correlation Explainer — professional intro for non-traders
   ════════════════════════════════════════════════ */

function CorrelationExplainer({ onClose }) {
  const [activeSection, setActiveSection] = useState(null);

  const sections = [
    {
      id: "what",
      title: "What is Correlation Analysis?",
      content: (
        <div className="space-y-2 text-zinc-400">
          <p>
            Correlation analysis measures how two stocks move relative to each other. When one stock goes up, does the
            other tend to go up too — or down? This is expressed as a <strong className="text-zinc-200">correlation coefficient</strong>{' '}
            from <strong className="text-green-400">+100%</strong> (perfectly together) to{' '}
            <strong className="text-red-400">-100%</strong> (perfectly opposite).
          </p>
          <p>
            Think of it like two dancers: some pairs move in perfect sync, some move in opposite directions,
            and some seem to dance independently.
          </p>
        </div>
      ),
    },
    {
      id: "how",
      title: "How to Use This Page",
      content: (
        <div className="space-y-2 text-zinc-400">
          <p>
            This page shows the <strong className="text-zinc-200">best trading opportunities</strong> from all 1,225
            Nifty 50 stock pairs, ranked by Portfolio Variance Reduction (PVR) score.
          </p>
          <ul className="space-y-1.5 list-disc list-inside">
            <li><strong className="text-zinc-300">Score (0-100):</strong> How much risk is eliminated by pairing these two stocks. 70+ = strong.</li>
            <li><strong className="text-zinc-300">Signal:</strong> Tells you what to do — BUY/SELL for spread mode, BUY BOTH for hedge mode.</li>
            <li><strong className="text-zinc-300">Z-Score:</strong> Current deviation from mean. |z| &gt; 2 = entry opportunity.</li>
            <li><strong className="text-zinc-300">Sharpe/Return/Win%:</strong> Pre-computed backtest metrics (cached on backend, 30-min refresh).</li>
            <li><strong className="text-zinc-300">Click any row</strong> to expand and see detailed backtest charts, trade log, and entry/stop levels.</li>
          </ul>
        </div>
      ),
    },
  ];

  return (
    <div className="bg-gradient-to-br from-zinc-900 via-zinc-900/95 to-blue-950/20 border border-blue-800/30 rounded-xl overflow-hidden shadow-lg mb-3">
      <div className="flex items-center justify-between px-4 py-3 border-b border-zinc-800">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-blue-500/15 flex items-center justify-center">
            <Info className="w-4 h-4 text-blue-400" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-zinc-100">Understanding Correlation Analysis</h3>
            <p className="text-[10px] text-zinc-500">A beginner-friendly guide to reading this page</p>
          </div>
        </div>
        <button onClick={onClose} className="p-1.5 rounded-lg hover:bg-zinc-800 text-zinc-500 hover:text-zinc-300 transition-colors" title="Close">
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
      <div className="divide-y divide-zinc-800/50">
        {sections.map((section) => (
          <div key={section.id}>
            <button
              onClick={() => setActiveSection(activeSection === section.id ? null : section.id)}
              className="w-full flex items-center justify-between px-4 py-2.5 text-left hover:bg-zinc-800/30 transition-colors"
            >
              <span className="text-xs font-medium text-zinc-200">{section.title}</span>
              <ChevronDown className={`w-3.5 h-3.5 text-zinc-600 transition-transform duration-200 ${activeSection === section.id ? "rotate-180" : ""}`} />
            </button>
            {activeSection === section.id && (
              <div className="px-4 pb-3 text-[11px] leading-relaxed">{section.content}</div>
            )}
          </div>
        ))}
      </div>
      <div className="px-4 py-2.5 bg-zinc-900/60 border-t border-zinc-800/50">
        <p className="text-[9px] text-zinc-600 uppercase tracking-wider mb-1.5">Quick Reference</p>
        <div className="flex flex-wrap gap-1.5">
          <span className="text-[9px] px-1.5 py-0.5 rounded bg-green-500/10 text-green-400 border border-green-800/30">↑ B/S = Pairs trade</span>
          <span className="text-[9px] px-1.5 py-0.5 rounded bg-yellow-500/10 text-yellow-400 border border-yellow-800/30">⊕ Buy both = Hedge</span>
          <span className="text-[9px] px-1.5 py-0.5 rounded bg-orange-500/10 text-orange-400 border border-orange-800/30">|z| &gt; 2 = Entry</span>
          <span className="text-[9px] px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-400 border border-purple-800/30">Score ≥ 70 = Strong</span>
          <span className="text-[9px] px-1.5 py-0.5 rounded bg-cyan-500/10 text-cyan-400 border border-cyan-800/30">Data cached 30 min</span>
        </div>
      </div>
    </div>
  );
}
