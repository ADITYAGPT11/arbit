import { useState } from "react";
import { ZoomIn, ZoomOut } from "lucide-react";

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

function getCorrColor(value) {
  // Scale: -1 (blue) → 0 (dark) → +1 (red)
  if (value === null || value === undefined) return "#1a1a1a";
  const v = Math.max(-1, Math.min(1, value));
  if (v > 0) {
    const intensity = Math.round(v * 200);
    return `rgb(${intensity + 40}, ${40 + Math.round((1 - v) * 60)}, ${80 - Math.round(v * 40)})`;
  }
  const intensity = Math.round(Math.abs(v) * 150);
  return `rgb(${40}, ${40 + Math.round((1 - Math.abs(v)) * 40)}, ${intensity + 60})`;
}

function formatCorr(v) {
  if (v === null || v === undefined) return "—";
  const sign = v >= 0 ? "+" : "";
  return `${sign}${(v * 100).toFixed(0)}`;
}

export default function CorrelationHeatmap({
  symbols = [],
  stockSectors = {},
  matrix = [],
  sectorOrder = [],
  onSelectPair,
  selectedPair,
}) {
  const [hoveredCell, setHoveredCell] = useState(null);
  const [zoom, setZoom] = useState(1);

  if (!symbols.length || !matrix.length) {
    return (
      <div className="flex items-center justify-center h-64 text-zinc-500 text-sm">
        No correlation data available
      </div>
    );
  }

  // Group symbols by sector for the heatmap
  const sectorGroups = [];
  const sectorSet = new Set();
  for (const sym of symbols) {
    const sec = stockSectors[sym] || "Unknown";
    if (!sectorSet.has(sec)) {
      sectorSet.add(sec);
      sectorGroups.push({ sector: sec, symbols: [sym] });
    } else {
      const group = sectorGroups.find((g) => g.sector === sec);
      if (group) group.symbols.push(sym);
    }
  }

  const cellSize = Math.max(10, Math.min(16, 640 / symbols.length));

  const matrixDim = symbols.length;

  // Find hovered cell info
  const hoverInfo = hoveredCell
    ? {
        sym1: symbols[hoveredCell.row],
        sym2: symbols[hoveredCell.col],
        value: matrix[hoveredCell.row]?.[hoveredCell.col],
      }
    : null;

  const handleCellClick = (row, col) => {
    if (row !== col && onSelectPair) {
      onSelectPair(symbols[row], symbols[col]);
    }
  };

  return (
    <div className="space-y-3">
      {/* Controls */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button
            onClick={() => setZoom((z) => Math.max(0.5, z - 0.2))}
            className="p-1 rounded hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200"
            title="Zoom out"
          >
            <ZoomOut className="w-4 h-4" />
          </button>
          <span className="text-xs text-zinc-500 w-12 text-center">
            {Math.round(zoom * 100)}%
          </span>
          <button
            onClick={() => setZoom((z) => Math.min(2, z + 0.2))}
            className="p-1 rounded hover:bg-zinc-800 text-zinc-400 hover:text-zinc-200"
            title="Zoom in"
          >
            <ZoomIn className="w-4 h-4" />
          </button>
        </div>

        {hoverInfo && (
          <div className="text-xs text-zinc-400 font-mono">
            {hoverInfo.sym1} / {hoverInfo.sym2}:{" "}
            <span className={hoverInfo.value >= 0 ? "text-green-400" : "text-red-400"}>
              {formatCorr(hoverInfo.value)}
            </span>
          </div>
        )}

        {/* Legend */}
        <div className="flex items-center gap-2 text-[10px] text-zinc-500">
          <span>-1</span>
          <div className="flex h-2 w-24 rounded overflow-hidden">
            <div className="flex-1" style={{ background: "#282845" }} />
            <div className="flex-1" style={{ background: "#1a1a2e" }} />
            <div className="flex-1" style={{ background: "#2a1a1a" }} />
            <div className="flex-1" style={{ background: "#3b2020" }} />
            <div className="flex-1" style={{ background: "#5a2020" }} />
            <div className="flex-1" style={{ background: "#8b2020" }} />
          </div>
          <span>+1</span>
        </div>
      </div>

      {/* Heatmap container */}
      <div
        className="overflow-auto border border-zinc-800 rounded-lg bg-zinc-900/50"
        style={{ maxHeight: "75vh" }}
      >
        <div
          className="relative"
          style={{
            transform: `scale(${zoom})`,
            transformOrigin: "top left",
            minWidth: matrixDim * cellSize + 120,
          }}
        >
          {/* Y-axis labels (left side) */}
          <div style={{ position: "absolute", left: 0, top: 24, width: 100 }}>
            {symbols.map((sym, i) => (
              <div
                key={sym}
                className="flex items-center gap-1 text-[10px] font-mono truncate"
                style={{
                  height: cellSize + 1,
                  lineHeight: `${cellSize + 1}px`,
                  paddingRight: 4,
                  color: hoveredCell?.row === i ? "#fff" : stockSectors[sym]
                    ? (SECTOR_COLORS[stockSectors[sym]] || "#666")
                    : "#666",
                }}
              >
                <span
                  className="w-1.5 h-1.5 rounded-full inline-block flex-shrink-0"
                  style={{
                    background: SECTOR_COLORS[stockSectors[sym]] || "#666",
                  }}
                />
                <span className="truncate">{sym}</span>
              </div>
            ))}
          </div>

          {/* X-axis labels (top) */}
          <div
            style={{
              marginLeft: 104,
              height: 20,
              whiteSpace: "nowrap",
              position: "sticky",
              top: 0,
              zIndex: 10,
              background: "#111",
            }}
          >
            {symbols.map((sym, i) => (
              <span
                key={sym}
                className="text-[9px] font-mono inline-block truncate"
                style={{
                  width: cellSize + 1,
                  lineHeight: "20px",
                  textAlign: "center",
                  color: hoveredCell?.col === i ? "#fff" : "#666",
                  transform: "rotate(-45deg)",
                  transformOrigin: "left center",
                  marginTop: 14,
                }}
                title={sym}
              >
                {sym}
              </span>
            ))}
          </div>

          {/* Grid */}
          <div style={{ marginLeft: 104, marginTop: 50 }}>
            {matrix.map((row, i) => (
              <div key={i} style={{ display: "flex", height: cellSize + 1 }}>
                {row.map((val, j) => {
                  const isSelected =
                    selectedPair &&
                    ((selectedPair.sym1 === symbols[i] && selectedPair.sym2 === symbols[j]) ||
                      (selectedPair.sym1 === symbols[j] && selectedPair.sym2 === symbols[i]));
                  const isHovered =
                    hoveredCell &&
                    (hoveredCell.row === i || hoveredCell.col === j);
                  const isDiagonal = i === j;

                  return (
                    <div
                      key={j}
                      className={`
                        cursor-pointer transition-all duration-75
                        ${isDiagonal ? "cursor-default" : "hover:ring-1 hover:ring-white/40"}
                        ${isSelected ? "ring-2 ring-yellow-400 z-10" : ""}
                      `}
                      style={{
                        width: cellSize + 1,
                        height: cellSize + 1,
                        background: isDiagonal
                          ? "#1a1a1a"
                          : getCorrColor(val),
                        opacity: isHovered && !isSelected ? 0.85 : 1,
                        position: "relative",
                        borderRadius: i === j ? "50%" : 1,
                      }}
                      onClick={() => handleCellClick(i, j)}
                      onMouseEnter={() =>
                        setHoveredCell({ row: i, col: j })
                      }
                      onMouseLeave={() => setHoveredCell(null)}
                      title={`${symbols[i]} / ${symbols[j]}: ${formatCorr(val)}`}
                    >
                      {/* Show value on hover for better readability */}
                      {hoveredCell?.row === i && hoveredCell?.col === j && cellSize >= 14 && (
                        <div
                          className="absolute z-20 bg-zinc-900 border border-zinc-700 rounded px-1.5 py-0.5 text-[10px] font-mono whitespace-nowrap pointer-events-none shadow-lg"
                          style={{
                            top: -22,
                            left: "50%",
                            transform: "translateX(-50%)",
                          }}
                        >
                          <span className={val >= 0 ? "text-green-400" : "text-red-400"}>
                            {formatCorr(val)}
                          </span>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Sector legend */}
      <div className="flex flex-wrap gap-2 text-[10px] text-zinc-500">
        {Object.entries(SECTOR_COLORS).map(([sector, color]) => {
          const count = symbols.filter((s) => stockSectors[s] === sector).length;
          if (count === 0) return null;
          return (
            <span key={sector} className="flex items-center gap-1">
              <span
                className="w-2 h-2 rounded-full inline-block"
                style={{ background: color }}
              />
              <span className="truncate max-w-[100px]">
                {sector.replace(/_/g, " ")}
              </span>
              <span className="text-zinc-600">({count})</span>
            </span>
          );
        })}
      </div>
    </div>
  );
}
