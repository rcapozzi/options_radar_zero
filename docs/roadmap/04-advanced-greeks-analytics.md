# Roadmap Item 4: Advanced Greeks Analytics & Visualization

**Status:** Proposed
**Priority:** Medium-High
**Target Release:** v0.4.0
**Estimated Effort:** 3-4 weeks

---

## Overview

Build a comprehensive Greeks analytics suite with real-time calculations, advanced visualizations, and risk management tools. Move beyond basic delta/gamma/theta/vega to provide institutional-grade analytics: gamma exposure profiles, charm/color/vanna/volga, term structure analysis, and scenario modeling.

---

## Problem Statement

Current dashboard shows basic Greeks per contract. Traders need:
- **Gamma Exposure (GEX)** by strike — where dealers are long/short gamma
- **Dealer Positioning** — inferred from open interest and volume
- **Charm/Color/Vanna/Volga** — second/third order Greeks for 0DTE
- **Term Structure** — IV across expiries, skew, curvature
- **Scenario Analysis** — "What happens to my P&L if SPY moves ±2%?"
- **Risk Metrics** — Max pain, pin risk, assignment risk, vega risk
- **Historical Comparison** — Current Greeks vs. historical percentiles

---

## Technical Design

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                  Greeks Analytics Engine                     │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐  ┌─────────────────────────────────┐   │
│  │  Calculation    │  │  Data Pipeline                  │   │
│  │  Core           │──▶│  (Chains → Greeks → Analytics)  │   │
│  │  (QuantLib/     │   │  - Real-time (1s)             │   │
│  │   custom)       │   │  - Historical (EOD snapshots) │   │
│  └────────┬────────┘   └─────────────────────────────────┘   │
│           │                          │                        │
│           ▼                          ▼                        │
│  ┌─────────────────┐  ┌─────────────────────────────────┐   │
│  │  Analytics      │  │  Visualization Layer            │   │
│  │  Modules        │──▶│  (Plotly/Dash components)       │   │
│  │  - GEX          │   │  - GEX Chart                    │   │
│  │  - Charm/Color  │   │  - Gamma Profile                │   │
│  │  - Term Struct  │   │  - Skew Surface                 │   │
│  │  - Scenarios    │   │  - Scenario P&L                 │   │
│  └─────────────────┘  └─────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Components

#### 1. Greeks Calculation Core (`src/options_radar_zero/greeks/calculator.py`)
- **Engine Options:**
  - **QuantLib** (via `quantlib-python`) — institutional standard, slower
  - **Custom Vectorized** (NumPy/Pandas) — fast, tailored for 0DTE
  - **Hybrid** — QuantLib for validation, custom for production
- **Inputs:** Chain data, underlying price, risk-free rate, dividend yield, IV
- **Outputs per Contract:** Delta, Gamma, Theta, Vega, Rho, Charm, Color, Vanna, Volga, Vomma, Ultima
- **Vectorized:** Process entire chain in <50ms

#### 2. Gamma Exposure (GEX) Module (`src/options_radar_zero/greeks/gex.py`)
- **Dealer GEX** = Σ (OI × Gamma × 100 × Contract Multiplier × Spot)
  - Positive = Dealers long gamma (hedge by selling rallies, buying dips)
  - Negative = Dealers short gamma (hedge by buying rallies, selling dips)
- **By Strike:** Bar chart showing net dealer gamma exposure
- **Flip Point:** Strike where net GEX crosses zero
- **Rolling Window:** Track GEX evolution intraday

#### 3. Higher-Order Greeks (`src/options_radar_zero/greeks/higher_order.py`)
| Greek | Formula | Significance for 0DTE |
|-------|---------|----------------------|
| **Charm** (ΔDelta/Δt) | ∂²V/∂t∂S | Delta decay — critical for 0DTE |
| **Color** (ΓGamma/Δt) | ∂³V/∂t∂S² | Gamma decay |
| **Vanna** (ΔDelta/Δσ) | ∂²V/∂σ∂S | Delta sensitivity to IV |
| **Volga** (ΔVega/Δσ) | ∂²V/∂σ² | Vega convexity |
| **Vomma** | ∂Vega/∂σ | Volga (same) |
| **Ultima** | ∂Volga/∂σ | Third-order vol sensitivity |

- **Charm Profile:** Shows where delta decay accelerates (near strikes, near expiry)
- **Vanna/Vomma:** Important for vol trades, skew trading

#### 4. Term Structure & Skew (`src/options_radar_zero/greeks/term_structure.py`)
- **IV Surface:** 3D (Strike × Expiry × IV)
- **Skew Metrics:**
  - 25Δ Put/Call Skew
  - ATM IV vs. 1M IV (term structure slope)
  - Curvature (butterfly)
- **Historical Percentiles:** Current skew vs. 30/60/90-day history
- **Forward IV:** Implied forward variance

#### 5. Scenario Analysis (`src/options_radar_zero/greeks/scenarios.py`)
- **Price Shocks:** ±1%, ±2%, ±5%, custom
- **Vol Shocks:** ±5, ±10, ±20 vol points
- **Time Decay:** 1h, 4h, EOD
- **Output per Scenario:**
  - Portfolio P&L (if positions loaded)
  - Greeks changes
  - Probability of profit (from IV)
  - Max pain strike

#### 5. Risk Metrics (`src/options_radar_zero/greeks/risk.py`)
- **Max Pain:** Strike where total option value minimized
- **Pin Risk:** Probability of expiring at strike (using IV)
- **Assignment Risk:** ITM probability for short positions
- **Vega Risk:** $ P&L per 1% vol move
- **Gamma Scalping Threshold:** Required move to cover theta

#### 6. Visualization Components (`src/options_radar_zero/components/greeks.py`)
- **GEX Chart:** Bar chart by strike, flip point marker, zero line
- **Gamma Profile:** Line chart (gamma vs strike), colored by call/put
- **Skew Surface:** 3D surface (Plotly) or heatmap (Strike × Expiry)
- **Term Structure:** Line chart (IV vs Days to Expiry) per delta
- **Scenario P&L:** Waterfall chart or tornado chart
- **Greeks Table:** Sortable, filterable, with sparklines

---

## User Experience

### New Tabs/Pages
```
/greeks
├── /greeks/gex              # Gamma Exposure dashboard
├── /greeks/higher-order     # Charm, Color, Vanna, Volga
├── /greeks/term-structure   # IV surface, skew, term structure
├── /greeks/scenarios        # Scenario analysis / what-if
├── /greeks/risk             # Max pain, pin risk, assignment
└── /greeks/historical       # Percentile rankings, evolution
```

### GEX Dashboard Layout
```
┌─────────────────────────────────────────────────────────────────┐
│  SPY GEX | Flip: 448.50 | Net: -$2.3B | Updated: 13:42:15     │
├─────────────────────────────────────────────────────────────────┤
│  [GEX by Strike Chart]                    │ [Dealer Positioning] │
│  (bars: call +, put -)                    │ Call OI: 1.2M        │
│  Flip ▲ 448.50                            │ Put OI: 1.5M         │
│                                           │ Net: Short Gamma     │
├─────────────────────────────────────────────────────────────────┤
│  [GEX Evolution]                          │ [Key Levels]         │
│  (intraday line: net GEX over time)       │ Max Pain: 449.20     │
│                                           │ Gamma Wall: 445/455  │
│                                           │ 0DTE Expiry: 16:00   │
└─────────────────────────────────────────────────────────────────┘
```

### Scenario Analysis UI
- **Inputs Panel:** Price move (±%), Vol move (±pts), Time (hours), Custom spot
- **Positions:** Load from portfolio or manual entry
- **Output:** Tornado chart (P&L sensitivity), Greeks delta table
- **Export:** CSV, PNG, shareable link

---

## Implementation Phases

### Phase 1: Calculation Core (Week 1)
- [ ] Vectorized Black-Scholes + Greeks (NumPy)
- [ ] Validate against QuantLib (test suite)
- [ ] Higher-order Greeks (Charm, Color, Vanna, Volga)
- [ ] Performance: <50ms for full chain (500 contracts)

### Phase 2: GEX & Core Analytics (Week 1-2)
- [ ] GEX calculation (dealer positioning)
- [ ] Flip point detection
- [ ] Max pain, pin risk
- [ ] Intraday GEX evolution tracking

### Phase 3: Term Structure & Skew (Week 2)
- [ ] Multi-expiry chain fetching
- [ ] IV surface construction
- [ ] Skew metrics (25Δ, curvature, term slope)
- [ ] Historical percentile database

### Phase 4: Scenario Engine (Week 2-3)
- [ ] Scenario definition DSL
- [ ] Portfolio P&L projection
- [ ] Greeks sensitivity matrix
- [ ] Monte Carlo option (optional)

### Phase 5: Visualizations (Week 3)
- [ ] GEX chart (bars + flip marker)
- [ ] Skew surface (3D/heatmap)
- [ ] Scenario tornado chart
- [ ] Greeks table with sparklines

### Phase 6: Integration & Polish (Week 3-4)
- [ ] Dashboard tabs routing
- [ ] Real-time updates (1s chain → 2s Greeks)
- [ ] Historical comparison views
- [ ] Tests (unit: calculator accuracy; integration: full pipeline)
- [ ] Documentation

---

## Dependencies

```toml
[tool.uv.sources]
# QuantLib for validation (optional, heavy)
quantlib = { version = ">=1.34", optional = true }

# Scientific stack (already in deps)
numpy = { version = ">=1.24" }
scipy = { version = ">=1.10" }  # for interpolation
pandas = { version = ">=2.0" }
plotly = { version = ">=5.0" }

# Performance
numba = { version = ">=0.58", optional = true }  # JIT compilation
```

---

## Configuration

```yaml
# config/greeks.yaml
calculation:
  engine: "vectorized"  # or "quantlib"
  risk_free_rate_source: "fred"  # or "fixed", "tbill"
  risk_free_rate_fixed: 0.05
  dividend_yield: 0.0  # SPY ≈ 0
  compounding: "continuous"
  day_count: "ACT/365"

greeks:
  calculate_higher_order: true
  charm_color_vanna_volga: true
  update_interval_seconds: 2

gex:
  contract_multiplier: 100
  spot_source: "underlying_price"  # from chain
  flip_detection_threshold: 0.01  # 1% of max GEX

term_structure:
  expiries_to_fetch: ["0DTE", "1W", "2W", "1M", "2M", "3M"]
  skew_deltas: [10, 25, 50, 75, 90]
  interpolation: "cubic_spline"
  history_window_days: 90

scenarios:
  default_shocks:
    price_pct: [-5, -2, -1, -0.5, 0.5, 1, 2, 5]
    vol_pts: [-20, -10, -5, 5, 10, 20]
    time_hours: [1, 4, 8]  # to expiry
  max_scenarios: 50

visualization:
  gex_chart_height: 500
  skew_surface_type: "heatmap"  # or "3d"
  scenario_chart_type: "tornado"
  color_scheme:
    call_gamma: "#6366f1"
    put_gamma: "#14b8a6"
    zero_line: "#e2e8f0"
```

---

## Data Requirements

### Real-Time (from existing chain poller)
- Per contract: bid, ask, last, volume, OI, IV, underlying_price
- Multi-expiry: Need to extend poller for weekly/monthly chains

### Historical (new storage)
- **Daily Snapshots:** EOD chains + calculated Greeks
- **Schema:**
```sql
CREATE TABLE greeks_snapshots (
    date DATE,
    symbol TEXT,
    expiry DATE,
    strike REAL,
    put_call TEXT,
    delta REAL, gamma REAL, theta REAL, vega REAL,
    charm REAL, color REAL, vanna REAL, volga REAL,
    gex REAL,
    PRIMARY KEY (date, symbol, expiry, strike, put_call)
);

CREATE TABLE term_structure_daily (
    date DATE,
    symbol TEXT,
    days_to_expiry INTEGER,
    delta_25_put REAL, delta_25_call REAL,
    atm_iv REAL, skew_25 REAL, curvature REAL,
    PRIMARY KEY (date, symbol, days_to_expiry)
);
```

---

## Acceptance Criteria

- [ ] Greeks calculate in <50ms for 500-contract chain
- [ ] GEX chart matches SpotGamma/Dealer positioning sources within 10%
- [ ] Higher-order Greeks validate against QuantLib (Δ < 1%)
- [ ] Flip point detection accurate (crosses zero correctly)
- [ ] Term structure loads 6+ expiries, renders in <2s
- [ ] Scenario analysis computes P&L for 20 scenarios in <500ms
- [ ] Historical percentiles available for 90 days
- [ ] All visualizations responsive, mobile-friendly
- [ ] Unit tests: calculator accuracy vs. known values
- [ ] Integration test: chain → Greeks → GEX → UI

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Calculation accuracy | Validate against QuantLib, known analytical values |
| Performance (many expiries) | Lazy load, cache IV surface, Web Workers for heavy calc |
| Data quality (bad IVs) | IV sanitization (bounds, smoothing), fallback to mid-price |
| QuantLib dependency heavy | Make optional, pure-Python fallback |
| Real-time updates overwhelming UI | Throttle UI updates to 2s, decouple calc from render |

---

## Future Enhancements

- **Vol Surface Dynamics:** Real-time skew movement tracking
- **Dealer Flow Inference:** From volume/OI changes
- **Correlation Greeks:** Cross-asset (SPY vs QQQ vs ES)
- **Portfolio Greeks Aggregation:** Net position Greeks
- **Options Strategy Builder:** Visual strategy P&L
- **ML Greeks Prediction:** Forecast gamma flip, charm decay
- **Options Flow Integration:** Unusual activity → Greeks impact