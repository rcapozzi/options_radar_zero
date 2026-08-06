# Roadmap Item 1: Real-time WebSocket Alert System

**Status:** Proposed
**Priority:** High
**Target Release:** v0.3.0
**Estimated Effort:** 2-3 weeks

---

## Overview

Implement a WebSocket-based alert system that receives real-time alerts from external sources (e.g., options scanners, unusual activity detectors, news feeds) and displays them to the user both on the web dashboard and via system/browser notifications.

---

## Problem Statement

Currently, the dashboard only visualizes historical/polled data. Traders need immediate notification of:
- Unusual options activity (large sweeps, block trades)
- Gamma/theta exposure threshold breaches
- Price level alerts (strikes, support/resistance)
- News-driven volatility spikes
- Custom user-defined criteria (e.g., "notify when SPY 0DTE call volume > 50k at strike")

---

## Technical Design

### Architecture

```
┌─────────────────┐     WebSocket      ┌──────────────────┐
│  Alert Source   │ ─────────────────> │  Dash App        │
│  (external)     │   wss://alerts/    │  (frontend)      │
└─────────────────┘                    └────────┬─────────┘
                                                │
                    ┌───────────────────────────┼───────────────────────┐
                    ▼                           ▼                       ▼
            ┌───────────────┐           ┌───────────────┐       ┌───────────────┐
            │  Alert Panel  │           │ Toast/Modal   │       │ System/Browser│
            │  (sidebar)    │           │ Notifications │       │ Notification  │
            └───────────────┘           └───────────────┘       └───────────────┘
```

### Components

#### 1. WebSocket Client (`src/options_radar_zero/alerts/ws_client.py`)
- Async WebSocket client using `websockets` or `aiohttp`
- Auto-reconnect with exponential backoff
- Message parsing/validation (JSON schema)
- Heartbeat/ping-pong for connection health
- Auth token management (JWT/API key)

#### 2. Alert Store (`src/options_radar_zero/alerts/store.py`)
- In-memory ring buffer (last 500 alerts)
- Persistence to SQLite for session recovery
- Filtering/query API (by symbol, severity, time range)
- TTL-based cleanup (configurable, default 24h)

#### 3. Dash Components (`src/options_radar_zero/components/alerts.py`)
- `AlertPanel`: Collapsible sidebar with filterable alert list
- `AlertToast`: Transient toast notifications (top-right)
- `AlertModal`: Critical alert modal (requires acknowledgment)
- Real-time updates via `dcc.Interval` polling or Dash WebSocket component

#### 4. Notification Service (`src/options_radar_zero/alerts/notifications.py`)
- Browser Notification API (requires user permission)
- System notifications via `plyer` (cross-platform)
- Sound alerts (configurable per severity)
- Email/webhook fallback for critical alerts

### Alert Schema (JSON)

```json
{
  "id": "uuid",
  "timestamp": "2026-08-06T13:45:00Z",
  "source": "unusual-whales|gamma-lab|custom",
  "symbol": "SPY",
  "alert_type": "unusual_volume|gamma_flip|price_level|news",
  "severity": "info|warning|critical",
  "title": "Large Call Sweep Detected",
  "message": "SPY 450C 0DTE: 25k contracts at $2.15 (avg size 500)",
  "data": {
    "strike": 450,
    "expiry": "2026-08-06",
    "volume": 25000,
    "premium": 2.15,
    "side": "call"
  },
  "actions": [
    {"label": "View Chain", "action": "navigate", "target": "/chain/SPY"},
    {"label": "Dismiss", "action": "dismiss"}
  ]
}
```

---

## User Experience

### Dashboard Integration
- **Alert Bell Icon** (top nav): Shows unread count, opens panel
- **Sidebar Panel**: Filterable, sortable table with columns: Time, Symbol, Type, Severity, Message
- **Toast Stack**: 3-5 concurrent toasts, auto-dismiss after 10s (configurable)
- **Critical Modal**: Blocks interaction until acknowledged

### Notification Permissions Flow
1. First visit → Banner: "Allow notifications for real-time alerts?"
2. User clicks "Allow" → Browser permission prompt
3. On grant → Test notification sent
4. Settings page: Toggle browser/system/sound per severity

### Settings (New Page/Modal)
- WebSocket endpoint URL
- Reconnect settings
- Severity filters (which levels trigger toast/modal/sound)
- Symbol watchlist (only alert for these)
- Sound selection per severity
- Auto-dismiss timeout

---

## Implementation Phases

### Phase 1: Core Infrastructure (Week 1)
- [ ] WebSocket client with reconnection
- [ ] Alert schema validation (Pydantic)
- [ ] In-memory alert store with TTL
- [ ] Basic Dash callback to poll store

### Phase 2: UI Components (Week 1-2)
- [ ] AlertPanel component (sidebar)
- [ ] AlertToast component
- [ ] Filtering/sorting in panel
- [ ] Unread count badge

### Phase 3: Notifications (Week 2)
- [ ] Browser Notification API integration
- [ ] System notifications (plyer)
- [ ] Sound alerts
- [ ] Permission request flow

### Phase 4: Polish & Config (Week 2-3)
- [ ] Settings page
- [ ] Persistence (SQLite)
- [ ] Tests (unit + integration)
- [ ] Documentation

---

## Dependencies

```toml
# pyproject.toml additions
[tool.uv.sources]
websockets = { version = ">=12.0" }
pydantic = { version = ">=2.0" }
plyer = { version = ">=2.1" }
```

---

## Configuration

```yaml
# config/alerts.yaml
websocket:
  url: "wss://alerts.example.com/ws"
  reconnect:
    max_attempts: 10
    base_delay: 1.0
    max_delay: 60.0
  heartbeat_interval: 30

alerts:
  max_stored: 500
  ttl_hours: 24
  persistence_path: "data/alerts.db"

notifications:
  browser:
    enabled: true
    request_permission_on_load: true
  system:
    enabled: true
  sound:
    enabled: true
    files:
      info: "sounds/alert-info.mp3"
      warning: "sounds/alert-warning.mp3"
      critical: "sounds/alert-critical.mp3"

ui:
  toast_max_concurrent: 5
  toast_auto_dismiss_seconds: 10
  panel_default_filters:
    severity: ["warning", "critical"]
    symbols: []
```

---

## Acceptance Criteria

- [ ] WebSocket connects on app start, auto-reconnects on failure
- [ ] Alerts appear in sidebar panel within 500ms of receipt
- [ ] Toast notifications appear for warning/critical alerts
- [ ] Browser notifications work after permission granted
- [ ] System notifications appear on macOS/Windows/Linux
- [ ] Critical alerts show modal requiring acknowledgment
- [ ] User can filter panel by symbol, severity, time range
- [ ] Settings persist across sessions
- [ ] Unit tests cover: WS client, store, schema validation
- [ ] Integration test: full alert flow from WS to UI

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| WebSocket connection instability | Exponential backoff, heartbeat, graceful degradation |
| Notification permission denied | Fallback to in-app toast only, clear guidance |
| Alert spam overwhelming user | Rate limiting, deduplication, severity thresholds |
| Mobile browser limitations | Progressive enhancement, no critical dependency |
| External source API changes | Versioned schema, adapter pattern for sources |

---

## Future Enhancements

- Alert correlation/grouping (related alerts)
- ML-based alert prioritization
- Custom alert rules engine (user-defined)
- Webhook forwarding (Slack, Discord, Telegram)
- Alert history export (CSV/JSON)
- Integration with trading journal