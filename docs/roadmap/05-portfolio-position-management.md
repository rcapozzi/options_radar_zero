# Roadmap Item 5: Portfolio Integration & Position Management

**Status:** Proposed
**Priority:** High
**Target Release:** v0.5.0
**Estimated Effort:** 4-5 weeks

---

## Overview

Enable traders to import, track, and manage their options positions directly in the dashboard. Combine real-time market data with personal positions for P&L tracking, risk analytics, Greeks aggregation, and automated alerts on position-specific events.

---

## Problem Statement

Traders currently use separate tools:
- Broker platform for execution/positions
- Dashboard for market analysis
- Spreadsheet for P&L tracking
- Journal for trade notes

This fragmentation causes:
- Delayed risk awareness (position Greeks not visible with market Greeks)
- Manual reconciliation errors
- Missed alerts (assignment risk, expiration, gamma flip near position)
- No unified view of strategy performance

---

## Technical Design

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Portfolio Engine                          │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │  Broker      │  │  Position    │  │  Analytics       │   │
│  │  Connectors  │──▶│  Engine      │──▶│  (Greeks, P&L,  │   │
│  │  (Tastytrade,│   │  (Positions, │   │   Risk, Alerts) │   │
│  │   IBKR,      │   │   Lots,      │   └────────┬────────┘   │
│  │   CSV/API)   │   │   Strategies)│            │            │
│  └──────────────┘  └──────────────┘             ▼            │
│                          ┌─────────────────────────────────┐  │
│                          │  Dashboard Integration          │  │
│                          │  - Positions Tab                │  │
│                          │  - P&L Widget (header)          │  │
│                          │  - Risk Panel                   │  │
│                          │  - Position-Aware Alerts        │  │
│                          └─────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Components

#### 1. Broker Connectors (`src/options_radar_zero/portfolio/connectors/`)
- **Abstract Base:** `BrokerConnector` interface
- **Implementations:**
  - `TastytradeConnector` — OAuth2, REST + WebSocket (existing auth)
  - `IBKRConnector` — ib_insync / TWS API
  - `SchwabConnector` — Schwab API (TD Ameritrade successor)
  - `CSVImporter` — Generic CSV/Excel import (fallback)
  - `ManualEntry` — UI for manual position entry
- **Sync Modes:**
  - **Real-time:** WebSocket position updates (Tastytrade, IBKR)
  - **Polling:** Every 30-60s (REST APIs)
  - **On-demand:** Manual "Sync Now" button
- **Data Normalization:** Unified `Position` model regardless of source

#### 2. Position Engine (`src/options_radar_zero/portfolio/engine.py`)
- **Position Model:**
```python
@dataclass
class Position:
    id: str
    symbol: str                    # SPY, AAPL
    underlying: str                # SPY
    strategy: StrategyType         # LONG_CALL, IRON_CONDOR, etc.
    legs: List[Leg]                # Individual options
    qty: int                       # Number of contracts (signed)
    entry_price: float             # Avg entry premium
    entry_date: datetime
    account_id: str
    tags: List[str]                # User-defined
    notes: str
```

- **Leg Model:**
```python
@dataclass
class Leg:
    option_symbol: str             # SPY260805C450
    strike: float
    expiry: date
    put_call: Literal["CALL", "PUT"]
    action: Literal["BUY", "SELL"]
    qty: int
    entry_price: float
    current_price: float           # From market data
    greeks: GreeksSnapshot         # Real-time
```

- **Strategy Recognition:** Auto-detect common strategies from legs
  - Single leg: Long/Short Call/Put
  - Vertical: Bull/Bear Call/Put Spread
  - Iron Condor/Butterfly
  - Calendar/Diagonal
  - Straddle/Strangle
  - Covered Call/Protective Put
  - Custom: User-labeled

#### 3. Portfolio Analytics (`src/options_radar_zero/portfolio/analytics.py`)
- **Real-time P&L:**
  - Unrealized: (current - entry) × qty × 100
  - Realized: Closed positions
  - Total: Unrealized + Realized + Fees
- **Aggregated Greeks:** Sum across all positions
  - Net Delta, Gamma, Theta, Vega (portfolio level)
  - Per-strategy, per-underlying breakdown
- **Risk Metrics:**
  - Max loss (defined risk strategies)
  - Margin requirement (reg T, portfolio margin)
  - Buying power effect
  - Concentration (by underlying, strategy, expiry)
- **Scenario Analysis:** Portfolio-level what-if (from Greeks engine)
- **Performance Attribution:** By strategy, underlying, time period

#### 4. Position Lifecycle Management (`src/options_radar_zero/portfolio/lifecycle.py`)
- **Events Tracked:**
  - Open/Close/Adjust
  - Assignment/Exercise
  - Expiration (ITM/OTM)
  - Roll (close + open new expiry)
  - Assignment risk alerts
- **Tax Lot Tracking:** FIFO/LIFO/HIFO for cost basis
- **Wash Sale Detection:** Flag potential wash sales
- **Corporate Actions:** Splits, dividends, symbol changes

#### 5. Position-Aware Alerts (`src/options_radar_zero/portfolio/alerts.py`)
Integrate with WebSocket Alert System (Roadmap #1):
- **Position-Specific:**
  - "Your SPY 450C 0DTE approaching strike (delta > 0.5)"
  - "Assignment risk: SPY 440P 0DTE ITM by $2.50"
  - "Gamma flip near your 455C strike"
  - "Theta burn: $150/day on current positions"
- **Portfolio-Level:**
  - "Net delta exposure > $50k (long)"
  - "Daily theta decay > $500"
  - "Vega risk: $2k per 1% vol move"
- **Risk Limits:**
  - "Max loss on iron condor exceeded"
  - "Concentration: >50% in SPY 0DTE"

#### 6. Dashboard Integration (`src/options_radar_zero/components/portfolio.py`)
**New Tabs:**
```
/portfolio
├── /portfolio/positions      # All positions table (groupable)
├── /portfolio/pnl            # P&L dashboard (realized/unrealized)
├── /portfolio/greeks         # Aggregated Greeks + per-position
├── /portfolio/risk           # Risk metrics, limits, scenarios
├── /portfolio/history        # Closed trades, performance
├── /portfolio/strategies     # By strategy type
└── /portfolio/settings       # Broker connections, sync, alerts
```

**Header Widget:** Persistent P&L summary (always visible)
```
[SPY: +$1,234  |  QQQ: -$567  |  Net: +$667  |  Δ: +45  |  Θ: -$230/day  |  ⟳ Sync]
```

**Positions Table Features:**
- Group by: Strategy / Underlying / Expiry / Account
- Columns: Symbol, Strategy, Qty, Entry, Mark, P&L, P&L%, Delta, Theta, Vega, DTE
- Inline charts: P&L sparkline per position
- Actions: Close, Roll, Adjust, Notes, Alerts

---

## User Experience

### Onboarding Flow
1. **Connect Broker** → OAuth (Tastytrade) or API keys (IBKR)
2. **Select Accounts** → Choose which accounts to sync
3. **Initial Sync** → Pull positions, show progress
4. **Review & Label** → Auto-detected strategies, user confirms/edits
5. **Set Risk Limits** → Max delta, max theta, max loss per strategy
6. **Enable Alerts** → Choose which position alerts to receive

### Daily Workflow
1. **Open Dashboard** → Header shows net P&L, key Greeks
2. **Positions Tab** → Scan for red flags (assignment risk, gamma flip)
3. **Alerts Panel** → Position-specific alerts prioritized
4. **Risk Tab** → Check scenario analysis before market open
5. **Adjust/Roll** → One-click roll to next expiry, pre-filled ticket

### Mobile (PWA - Roadmap #3)
- Position cards optimized for mobile
- Swipe actions: Close, Roll, Notes
- Push alerts for critical position events

---

## Implementation Phases

### Phase 1: Core Infrastructure (Week 1)
- [ ] Position/Leg/Strategy data models
- [ ] Abstract broker connector interface
- [ ] Tastytrade connector (OAuth2, positions endpoint)
- [ ] CSV importer (fallback)
- [ ] SQLite storage schema

### Phase 2: Sync & Analytics (Week 1-2)
- [ ] Position sync engine (polling + WebSocket)
- [ ] Real-time mark-to-market (join with chain data)
- [ ] Aggregated Greeks calculation
- [ ] P&L calculation (unrealized/realized)
- [ ] Strategy auto-detection

### Phase 3: Broker Expansion (Week 2)
- [ ] IBKR connector (ib_insync)
- [ ] Manual entry UI
- [ ] Multi-account support
- [ ] Sync scheduling & conflict resolution

### Phase 4: Risk & Alerts (Week 2-3)
- [ ] Risk metrics (margin, buying power, concentration)
- [ ] Position-aware alert rules
- [ ] Integration with WebSocket alert system
- [ ] Assignment/expiration tracking

### Phase 5: Dashboard UI (Week 3-4)
- [ ] Positions table (grouping, sorting, inline charts)
- [ ] P&L dashboard (realized/unrealized, attribution)
- [ ] Greeks tab (portfolio + per-position)
- [ ] Risk tab (scenarios, limits, margin)
- [ ] Header P&L widget

### Phase 6: History & Performance (Week 4)
- [ ] Closed trade history
- [ ] Performance attribution (by strategy, underlying, month)
- [ ] Tax lot tracking (FIFO/LIFO)
- [ ] Export (CSV, PDF reports)

### Phase 7: Polish & Testing (Week 4-5)
- [ ] End-to-end tests (sync → analytics → UI)
- [ ] Multi-broker test scenarios
- [ ] Performance: <2s full sync, <500ms P&L refresh
- [ ] Security: Encrypted credential storage
- [ ] Documentation

---

## Dependencies

```toml
[tool.uv.sources]
# Tastytrade (already in deps)
tastytrade = { version = ">=0.1" }

# IBKR
ib-insync = { version = ">=0.9" }

# Encryption for credentials
cryptography = { version = ">=41.0" }

# Keyring for secure storage
keyring = { version = ">=24.0" }

# Data validation
pydantic = { version = ">=2.0" }
```

---

## Configuration

```yaml
# config/portfolio.yaml
portfolio:
  sync:
    interval_seconds: 30
    websocket_enabled: true
    max_sync_age_hours: 24
  
  positions:
    strategy_detection: true
    min_legs_for_complex: 2
    group_by_default: "strategy"
  
  analytics:
    pnl_update_interval_seconds: 5
    greeks_aggregation: true
    scenario_shocks:
      price_pct: [-5, -2, -1, 1, 2, 5]
      vol_pts: [-10, -5, 5, 10]
  
  risk_limits:
    max_portfolio_delta: 100000  # $ delta
    max_portfolio_theta: -5000   # $/day
    max_single_strategy_loss: 5000
    max_concentration_pct: 50    # % in single underlying
    assignment_risk_threshold: 0.05  # 5% ITM
  
  alerts:
    position_alerts_enabled: true
    assignment_warning_hours: 24
    expiration_warning_hours: 4
    gamma_flip_proximity: 5      # strikes
    theta_burn_threshold: 100    # $/day

brokers:
  tastytrade:
    enabled: true
    sandbox: false
    accounts: ["*"]  # or specific account numbers
  
  ibkr:
    enabled: false
    host: "127.0.0.1"
    port: 7497
    client_id: 1
    accounts: ["*"]
  
  csv_import:
    enabled: true
    column_mapping:
      symbol: "Symbol"
      quantity: "Qty"
      entry_price: "Avg Price"
      # ... flexible mapping

security:
  credential_encryption: true
  keyring_backend: "system"  # or "file"
  session_timeout_hours: 24
```

---

## Database Schema

```sql
-- Broker connections (encrypted credentials)
CREATE TABLE broker_connections (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    broker_type TEXT NOT NULL,        -- tastytrade, ibkr, csv
    config_encrypted TEXT NOT NULL,   -- JSON, encrypted
    accounts TEXT,                    -- JSON array
    enabled BOOLEAN DEFAULT 1,
    last_sync TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Positions (current open)
CREATE TABLE positions (
    id TEXT PRIMARY KEY,
    connection_id TEXT REFERENCES broker_connections(id),
    account_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    underlying TEXT NOT NULL,
    strategy_type TEXT,
    strategy_label TEXT,              -- User-defined
    qty INTEGER NOT NULL,             -- Signed
    entry_price REAL NOT NULL,
    entry_date TIMESTAMP NOT NULL,
    current_price REAL,
    unrealized_pnl REAL,
    realized_pnl REAL,
    tags TEXT,                        -- JSON array
    notes TEXT,
    status TEXT DEFAULT 'OPEN',       -- OPEN, CLOSED, EXPIRED, ASSIGNED
    closed_at TIMESTAMP,
    closed_price REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Position legs
CREATE TABLE position_legs (
    id TEXT PRIMARY KEY,
    position_id TEXT REFERENCES positions(id),
    option_symbol TEXT NOT NULL,
    strike REAL NOT NULL,
    expiry DATE NOT NULL,
    put_call TEXT NOT NULL,
    action TEXT NOT NULL,             -- BUY, SELL
    qty INTEGER NOT NULL,
    entry_price REAL NOT NULL,
    current_price REAL,
    delta REAL, gamma REAL, theta REAL, vega REAL,
    charm REAL, color REAL, vanna REAL, volga REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Closed trades (history)
CREATE TABLE closed_trades (
    id TEXT PRIMARY KEY,
    position_id TEXT REFERENCES positions(id),
    symbol TEXT NOT NULL,
    strategy_type TEXT,
    entry_date TIMESTAMP NOT NULL,
    exit_date TIMESTAMP NOT NULL,
    entry_price REAL NOT NULL,
    exit_price REAL NOT NULL,
    qty INTEGER NOT NULL,
    gross_pnl REAL NOT NULL,
    fees REAL DEFAULT 0,
    net_pnl REAL NOT NULL,
    hold_duration_hours REAL,
    max_favorable REAL,               -- MFE
    max_adverse REAL,                 -- MAE
    exit_reason TEXT,                 -- TARGET, STOP, ROLL, EXPIRED, MANUAL
    notes TEXT
);

-- Sync log
CREATE TABLE sync_log (
    id TEXT PRIMARY KEY,
    connection_id TEXT REFERENCES broker_connections(id),
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    status TEXT,                      -- SUCCESS, PARTIAL, FAILED
    positions_synced INTEGER,
    error_message TEXT
);
```

---

## Security Considerations

- **Credential Storage:** Encrypt with `cryptography.Fernet`, key from OS keyring
- **Token Refresh:** Automatic OAuth2 refresh (Tastytrade)
- **Least Privilege:** Read-only API scopes where possible
- **Audit Log:** All sync/position changes logged
- **Session Management:** Auto-logout, re-auth for sensitive actions

---

## Acceptance Criteria

- [ ] Connects to Tastytrade via OAuth, syncs positions in <5s
- [ ] Manual CSV import works for unsupported brokers
- [ ] Real-time P&L updates within 5s of market data
- [ ] Aggregated Greeks match sum of position Greeks
- [ ] Strategy auto-detection: >90% accuracy for common strategies
- [ ] Position alerts fire correctly (assignment, gamma flip, theta)
- [ ] Risk limits enforceable with dashboard warnings
- [ ] Multi-account, multi-broker support
- [ ] Credentials encrypted at rest, never in logs
- [ ] Sync resilient to network failures (retry, partial sync)
- [ ] Performance: 100 positions sync <3s, P&L refresh <500ms
- [ ] Unit tests: connectors, analytics, strategy detection
- [ ] Integration test: full sync → analytics → alert flow

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Broker API changes | Versioned connectors, adapter pattern, automated tests |
| Credential security | Encryption, keyring, read-only scopes, audit logs |
| Sync conflicts (multi-device) | Last-write-wins with timestamp, user notification |
| API rate limits | Respect limits, exponential backoff, caching |
| Tax lot complexity | FIFO default, user override, export for CPA |
| Assignment prediction accuracy | Conservative thresholds, clear "estimate" labeling |

---

## Future Enhancements

- **Paper Trading:** Simulated positions with real market data
- **Strategy Templates:** One-click deploy common strategies
- **Auto-Roll:** Rules-based rolling (e.g., "roll 7 DTE at 4 PM")
- **Tax Optimization:** Tax-loss harvesting suggestions
- **Portfolio Optimization:** Risk parity, delta-neutral targeting
- **Social/Copy Trading:** Follow other traders' positions
- **API for External Tools:** Webhook for position changes
- **Institutional Features:** Sub-accounts, compliance reporting