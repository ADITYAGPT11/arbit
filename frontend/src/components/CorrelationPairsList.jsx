import { useState, useMemo } from "react";
import { ArrowUpDown, TrendingUp, TrendingDown, Minus } from "lucide-react";

const SECTOR_COLORS = {
  Financial_Services: "#3b82f6",
  IT: "#8b5cf6",
  Oil_Gas: "#f59e0b",
  FMCG: "#10b981",
  Auto: "#ef4444",
  Pharma: "#06b6d4",
  Metals: "#f97316",
  Power: "#14b8a6",
  Telecom: "#ec4899",
  Construction: "#6366f1",
  Consumer: "#eab308",
  Healthcare: "#84cc16",
  Media: "#a855f7",
};

function getCorrelationLabel(value) {
  const abs = Math.abs(value);
  if (abs >= 0.8) return { text: "Very strong", color: "text-green-400", bg: "bg-green-500/10" };
  if (abs >= 0.6) return { text: "Strong", color: "text-lime-400", bg: "bg-lime-500/10" };
  if (abs >= 0.4) return { text: "Moderate", color: "text-yellow-400", bg: "bg-yellow-500/10" };
  if (abs >= 0.2) return { text: "Weak", color: "text-orange-400", bg: "bg-orange-500/10" };
  return { text: "None", color: "text-zinc-500", bg: "bg-zinc-500/10" };
}

function getSignalIcon(corr, pair) {
  if (pair.z_score !== undefined) {
    if (Math.abs(pair.z_score) > 2) {
      return pair.z_score > 0 ? (
        <TrendingUp className="w-3 h-3 text-red-400" />
      ) : (
        <TrendingDown className="w-3 h-3 text-green-400" />
      );
    }
  }
  if (corr > 0.8) return <TrendingUp className="w-3 h-3 text-green-500" />;
  if (corr < 0.3) return <TrendingDown className="w-3 h-3 text-red-500" />;
  return <Minus className="w-3 h-3 text-zinc-500" />;
}

export default function CorrelationPairsList({
  pairs = [],
  onSelectPair,
  selectedPair,
  timeframeLabel,
  loading,
}) {
  const [sortBy, setSortBy] = useState("abs_corr");
  const [sortDir, setSortDir] = useState("desc");
  const [filter, setFilter] = useState("all");

  const filteredPairs = useMemo(() => {
    let result = [...pairs];

    if (filter === "same_sector") {
      result = result.filter((p) => p.same_sector);
    } else if (filter === "cross_sector") {
      result = result.filter((p) => !p.same_sector);
    }

    result.sort((a, b) => {
      const aVal = a[sortBy] || 0;
      const bVal = b[sortBy] || 0;
      return sortDir === "desc" ? bVal - aVal : aVal - bVal;
    });

    return result;
  }, [pairs, sortBy, sortDir, filter]);

  const toggleSort = (field) => {
    if (sortBy === field) {
      setSortDir((d) => (d === "desc" ? "asc" : "desc"));
    } else {
      setSortBy(field);
      setSortDir("desc");
    }
  };

  // Group by sector if requested
  const groupedPairs = useMemo(() => {
    if (filter === "same_sector") {
      const groups = {};
      for (const p of filteredPairs) {
        const sec = p.sym1_sector || "Other";
        if (!groups[sec]) groups[sec] = [];
        groups[sec].push(p);
      }
      return groups;
    }
    return null;
  }, [filteredPairs, filter]);

  const SortHeader = ({ field, label, className = "" }) => (
    <button
      onClick={() => toggleSort(field)}
      className={`flex items-center gap-0.5 hover:text-zinc-400 ${className}`}
    >
      {label}
      <ArrowUpDown className="w-2.5 h-2.5" />
    </button>
  );

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs font-semibold text-zinc-400 uppercase tracking-wider">
          Top Pairs
        </h3>
        <span className="text-[10px] text-zinc-600">{timeframeLabel}</span>
      </div>

      {/* Filters */}
      <div className="flex gap-1.5 mb-3 overflow-x-auto -mx-1 px-1 pb-1">
        {[
          { value: "all", label: "All" },
          { value: "same_sector", label: "Same Sector" },
          { value: "cross_sector", label: "Cross Sector" },
        ].map((f) => (
          <button
            key={f.value}
            onClick={() => setFilter(f.value)}
            className={`text-[10px] px-2 py-1 rounded transition-colors whitespace-nowrap flex-shrink-0 ${
              filter === f.value
                ? "bg-blue-600 text-white"
                : "bg-zinc-800 text-zinc-400 hover:bg-zinc-700"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Column headers */}
      <div className="grid grid-cols-[1fr_auto] gap-2 text-[9px] text-zinc-600 uppercase tracking-wider px-2 pb-1 border-b border-zinc-800">
        <span>Pair</span>
        <div className="flex items-center gap-3">
          <SortHeader field="abs_corr" label="Corr" />
          <span className="w-4" />
        </div>
      </div>

      {/* Pairs list */}
      <div className="flex-1 overflow-y-auto space-y-0.5 mt-1 min-h-0">
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <div className="animate-spin w-5 h-5 border-2 border-blue-500 border-t-transparent rounded-full" />
          </div>
        ) : filteredPairs.length === 0 ? (
          <div className="flex items-center justify-center py-8 text-zinc-600 text-xs">
            No pairs match filters
          </div>
        ) : groupedPairs ? (
          Object.entries(groupedPairs).map(([sector, sectorPairs]) => (
            <div key={sector} className="mb-2">
              <div
                className="text-[9px] px-2 py-1 font-semibold uppercase tracking-wider flex items-center gap-1"
                style={{ color: SECTOR_COLORS[sector] || "#666" }}
              >
                <span
                  className="w-1.5 h-1.5 rounded-full"
                  style={{ background: SECTOR_COLORS[sector] || "#666" }}
                />
                {sector.replace(/_/g, " ")} ({sectorPairs.length})
              </div>
              {sectorPairs.map((pair, idx) => (
                <PairRow
                  key={`${pair.sym1}-${pair.sym2}-${idx}`}
                  pair={pair}
                  isSelected={
                    selectedPair &&
                    ((selectedPair.sym1 === pair.sym1 && selectedPair.sym2 === pair.sym2) ||
                      (selectedPair.sym1 === pair.sym2 && selectedPair.sym2 === pair.sym1))
                  }
                  onClick={() => onSelectPair(pair.sym1, pair.sym2)}
                />
              ))}
            </div>
          ))
        ) : (
          filteredPairs.map((pair, idx) => (
            <PairRow
              key={`${pair.sym1}-${pair.sym2}-${idx}`}
              pair={pair}
              isSelected={
                selectedPair &&
                ((selectedPair.sym1 === pair.sym1 && selectedPair.sym2 === pair.sym2) ||
                  (selectedPair.sym1 === pair.sym2 && selectedPair.sym2 === pair.sym1))
              }
              onClick={() => onSelectPair(pair.sym1, pair.sym2)}
            />
          ))
        )}
      </div>

      <div className="text-[9px] text-zinc-700 pt-2 text-center border-t border-zinc-800 mt-2 flex-shrink-0">
        {filteredPairs.length} pair{filteredPairs.length !== 1 ? "s" : ""} · click to analyze
      </div>
    </div>
  );
}

function getCorrBarColor(value) {
  return value > 0 ? "#22c55e" : "#ef4444";
}

function PairRow({ pair, isSelected, onClick }) {
  const corr = pair.correlation || 0;
  const absCorr = Math.abs(corr);
  const barWidth = absCorr * 100;
  const label = getCorrelationLabel(corr);

  return (
    <div
      onClick={onClick}
      className={`
        grid grid-cols-[1fr_auto] gap-2 items-center px-2 py-1.5 rounded
        cursor-pointer transition-colors text-xs
        ${isSelected ? "bg-blue-600/20 ring-1 ring-blue-500/40" : "hover:bg-zinc-800/50"}
      `}
    >
      <div className="flex items-center gap-1.5 min-w-0">
        <div className="flex items-center gap-1 font-mono text-[11px] min-w-0">
          <span className="truncate">{pair.sym1}</span>
          <span className="text-zinc-600 text-[9px] flex-shrink-0">/</span>
          <span className="truncate">{pair.sym2}</span>
        </div>
        {pair.same_sector && (
          <span className="text-[8px] px-1 rounded bg-zinc-800 text-zinc-500 flex-shrink-0">
            same
          </span>
        )}
        {/* Strength badge — hidden on very small screens */}
        <span className={`text-[8px] px-1 rounded ${label.bg} ${label.color} hidden sm:inline flex-shrink-0`}>
          {label.text}
        </span>
      </div>

      <div className="flex items-center gap-1.5">
        <div className="w-12 sm:w-14 h-1.5 bg-zinc-800 rounded-full overflow-hidden hidden sm:block">
          <div
            className="h-full rounded-full transition-all"
            style={{
              width: `${barWidth}%`,
              background: getCorrBarColor(corr),
            }}
          />
        </div>
        <span
          className={`font-mono text-[11px] w-10 text-right ${
            corr > 0.7
              ? "text-green-400"
              : corr < -0.3
              ? "text-red-400"
              : "text-zinc-400"
          }`}
        >
          {corr >= 0 ? "+" : ""}
          {(corr * 100).toFixed(0)}
        </span>
        {getSignalIcon(corr, pair)}
      </div>
    </div>
  );
}
