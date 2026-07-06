import { useState, useEffect, useCallback, useMemo } from "react";
import axios from "axios";
import { API } from "../App";
import {
  Activity, RefreshCw, TrendingUp, TrendingDown,
  Award, Target, Filter, ChevronDown, ChevronRight,
  BarChart3, AlertCircle, Search, List, ArrowRight
} from "lucide-react";
import { toast } from "sonner";

import CorrelationPairDetail from "../components/CorrelationPairDetail";

const ALL_TIMEFRAMES = [5, 10, 20, 60, 126, 252];

const TABS = [
  { id: "correlation-list", label: "Correlation List", icon: List },
  { id: "ranking-signals", label: "Ranking & Signals", icon: Award },
];

function getSignalIcon(signal) {
  if (signal === "LONG_SPREAD") return <TrendingUp className="w-3.5 h-3.5 text-green-400" />;
  if (signal === "SHORT_SPREAD") return <TrendingDown className="w-3.5 h-3.5 text-red-400" />;
  return <Activity className="w-3.5 h-3.5 text-zinc-500" />;
}

export default function CorrelationAnalysis() {
  const [activeTab, setActiveTab] = useState("correlation-list");

  // ── Tab 1: Correlation List state ──
  const [allPairsData, setAllPairsData] = useState(null);
  const [listLoading, setListLoading] = useState(false);
  const [listError, setListError] = useState(null);
  const [listFilter, setListFilter] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");

  // ── Tab 2: Ranking & Signals state ──
  const [rankingsData, setRankingsData] = useState(null);
  const [rankingsLoading, setRankingsLoading] = useState(false);
  const [optimalParams, setOptimalParams] = useState(null);
  const [optParamsLoading, setOptParamsLoading] = useState(false);
  const [sectorFilter, setSectorFilter] = useState("all");
  const [signalFilter, setSignalFilter] = useState("all");
  const [scoreFilter, setScoreFilter] = useState("all");
  const [sortBy, setSortBy] = useState("score");

  // ── Selected pair (for inline analysis + backtest) ──
  const [selectedPair, setSelectedPair] = useState(null);
  const [pairDetail, setPairDetail] = useState(null);
  const [pairLoading, setPairLoading] = useState(false);
  const [pairDismissed, setPairDismissed] = useState(false);

  // ── Data fetching ──

  const fetchAllPairs = useCallback(async () => {
    setListLoading(true);
    setListError(null);
    try {
      const res = await axios.get(`${API}/correlation/pair-rankings`, {
        params: { max_days: 252, include_all: true },
        timeout: 120000,
      });
      setAllPairsData(res.data);
    } catch (err) {
      setListError(err.response?.data?.detail || err.message || "Failed to load correlation list");
      toast.error("Failed to load correlation list.");
    } finally {
      setListLoading(false);
    }
  }, []);

  const fetchRankings = useCallback(async () => {
    setRankingsLoading(true);
    try {
      const [rankRes, paramsRes] = await Promise.all([
        axios.get(`${API}/correlation/pair-rankings`, { params: { max_days: 252 }, timeout: 120000 }),
        axios.get(`${API}/correlation/optimal-params`, { params: { max_days: 252 }, timeout: 120000 }),
      ]);
      setRankingsData(rankRes.data);
      setOptimalParams(paramsRes.data);
    } catch (err) {
      toast.error("Failed to load pair rankings.");
    } finally {
      setRankingsLoading(false);
    }
  }, []);

  useEffect(() => { fetchAllPairs(); }, [fetchAllPairs]);
  useEffect(() => { if (activeTab === "ranking-signals") fetchRankings(); }, [activeTab, fetchRankings]);

  // ── Handler: select a pair → load detail inline in Tab 2 ──

  const handleSelectPair = async (sym1, sym2) => {
    setSelectedPair({ sym1, sym2 });
    setPairLoading(true);
    setPairDetail(null);
    setPairDismissed(false);
    setActiveTab("ranking-signals");
    try {
      const res = await axios.get(`${API}/correlation/pair/${sym1}/${sym2}`, {
        params: { timeframe: 60 },
        timeout: 60000,
      });
      setPairDetail(res.data);
    } catch (err) {
      toast.error(`Failed to load pair analysis: ${err.message}`);
    } finally {
      setPairLoading(false);
    }
  };

  const handleDismissPair = () => {
    setSelectedPair(null);
    setPairDetail(null);
    setPairDismissed(true);
  };

  // ── Filtered / searched pairs for the Correlation List ──

  const displayedPairs = useMemo(() => {
    if (!allPairsData?.all_pairs) return [];
    let filtered = allPairsData.all_pairs;

    // Sector filter
    if (listFilter !== "all") {
      filtered = filtered.filter(
        p => p.sym1_sector === listFilter || p.sym2_sector === listFilter
      );
    }

    // Search
    if (searchQuery.trim()) {
      const q = searchQuery.toUpperCase();
      filtered = filtered.filter(
        p => p.sym1.includes(q) || p.sym2.includes(q)
      );
    }

    return filtered.slice(0, 200); // Show top 200 pairs
  }, [allPairsData, listFilter, searchQuery]);

  // ── Helper: unique sectors from all pairs ──

  const allSectors = useMemo(() => {
    if (!allPairsData?.all_pairs) return [];
    const set = new Set();
    for (const p of allPairsData.all_pairs) {
      if (p.sym1_sector) set.add(p.sym1_sector);
      if (p.sym2_sector) set.add(p.sym2_sector);
    }
    return Array.from(set).sort();
  }, [allPairsData]);

  // ── Render ──

  return (
    <div className="page-container" data-testid="correlation-page">
      {/* Header */}
      <div className="page-header flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="page-title flex items-center gap-3">
            <Activity className="w-6 h-6 text-blue-500" />
            Correlation Analysis
          </h1>
          <p className="page-subtitle">
            Find stock pairs that move together — identify mean reversion & pairs trading opportunities
          </p>
        </div>
      </div>

      {/* Tab bar — only 2 tabs */}
      <div className="flex gap-1 mb-4 border-b border-zinc-800 pb-2">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-t transition-all ${
              activeTab === tab.id
                ? "bg-zinc-800 text-zinc-200 border-b-2 border-blue-500"
                : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50"
            }`}
          >
            <tab.icon className="w-3.5 h-3.5" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* ════════════════════════════════════════════
          TAB 1: CORRELATION LIST
          ════════════════════════════════════════════ */}
      {activeTab === "correlation-list" && (
        <div className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 className="text-sm font-semibold text-zinc-200 flex items-center gap-2">
                <List className="w-4 h-4 text-blue-400" />
                All Pairs — Multi-Timeframe Correlation
              </h2>
              <p className="text-[11px] text-zinc-500 mt-0.5">
                {allPairsData?.total_pairs?.toLocaleString() || "—"} pairs scanned · Click any row to analyze
              </p>
            </div>
            <button
              onClick={fetchAllPairs}
              disabled={listLoading}
              className="flex items-center gap-1 text-[10px] px-2.5 py-1.5 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200 transition-colors"
            >
              <RefreshCw className={`w-3 h-3 ${listLoading ? "animate-spin" : ""}`} />
              Refresh
            </button>
          </div>

          {/* Filters */}
          <div className="flex flex-wrap items-center gap-2 text-[10px]">
            <Filter className="w-3 h-3 text-zinc-500" />
            <span className="text-zinc-600 uppercase tracking-wider font-semibold">Filter:</span>

            {/* Sector */}
            <select
              value={listFilter}
              onChange={e => setListFilter(e.target.value)}
              className="bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-zinc-300 text-[10px] cursor-pointer"
            >
              <option value="all">All Sectors</option>
              {allSectors.map(s => (
                <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>
              ))}
            </select>

            {/* Search */}
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

          {/* Loading */}
          {listLoading && (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full mr-3" />
              <span className="text-sm text-zinc-400">Computing correlations for all 1225 pairs...</span>
            </div>
          )}

          {/* Error */}
          {listError && !listLoading && (
            <div className="bg-red-900/20 border border-red-800/30 rounded-lg p-4 text-sm text-red-400">
              {listError}
              <button onClick={fetchAllPairs} className="ml-3 underline hover:text-red-300">Retry</button>
            </div>
          )}

          {/* Table */}
          {allPairsData && !listLoading && (
            <div className="overflow-x-auto rounded-lg border border-zinc-800">
              <table className="w-full text-[10px] font-mono">
                <thead>
                  <tr className="bg-zinc-900 text-zinc-500 uppercase tracking-wider border-b border-zinc-800">
                    <th className="text-left py-2 px-2 font-semibold sticky left-0 bg-zinc-900 z-10">#</th>
                    <th className="text-left py-2 px-2 font-semibold sticky left-[24px] bg-zinc-900 z-10">Pair</th>
                    <th className="text-left py-2 px-2 font-semibold">Sector</th>
                    {ALL_TIMEFRAMES.map(tf => (
                      <th key={tf} className="text-right py-2 px-1.5 font-semibold">{tf}d</th>
                    ))}
                    <th className="text-right py-2 px-1.5 font-semibold">Avg</th>
                    <th className="text-right py-2 px-1.5 font-semibold">Cst%</th>
                    <th className="text-center py-2 px-1.5 font-semibold">Coint</th>
                    <th className="text-right py-2 px-1.5 font-semibold">HL</th>
                    <th className="text-right py-2 px-1.5 font-semibold">Score</th>
                    <th className="text-center py-2 px-2 font-semibold">Signal</th>
                    <th className="py-2 px-2" />
                  </tr>
                </thead>
                <tbody>
                  {displayedPairs.map((p, idx) => {
                    const sameSector = p.sym1_sector === p.sym2_sector;
                    const hasSignal = p.signal === "LONG_SPREAD" || p.signal === "SHORT_SPREAD";
                    return (
                      <tr
                        key={`${p.sym1}-${p.sym2}`}
                        onClick={() => handleSelectPair(p.sym1, p.sym2)}
                        className={`border-b border-zinc-800/30 transition-colors cursor-pointer ${
                          idx % 2 === 0 ? "bg-zinc-900/30" : "bg-transparent"
                        } hover:bg-zinc-800/40`}
                      >
                        <td className="py-1.5 px-2 text-zinc-600 sticky left-0 bg-inherit z-10">{idx + 1}</td>
                        <td className="py-1.5 px-2 sticky left-[24px] bg-inherit z-10">
                          <span className="font-semibold text-blue-400">{p.sym1}</span>
                          <span className="text-zinc-700 mx-0.5">/</span>
                          <span className="font-semibold text-orange-400">{p.sym2}</span>
                        </td>
                        <td className="py-1.5 px-2 text-zinc-500 text-[9px]">
                          {sameSector
                            ? <span className="text-zinc-500">{p.sym1_sector?.replace(/_/g, ' ')}</span>
                            : <span className="text-yellow-600">Cross</span>
                          }
                        </td>
                        {ALL_TIMEFRAMES.map(tf => {
                          const corr = p.correlations?.[`${tf}d`];
                          const isDefined = corr !== undefined && corr !== null;
                          return (
                            <td key={tf} className={`py-1.5 px-1.5 text-right ${
                              isDefined
                                ? Math.abs(corr) > 0.7 ? 'text-green-400'
                                  : Math.abs(corr) > 0.4 ? 'text-yellow-400'
                                  : 'text-zinc-500'
                                : 'text-zinc-700'
                            }`}>
                              {isDefined ? `${corr >= 0 ? '+' : ''}${(corr * 100).toFixed(0)}%` : '—'}
                            </td>
                          );
                        })}
                        <td className={`py-1.5 px-1.5 text-right ${
                          p.avg_abs_corr > 0.7 ? 'text-green-400'
                            : p.avg_abs_corr > 0.4 ? 'text-yellow-400'
                            : 'text-zinc-500'
                        }`}>
                          {(p.avg_abs_corr * 100).toFixed(0)}%
                        </td>
                        <td className={`py-1.5 px-1.5 text-right ${
                          p.consistency > 0.7 ? 'text-green-400'
                            : p.consistency > 0.5 ? 'text-yellow-400'
                            : 'text-red-400'
                        }`}>
                          {(p.consistency * 100).toFixed(0)}%
                        </td>
                        <td className="py-1.5 px-1.5 text-center">
                          {p.cointegrated
                            ? <span className="text-green-400 text-[11px]">✓</span>
                            : <span className="text-zinc-600">—</span>
                          }
                        </td>
                        <td className="py-1.5 px-1.5 text-right text-zinc-500">
                          {p.half_life_days > 0 && p.half_life_days < 999 ? `${p.half_life_days.toFixed(0)}d` : '—'}
                        </td>
                        <td className={`py-1.5 px-1.5 text-right font-bold ${
                          p.score >= 70 ? 'text-green-400'
                            : p.score >= 50 ? 'text-yellow-400'
                            : p.score >= 30 ? 'text-orange-400'
                            : 'text-red-400'
                        }`}>
                          {p.score}
                        </td>
                        <td className="py-1.5 px-2 text-center">
                          {hasSignal ? (
                            <span className={`inline-flex items-center gap-0.5 text-[9px] px-1 py-0.5 rounded font-bold ${
                              p.signal === "LONG_SPREAD"
                                ? "bg-green-500/10 text-green-400"
                                : "bg-red-500/10 text-red-400"
                            }`}>
                              {p.signal === "LONG_SPREAD" ? "↑" : "↓"}
                            </span>
                          ) : (
                            <span className="text-zinc-700">—</span>
                          )}
                        </td>
                        <td className="py-1.5 px-2 text-zinc-600">
                          <ArrowRight className="w-3 h-3" />
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
              {displayedPairs.length === 0 && !listLoading && (
                <div className="text-center py-8 text-zinc-600 text-xs">No pairs match the current filters</div>
              )}
              {allPairsData?.all_pairs?.length > 200 && (
                <div className="text-center py-2 text-[9px] text-zinc-600 border-t border-zinc-800/50">
                  Showing top 200 of {allPairsData.all_pairs.length.toLocaleString()} pairs — use filters to narrow down
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ════════════════════════════════════════════
          TAB 2: RANKING & SIGNALS
          ════════════════════════════════════════════ */}
      {activeTab === "ranking-signals" && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-sm font-semibold text-zinc-200 flex items-center gap-2">
                <Award className="w-4 h-4 text-yellow-400" />
                Ranking & Signals
              </h2>
              <p className="text-[11px] text-zinc-500 mt-0.5">
                Top-ranked pairs with live signals, entry/stop levels, and one-click backtest
              </p>
            </div>
            <button
              onClick={fetchRankings}
              disabled={rankingsLoading}
              className="flex items-center gap-1 text-[10px] px-2.5 py-1.5 rounded bg-zinc-800 hover:bg-zinc-700 text-zinc-400 hover:text-zinc-200 transition-colors"
            >
              <RefreshCw className={`w-3 h-3 ${rankingsLoading ? "animate-spin" : ""}`} />
              Refresh
            </button>
          </div>

          {rankingsLoading && (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin w-5 h-5 border-2 border-yellow-500 border-t-transparent rounded-full mr-3" />
              <span className="text-sm text-zinc-400">Computing rankings for all 1225 pairs... This may take a moment.</span>
            </div>
          )}

          {!rankingsData && !rankingsLoading && (
            <div className="text-center py-12 text-zinc-600 text-xs">
              Click <strong>Ranking & Signals</strong> tab to load data
            </div>
          )}

          {rankingsData && !rankingsLoading && (
            <>
              {/* ── How to Use Section ── */}
              <RankingsExplainer />

              {/* ── Optimal Parameters Card ── */}
              {optimalParams && !optParamsLoading && !optimalParams.error && (
                <div className="bg-gradient-to-r from-purple-900/20 to-blue-900/20 border border-purple-800/30 rounded-xl p-3 sm:p-4">
                  <div className="flex items-center gap-2 mb-2">
                    <Target className="w-4 h-4 text-purple-400" />
                    <h3 className="text-xs font-semibold text-zinc-200">Recommended Strategy Parameters</h3>
                  </div>
                  <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
                    <ParamDisplay label="Entry Z-Score" value={optimalParams.recommended_params.entry_z} highlight />
                    <ParamDisplay label="Exit Z-Score" value={optimalParams.recommended_params.exit_z} />
                    <ParamDisplay label="Stop Z-Score" value={optimalParams.recommended_params.stop_z} highlight />
                    <ParamDisplay label="Rolling Window" value={`${optimalParams.recommended_params.rolling_window}d`} />
                    <ParamDisplay label="Hedge Ratio" value={optimalParams.recommended_params.use_hedge_ratio ? "ON" : "OFF"} highlight />
                  </div>
                  <div className="mt-2 text-[10px] text-zinc-600">
                    Based on grid search across top {optimalParams.pairs_used?.length || 0} pairs
                  </div>
                  {optimalParams?.param_details && (
                    <details className="group mt-1">
                      <summary className="text-[10px] text-zinc-600 cursor-pointer hover:text-zinc-400 transition-colors">
                        View parameter comparison details
                      </summary>
                      <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                        {Object.entries(optimalParams.param_details).map(([key, data]) => (
                          <div key={key} className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-2">
                            <div className="text-[9px] text-zinc-500 uppercase tracking-wider mb-1">{key.replace(/_/g, ' ')}</div>
                            {data.tested_values.map((v, i) => (
                              <div key={i} className={`flex items-center justify-between text-[10px] font-mono px-1.5 py-0.5 rounded ${
                                v.value === data.best_value ? "bg-green-900/20 text-green-400" : "text-zinc-400"
                              }`}>
                                <span>{String(v.value)}</span>
                                <span>Sharpe: {v.avg_sharpe > -999 ? v.avg_sharpe.toFixed(2) : 'N/A'}</span>
                              </div>
                            ))}
                          </div>
                        ))}
                      </div>
                    </details>
                  )}
                </div>
              )}

              {/* ── Filter Bar ── */}
              <RankingFilterBar
                data={rankingsData}
                sectorFilter={sectorFilter}
                setSectorFilter={setSectorFilter}
                signalFilter={signalFilter}
                setSignalFilter={setSignalFilter}
                scoreFilter={scoreFilter}
                setScoreFilter={setScoreFilter}
                sortBy={sortBy}
                setSortBy={setSortBy}
              />

              {/* ── Best 10 Trade Cards ── */}
              <div>
                <h3 className="text-xs font-semibold text-green-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                  <TrendingUp className="w-3.5 h-3.5" />
                  Best 10 Pairs for Trading
                  <span className="text-zinc-600 text-[9px] font-normal normal-case">
                    — Highest composite score
                  </span>
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  {getFilteredPairs(rankingsData.best_10, sectorFilter, signalFilter, scoreFilter, sortBy).map((p, idx) => (
                    <TradeSetupCard
                      key={`${p.sym1}-${p.sym2}`}
                      pair={p}
                      rank={idx + 1}
                      onSelectPair={handleSelectPair}
                      timeframes={rankingsData.timeframes}
                    />
                  ))}
                </div>
                {getFilteredPairs(rankingsData.best_10, sectorFilter, signalFilter, scoreFilter, sortBy).length === 0 && (
                  <div className="text-center py-8 text-zinc-600 text-xs">No pairs match the current filters</div>
                )}
              </div>

              {/* ── Worst 10 Trade Cards ── */}
              <div>
                <h3 className="text-xs font-semibold text-red-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                  <TrendingDown className="w-3.5 h-3.5" />
                  Worst 10 Pairs (Negative Correlation)
                  <span className="text-zinc-600 text-[9px] font-normal normal-case">
                    — Useful for hedging or inverse trading
                  </span>
                </h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  {getFilteredPairs(rankingsData.worst_10, sectorFilter, signalFilter, scoreFilter, sortBy).map((p, idx) => (
                    <TradeSetupCard
                      key={`${p.sym1}-${p.sym2}`}
                      pair={p}
                      rank={idx + 1}
                      onSelectPair={handleSelectPair}
                      timeframes={rankingsData.timeframes}
                      negative
                    />
                  ))}
                </div>
                {getFilteredPairs(rankingsData.worst_10, sectorFilter, signalFilter, scoreFilter, sortBy).length === 0 && (
                  <div className="text-center py-8 text-zinc-600 text-xs">No pairs match the current filters</div>
                )}
              </div>

              <div className="text-[10px] text-zinc-600 text-center pt-2">
                {rankingsData.total_pairs} pairs analyzed · {rankingsData.best_10.filter(p => p.signal === 'LONG_SPREAD' || p.signal === 'SHORT_SPREAD').length} have active signals
              </div>

              {/* ── Inline Pair Detail + Backtest ── */}
              {pairLoading && (
                <div className="bg-zinc-900/80 border border-zinc-700/50 rounded-xl p-8 flex items-center justify-center">
                  <div className="animate-spin w-5 h-5 border-2 border-purple-500 border-t-transparent rounded-full mr-3" />
                  <span className="text-sm text-zinc-400">Loading {selectedPair?.sym1}/{selectedPair?.sym2} analysis...</span>
                </div>
              )}
              {pairDetail && !pairDetail.error && !pairDismissed && (
                <div className="relative">
                  <CorrelationPairDetail pair={pairDetail} onClose={handleDismissPair} />
                </div>
              )}
              {pairDetail?.error && (
                <div className="bg-yellow-900/20 border border-yellow-800/30 rounded-lg p-4 text-sm text-yellow-400">{pairDetail.error}</div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

/* ════════════════════════════════════════════════
   Filter Helpers
   ════════════════════════════════════════════════ */

function getFilteredPairs(pairs, sector, signal, score, sort) {
  let filtered = [...pairs];

  if (sector !== "all") {
    filtered = filtered.filter(p =>
      p.sym1_sector === sector || p.sym2_sector === sector
    );
  }

  if (signal !== "all") {
    filtered = filtered.filter(p => p.signal === signal);
  }

  if (score === "70") filtered = filtered.filter(p => p.score >= 70);
  else if (score === "50") filtered = filtered.filter(p => p.score >= 50);
  else if (score === "30") filtered = filtered.filter(p => p.score >= 30);

  if (sort === "score") filtered.sort((a, b) => b.score - a.score);
  else if (sort === "zscore") filtered.sort((a, b) => Math.abs(b.z_score || 0) - Math.abs(a.z_score || 0));
  else if (sort === "hl") filtered.sort((a, b) => (a.half_life_days || 999) - (b.half_life_days || 999));
  else if (sort === "corr") filtered.sort((a, b) => Math.abs(b.avg_abs_corr || 0) - Math.abs(a.avg_abs_corr || 0));

  return filtered;
}

function extractAllSectors(pairs) {
  const set = new Set();
  for (const p of pairs || []) {
    if (p.sym1_sector) set.add(p.sym1_sector);
    if (p.sym2_sector) set.add(p.sym2_sector);
  }
  return Array.from(set).sort();
}

/* ════════════════════════════════════════════════
   Rankings Explainer
   ════════════════════════════════════════════════ */

function RankingsExplainer() {
  return (
    <details open className="group bg-zinc-900/40 border border-zinc-800/60 rounded-lg">
      <summary className="flex items-center gap-1.5 text-xs text-zinc-500 cursor-pointer hover:text-zinc-300 transition-colors p-3">
        <AlertCircle className="w-3.5 h-3.5" />
        How to use this page — pick your trade setup
        <span className="text-zinc-700 group-open:hidden"> — click to expand</span>
      </summary>
      <div className="px-3 pb-3 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2 text-[10px] text-zinc-400">
        <div className="bg-zinc-900/50 rounded-lg p-2.5">
          <div className="flex items-center gap-1.5 mb-1">
            <span className="text-green-400 font-bold text-[11px]">①</span>
            <strong className="text-zinc-200">Check the live signal</strong>
          </div>
          <p>Each card shows its current z-score. <span className="text-green-400">LONG SPREAD</span> (z &lt; -2) = spread is oversold, <span className="text-red-400">SHORT SPREAD</span> (z &gt; 2) = overbought. <span className="text-zinc-500">NEUTRAL</span> = no signal right now.</p>
        </div>
        <div className="bg-zinc-900/50 rounded-lg p-2.5">
          <div className="flex items-center gap-1.5 mb-1">
            <span className="text-green-400 font-bold text-[11px]">②</span>
            <strong className="text-zinc-200">Check cointegration & half-life</strong>
          </div>
          <p><span className="text-green-400">✓ Cointegrated</span> = pair reliably mean-reverts. <strong>Half-life</strong> &lt; 20d = fast reversion. 20-60d = slower but tradeable.</p>
        </div>
        <div className="bg-zinc-900/50 rounded-lg p-2.5">
          <div className="flex items-center gap-1.5 mb-1">
            <span className="text-green-400 font-bold text-[11px]">③</span>
            <strong className="text-zinc-200">Set entry & stop levels</strong>
          </div>
          <p>Use the recommended params above. <strong>Entry</strong> = buy/sell when ratio hits entry level. <strong>Stop</strong> = exit if ratio breaks the stop level. <strong>Target</strong> = exit when z-score returns to 0.</p>
        </div>
        <div className="bg-zinc-900/50 rounded-lg p-2.5">
          <div className="flex items-center gap-1.5 mb-1">
            <span className="text-green-400 font-bold text-[11px]">④</span>
            <strong className="text-zinc-200">Backtest & refine</strong>
          </div>
          <p>Click a card to expand trade levels, then <strong className="text-blue-400">Analyze</strong> to see charts, or use the <strong className="text-purple-400">backtest panel</strong> below to test the strategy before trading real money.</p>
        </div>
        <div className="sm:col-span-2 lg:col-span-4 flex items-start gap-2 bg-zinc-900/50 rounded-lg p-2.5">
          <BarChart3 className="w-4 h-4 text-zinc-500 flex-shrink-0 mt-0.5" />
          <div className="text-zinc-500">
            <strong className="text-zinc-300">Score breakdown:</strong>{' '}
            Score (0-100) = <span className="text-blue-400">Correlation (25 pts)</span> +{' '}
            <span className="text-yellow-400">Consistency (20 pts)</span> +{' '}
            <span className="text-green-400">Cointegration (35 pts)</span> +{' '}
            <span className="text-purple-400">Half-Life bonus (20 pts)</span>.{' '}
            Score &gt; 70 = highly tradeable. Look for pairs with <span className="text-green-400">active signals</span> (green/red badges) for the best setups right now.
          </div>
        </div>
      </div>
    </details>
  );
}

/* ════════════════════════════════════════════════
   Ranking Filter Bar
   ════════════════════════════════════════════════ */

function RankingFilterBar({ data, sectorFilter, setSectorFilter, signalFilter, setSignalFilter, scoreFilter, setScoreFilter, sortBy, setSortBy }) {
  const sectors = extractAllSectors(data?.best_10 || []);

  return (
    <div className="flex flex-wrap items-center gap-2 text-[10px]">
      <Filter className="w-3 h-3 text-zinc-500" />
      <span className="text-zinc-600 uppercase tracking-wider font-semibold">Filter:</span>

      <select
        value={sectorFilter}
        onChange={e => setSectorFilter(e.target.value)}
        className="bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-zinc-300 text-[10px] cursor-pointer"
      >
        <option value="all">All Sectors</option>
        {sectors.map(s => (
          <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>
        ))}
      </select>

      <select
        value={signalFilter}
        onChange={e => setSignalFilter(e.target.value)}
        className="bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-zinc-300 text-[10px] cursor-pointer"
      >
        <option value="all">All Signals</option>
        <option value="LONG_SPREAD">LONG SPREAD (oversold)</option>
        <option value="SHORT_SPREAD">SHORT SPREAD (overbought)</option>
        <option value="NEUTRAL">NEUTRAL (no signal)</option>
      </select>

      <select
        value={scoreFilter}
        onChange={e => setScoreFilter(e.target.value)}
        className="bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-zinc-300 text-[10px] cursor-pointer"
      >
        <option value="all">Any Score</option>
        <option value="70">Score ≥ 70</option>
        <option value="50">Score ≥ 50</option>
        <option value="30">Score ≥ 30</option>
      </select>

      <div className="flex items-center gap-1.5 ml-auto">
        <span className="text-zinc-600">Sort:</span>
        <select
          value={sortBy}
          onChange={e => setSortBy(e.target.value)}
          className="bg-zinc-800 border border-zinc-700 rounded px-2 py-1 text-zinc-300 text-[10px] cursor-pointer"
        >
          <option value="score">Score</option>
          <option value="zscore">Signal Strength</option>
          <option value="hl">Half-Life</option>
          <option value="corr">Correlation</option>
        </select>
      </div>
    </div>
  );
}

/* ════════════════════════════════════════════════
   Trade Setup Card
   ════════════════════════════════════════════════ */

function TradeSetupCard({ pair, rank, onSelectPair, timeframes, negative }) {
  const [expanded, setExpanded] = useState(false);
  const tfKeys = timeframes?.map(t => `${t}d`) || [];
  const p = pair;

  const signalColors = {
    LONG_SPREAD: { bg: "bg-green-500/10 border-green-500/30", text: "text-green-400", label: "BUY SPREAD", icon: "↑" },
    SHORT_SPREAD: { bg: "bg-red-500/10 border-red-500/30", text: "text-red-400", label: "SELL SPREAD", icon: "↓" },
    NEUTRAL: { bg: "bg-zinc-800/50 border-zinc-700/30", text: "text-zinc-400", label: "NEUTRAL", icon: "—" },
  };
  const sc = signalColors[p.signal] || signalColors.NEUTRAL;
  const hasSignal = p.signal !== "NEUTRAL";

  return (
    <div
      className={`rounded-lg border transition-all cursor-pointer ${
        hasSignal
          ? negative
            ? "bg-red-900/5 border-red-800/20 hover:border-red-700/40"
            : "bg-zinc-900/60 border-zinc-800 hover:border-zinc-700"
          : "bg-zinc-900/40 border-zinc-800/50 hover:border-zinc-700/60"
      }`}
    >
      <div className="p-2.5" onClick={() => setExpanded(!expanded)}>
        <div className="flex items-start justify-between gap-2">
          <div className="flex items-center gap-2 min-w-0">
            <span className="text-[9px] font-mono text-zinc-600 w-4 flex-shrink-0">#{rank}</span>
            <span className="text-xs font-semibold whitespace-nowrap">
              <span className="text-blue-400">{p.sym1}</span>
              <span className="text-zinc-700 mx-0.5">/</span>
              <span className="text-orange-400">{p.sym2}</span>
            </span>
            <span className={`text-[9px] px-1.5 py-0.5 rounded font-bold ${sc.bg} ${sc.text} border`}>
              {sc.icon} {sc.label}
            </span>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <span className={`text-[10px] font-bold font-mono ${
              p.score >= 70 ? 'text-green-400' :
              p.score >= 50 ? 'text-yellow-400' :
              'text-zinc-500'
            }`}>
              {p.score}
            </span>
            {expanded ? <ChevronDown className="w-3 h-3 text-zinc-600" /> : <ChevronRight className="w-3 h-3 text-zinc-600" />}
          </div>
        </div>

        <div className="flex items-center gap-2 mt-1 text-[10px] text-zinc-500">
          <span className={`font-mono font-semibold ${hasSignal ? sc.text : "text-zinc-500"}`}>
            z = {p.z_score?.toFixed(2)}
          </span>
          {p.cointegrated && <span className="text-green-600">✓ Cointegrated</span>}
          {p.half_life_days > 0 && p.half_life_days < 999 && (
            <span>HL: {p.half_life_days.toFixed(0)}d</span>
          )}
          <span className="text-zinc-700">·</span>
          <span>{p.sym1_sector?.replace(/_/g, ' ')} / {p.sym2_sector?.replace(/_/g, ' ')}</span>
        </div>
      </div>

      {expanded && (
        <div className="px-2.5 pb-2.5 space-y-2 border-t border-zinc-800/50 pt-2">
          <div className="grid grid-cols-3 gap-1.5">
            <div className="bg-zinc-900/80 rounded px-2 py-1.5 text-center">
              <div className="text-[8px] text-zinc-600 uppercase tracking-wider">Entry Level</div>
              <div className="font-mono text-[11px] font-bold text-blue-400">
                {p.signal === "LONG_SPREAD" ? p.entry_level_down?.toFixed(4) : p.entry_level_up?.toFixed(4)}
              </div>
              <div className="text-[8px] text-zinc-600">
                {p.signal === "LONG_SPREAD" ? "Buy when ratio ↓ here" : "Sell when ratio ↑ here"}
              </div>
            </div>
            <div className="bg-zinc-900/80 rounded px-2 py-1.5 text-center">
              <div className="text-[8px] text-zinc-600 uppercase tracking-wider">Target (Exit)</div>
              <div className="font-mono text-[11px] font-bold text-green-400">{p.mean_ratio?.toFixed(4)}</div>
              <div className="text-[8px] text-zinc-600">Exit when z-score ≈ 0</div>
            </div>
            <div className="bg-zinc-900/80 rounded px-2 py-1.5 text-center">
              <div className="text-[8px] text-zinc-600 uppercase tracking-wider">Stop Loss</div>
              <div className="font-mono text-[11px] font-bold text-red-400">
                {p.signal === "LONG_SPREAD" ? p.entry_level_up?.toFixed(4) : p.entry_level_down?.toFixed(4)}
              </div>
              <div className="text-[8px] text-zinc-600">Exit if ratio crosses here</div>
            </div>
          </div>

          <div className="flex flex-wrap gap-x-2 gap-y-0.5 text-[9px] text-zinc-600">
            <span className="text-zinc-500 uppercase tracking-wider">Corr:</span>
            {tfKeys.map(tf => {
              const corr = p.correlations?.[tf];
              const isDefined = corr !== undefined && corr !== null;
              return (
                <span key={tf} className={isDefined ? (
                  Math.abs(corr) > 0.7 ? 'text-green-400' :
                  Math.abs(corr) > 0.4 ? 'text-yellow-400' :
                  'text-zinc-500'
                ) : 'text-zinc-700'}>
                  {tf}: {isDefined ? `${corr >= 0 ? '+' : ''}${(corr * 100).toFixed(0)}%` : '—'}
                </span>
              );
            })}
            <span className="text-zinc-700">·</span>
            <span>Consistency: {(p.consistency * 100).toFixed(0)}%</span>
            <span className="text-zinc-700">·</span>
            <span>p-value: {p.coint_pvalue?.toFixed(4)}</span>
          </div>

          <div className="flex gap-1.5 pt-1">
            <button
              onClick={(e) => { e.stopPropagation(); onSelectPair(p.sym1, p.sym2); }}
              className="flex-1 text-[10px] py-1.5 rounded bg-blue-600/20 hover:bg-blue-600/30 text-blue-400 font-medium transition-colors"
            >
              Analyze & Backtest →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ════════════════════════════════════════════════
   Param Display
   ════════════════════════════════════════════════ */

function ParamDisplay({ label, value, highlight }) {
  return (
    <div className="bg-zinc-900/60 border border-zinc-800 rounded-lg px-2.5 py-1.5">
      <div className="text-[8px] text-zinc-500 uppercase tracking-wider mb-0.5">{label}</div>
      <div className={`font-mono text-sm font-bold ${highlight ? 'text-purple-300' : 'text-zinc-300'}`}>
        {String(value)}
      </div>
    </div>
  );
}
