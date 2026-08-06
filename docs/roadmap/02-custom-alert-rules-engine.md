# Roadmap Item 2: Custom Alert Rules Engine

**Status:** Proposed
**Priority:** High
**Target Release:** v0.3.0 (after WebSocket Alert System)
**Estimated Effort:** 2-3 weeks

---

## Overview

A flexible, user-configurable rules engine that allows traders to define custom alert conditions using a visual rule builder or DSL. Rules evaluate against real-time and historical data (options chains, Greeks, underlying price, volume, news sentiment) and trigger alerts through the WebSocket alert system.

---

## Problem Statement

Traders have highly specific strategies that generic alerts can't capture. Examples:
- "Alert when SPY 0DTE put/call ratio > 1.5 AND VIX < 15"
- "Notify when any 0DTE strike has gamma exposure > $50M within 5 points of spot"
- "Warn when 5-min realized vol > 2x implied vol for 3 consecutive candles"
- "Alert on unusual dark pool prints > $1M in SPY options"

Current solutions require coding or rigid pre-built alerts. A visual rules engine democratizes this capability.

---

## Technical Design

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Rules Engine                            │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Rule Parser  │  │  Evaluator   │  │  Data Provider   │  │
│  │  (DSL/AST)   │──▶│  (CEL/Expr)  │──▶│  (Chains, Greeks,│  │
│  └──────────────┘  └──────────────┘  │   Price, News)   │  │
│         ▲              ▲             └──────────────────┘  │
│         │              │                    ▲               │
│  ┌──────┴──────┐  ┌────┴──────┐            │               │
│  │ Rule Store  │  │  Scheduler│────────────┘               │
│  │ (SQLite)    │  │ (cron/evt)│                            │
│  └─────────────┘  └───────────┘                            │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │   Alert System        │
              │ (WebSocket/Notifications)│
              └───────────────────────┘
```

### Components

#### 1. Rule DSL (`src/options_radar_zero/rules/dsl.py`)
- Expression language: **CEL (Common Expression Language)** via `cel-py`
- Alternative: Custom Python-like DSL parsed to AST
- Type-safe with schema validation
- Built-in functions for common operations

**Example Rules:**
```cel
// Unusual volume at strike
chain.symbol == "SPY" &&
chain.expiry == today() &&
chain.put_call == "CALL" &&
chain.volume > chain.avg_volume_5d * 3 &&
chain.open_interest > 1000

// Gamma flip risk
greeks.net_gamma > 50_000_000 &&
abs(underlying.price - greeks.gamma_peak_strike) < 5

// Volume/vol divergence
realized_vol_5m > implied_vol * 2 &&
count(candles[-3:], c => c.realized_vol > c.implied_vol * 2) == 3

// Dark pool sweep
prints.source == "dark_pool" &&
prints.size > 1_000_000 &&
prints.symbol == "SPY"
```

#### 2. Data Provider Registry (`src/options_radar_zero/rules/data_provider.py`)
- Pluggable data sources with unified interface
- Sources: Option chains, Greeks, Underlying price, Candles, News, Dark pool prints
- Caching layer (1-5s TTL for real-time)
- Subscription model for efficient updates

#### 3. Rule Evaluator (`src/options_radar_zero/rules/evaluator.py`)
- Compiles CEL expressions to bytecode (cached)
- Evaluates against current data snapshot
- Supports streaming (incremental) and batch evaluation
- Returns: `Match` object with rule, data snapshot, timestamp

#### 4. Rule Store (`src/options_radar_zero/rules/store.py`)
- SQLite persistence (rules, folders, versions)
- CRUD API with validation
- Import/export (JSON/YAML)
- Version history for rollback

#### 5. Visual Rule Builder (`src/options_radar_zero/components/rule_builder.py`)
- Drag-and-drop UI (React-style via `dash-mantine-components`)
- Components: Field picker, Operator selector, Value input, Logic combiner (AND/OR/NOT)
- Live preview: shows matching historical events
- Template library (common patterns)

#### 6. Scheduler (`src/options_radar_zero/rules/scheduler.py`)
- Evaluation triggers:
  - **Event-driven**: On new chain tick, price update, print
  - **Time-based**: Every N seconds/minutes (cron)
  - **Hybrid**: Event-driven with debounce
- Deduplication: Prevent duplicate alerts within cooldown window
- Prioritization: Critical rules evaluate first

---

## User Experience

### Rule Management Page
```
/rules
├── /rules/list          # Table: Name, Status, Last Triggered, Severity, Actions
├── /rules/new           # Visual builder or DSL editor
├── /rules/:id/edit      # Edit existing
├── /rules/:id/history   # Trigger history with data snapshots
├── /rules/templates     # Pre-built templates (one-click clone)
└── /rules/import        # Import from JSON/YAML
```

### Visual Builder Flow
1. **Select Data Source** → Chain / Greeks / Price / Candles / News
2. **Pick Field** → e.g., `chain.volume`, `greeks.net_gamma`, `underlying.price`
3. **Choose Operator** → `>`, `<`, `>=`, `<=`, `==`, `!=`, `contains`, `between`, `crosses_above`, `crosses_below`
4. **Enter Value** → Number, formula, or reference another field
5. **Combine** → AND / OR / NOT groups (nestable)
6. **Set Alert Config** → Severity, cooldown, notification channels
7. **Test** → Run against last 30 days, show matches
8. **Save** → Name, folder, tags, description

### Rule Templates (Ship with App)
- "Unusual Call Volume" (0DTE, >3x avg)
- "Gamma Flip Risk" (net gamma > threshold near strike)
- "Put/Call Ratio Extreme" (>1.5 or <0.5)
- "IV/RV Divergence" (realized > 2x implied)
- "Large Dark Pool Print" (>$1M)
- "Strike Pin Risk" (price within 1% of major strike)
- "VIX Term Structure" (contango/backwardation signals)

---

## Implementation Phases

### Phase 1: Core Engine (Week 1)
- [ ] CEL integration, expression compilation/caching
- [ ] Data provider registry with mock sources
- [ ] Rule evaluator (single rule, snapshot)
- [ ] Rule store (SQLite, CRUD, validation)

### Phase 2: Data Providers (Week 1-2)
- [ ] Chain data provider (from existing cache)
- [ ] Greeks provider (compute from chain)
- [ ] Price/candle provider
- [ ] News provider (placeholder)

### Phase 3: Scheduler & Integration (Week 2)
- [ ] Event-driven evaluation (on chain update)
- [ ] Time-based scheduler (APScheduler)
- [ ] Deduplication/cooldown logic
- [ ] Integration with WebSocket alert system

### Phase 4: Visual Builder (Week 2-3)
- [ ] Field/operator/value component library
- [ ] Logic combiner (AND/OR/NOT tree)
- [ ] Live test panel (historical replay)
- [ ] Template gallery

### Phase 5: Polish (Week 3)
- [ ] Import/export
- [ ] Version history
- [ ] Tests (unit: evaluator, providers; integration: full flow)
- [ ] Documentation

---

## Dependencies

```toml
[tool.uv.sources]
cel-py = { version = ">=0.2" }  # Common Expression Language
apscheduler = { version = ">=3.10" }
```

---

## Configuration

```yaml
# config/rules.yaml
engine:
  expression_language: "cel"  # or "custom"
  max_expression_length: 5000
  compilation_cache_size: 1000

data_providers:
  chain:
    refresh_seconds: 1
    cache_ttl_seconds: 2
  greeks:
    refresh_seconds: 5
    model: "black_scholes"
  price:
    refresh_seconds: 1
  candles:
    timeframes: ["1m", "5m", "15m"]
    refresh_seconds: 10

scheduler:
  event_driven: true
  time_based_interval_seconds: 30
  max_concurrent_evaluations: 10
  default_cooldown_seconds: 60

storage:
  path: "data/rules.db"
  max_history_per_rule: 1000
  history_retention_days: 30

templates:
  builtin_path: "config/rule_templates/"
  user_template_path: "data/user_templates/"
```

---

## Rule Schema (Storage)

```sql
CREATE TABLE rules (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    expression TEXT NOT NULL,      -- CEL expression
    expression_hash TEXT NOT NULL, -- for change detection
    severity TEXT NOT NULL,        -- info|warning|critical
    cooldown_seconds INTEGER DEFAULT 60,
    enabled BOOLEAN DEFAULT 1,
    folder_id TEXT,
    tags TEXT,                     -- JSON array
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    version INTEGER DEFAULT 1,
    created_by TEXT
);

CREATE TABLE rule_history (
    id TEXT PRIMARY KEY,
    rule_id TEXT REFERENCES rules(id),
    triggered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    data_snapshot TEXT,            -- JSON of matched data
    actions_taken TEXT             -- JSON: ["toast", "notification", "webhook"]
);
```

---

## Acceptance Criteria

- [ ] User can create rule via visual builder without writing code
- [ ] Rule evaluates correctly against live data
- [ ] Alert triggers within 1s of condition met
- [ ] Cooldown prevents duplicate alerts
- [ ] Historical test shows matches for last 30 days
- [ ] Rules persist across app restarts
- [ ] Import/export works (JSON/YAML)
- [ ] Templates can be cloned and modified
- [ ] Unit tests: evaluator accuracy, provider contracts
- [ ] Integration test: rule → alert → notification flow

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| CEL expression injection | Sandboxed evaluation, no arbitrary code execution |
| Performance (many rules) | Compiled bytecode caching, incremental evaluation, priority queue |
| False positives | Historical backtesting, cooldown, severity tuning |
| Complex UI overwhelming | Progressive disclosure, templates, guided wizard |
| Data latency | Clear TTL config, stale data warnings in UI |

---

## Future Enhancements

- ML-assisted rule generation ("create rule like this alert")
- Rule composition (rules as building blocks)
- Backtesting engine with P&L simulation
- Community template marketplace
- Natural language → rule (LLM-assisted)
- Rule performance analytics (precision/recall)