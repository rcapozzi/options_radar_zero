# Roadmap Item 3: Mobile-Responsive PWA with Offline Support

**Status:** Proposed
**Priority:** Medium
**Target Release:** v0.4.0
**Estimated Effort:** 3-4 weeks

---

## Overview

Transform the dashboard into a Progressive Web App (PWA) with full mobile responsiveness, offline caching, and native-like experience on iOS/Android. Enable traders to monitor positions and receive alerts on mobile devices without a native app.

---

## Problem Statement

The current dashboard is desktop-first with poor mobile usability:
- Tables overflow horizontally on mobile
- Touch interactions don't work well (hover tooltips, small targets)
- No offline capability - loses connection = blank screen
- Can't install to home screen
- No push notifications when browser closed
- Charts not optimized for small screens

Traders need to monitor positions during commute, away from desk, or when primary connection fails.

---

## Technical Design

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      PWA Architecture                        │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Service Worker (SW)                     │    │
│  │  ┌─────────────┐ ┌─────────────┐ ┌──────────────┐   │    │
│  │  │  Cache      │ │  Fetch      │ │  Background  │   │    │
│  │  │  Strategy   │ │  Handler    │ │  Sync        │   │    │
│  │  └─────────────┘ └─────────────┘ └──────────────┘   │    │
│  └─────────────────────────────────────────────────────┘    │
│                          │                                   │
├──────────────────────────┼──────────────────────────────────┤
│  ┌─────────────────────┐ ▼ ┌─────────────────────────────┐  │
│  │  App Shell          │   │  Content Pages              │  │
│  │  (HTML/CSS/JS)      │   │  (lazy-loaded)              │  │
│  │  - Header/Nav       │   │  - Chain View               │  │
│  │  - Alert Panel      │   │  - Greeks View              │  │
│  │  - Settings         │   │  - Rules Engine             │  │
│  │  - Offline Indicator│   │  - Alert History            │  │
│  └─────────────────────┘   └─────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Components

#### 1. Service Worker (`public/sw.js` via `dash-extensions` or custom)
- **Cache Strategies:**
  - App Shell: `CacheFirst` (immutable, versioned)
  - API Data: `StaleWhileRevalidate` (5min TTL)
  - Static Assets: `CacheFirst` (1yr)
  - WebSocket: Network only (fallback to cached alerts)
- **Background Sync:** Queue alert acknowledgments, rule saves for when online
- **Push Notifications:** Handle `push` events, show notifications
- **Periodic Sync:** Refresh cached chains every 5min when online

#### 2. Responsive Layout System (`src/options_radar_zero/components/layout.py`)
- **Breakpoints:** Mobile (<640px), Tablet (640-1024px), Desktop (>1024px)
- **CSS Grid/Flexbox** via `dash-mantine-components` responsive props
- **Component Variants:** Mobile-first design, progressive enhancement

**Key Layout Changes:**
```
Desktop:                    Mobile:
┌─────────────────────┐     ┌─────────────┐
│ Sidebar | Main      │     │ ☰ Menu      │
│ Chain   | Greeks    │     │ ┌─────────┐ │
│ Volume  | OI        │     │ │ Chain   │ │
└─────────────────────┘     │ │ (swipe) │ │
                            │ ├─────────┤ │
                            │ │ Greeks  │ │
                            │ │ (tab)   │ │
                            └─────────────┘
```

#### 3. Mobile-Optimized Components

**Tables → Cards/List Views**
- Chain table → Expandable cards per strike
- Greeks table → Horizontal scroll cards
- Alert history → Timeline cards

**Charts → Touch-Friendly**
- Plotly `config`: `scrollZoom: true`, `displayModeBar: 'hover'`
- Custom touch gestures: pinch-zoom, pan, double-tap reset
- Responsive sizing: full-width, aspect-ratio preserved
- Simplified mode: fewer traces, larger touch targets

**Forms/Inputs**
- Native date/time pickers
- Select → Searchable combobox (mobile-friendly)
- Numeric inputs with stepper buttons
- Toggle switches instead of checkboxes

#### 4. Offline State Management (`src/options_radar_zero/offline/`)
- **IndexedDB** (via `idb` or `localforage`) for:
  - Last known chains/Greeks (compressed)
  - User preferences
  - Pending mutations (rule saves, alert acks)
  - Alert history (last 100)
- **Online/Offline Detection:** `navigator.onLine` + heartbeat API
- **Conflict Resolution:** Last-write-wins with timestamp, manual merge for complex

#### 5. Push Notifications (`src/options_radar_zero/pwa/push.py`)
- **Web Push Protocol** (VAPID keys)
- Subscription management (register, unregister, update)
- Payload encryption
- Fallback to in-app when push unavailable

#### 6. Install Prompt (`src/options_radar_zero/components/pwa_prompt.py`)
- Custom install banner (not native mini-infobar)
- Shows after 2+ visits, 30s engagement
- Dismissible, remembers choice
- iOS: Shows "Add to Home Screen" instructions

---

## User Experience

### Mobile Navigation
- **Bottom Tab Bar** (primary): Chain | Greeks | Alerts | Rules | Settings
- **Hamburger Menu** (secondary): Profile, Help, Logout
- **Swipe Gestures:** Left/right between main views
- **Pull-to-Refresh:** On chain/Greeks views

### Offline Experience
- **Banner:** "You're offline. Showing cached data from 13:42"
- **Indicators:** Grayed-out timestamps, stale data warnings
- **Actions:** Queue alert dismissals, rule edits sync when online
- **Cache Status:** Settings page shows "Last synced: 2 min ago"

### Install Flow
1. User visits 3+ times, spends >30s each
2. Custom banner: "Install Options Radar for offline access & push alerts"
3. Click "Install" → Browser prompt → Home screen icon
4. Launch from home screen → Full-screen, no browser chrome

### Settings (Mobile-Specific)
- Data saver mode (reduce polling frequency)
- Chart quality (full/simplified)
- Notification channels (push, in-app, sound)
- Cache size limit (auto-cleanup)
- Biometric lock (optional)

---

## Implementation Phases

### Phase 1: PWA Foundation (Week 1)
- [ ] Service Worker with Workbox (or custom)
- [ ] Web App Manifest (`manifest.json`)
- [ ] HTTPS enforcement (required for PWA)
- [ ] App shell caching
- [ ] Basic offline page

### Phase 2: Responsive Layout (Week 1-2)
- [ ] Mobile-first CSS reset
- [ ] Breakpoint-aware layout components
- [ ] Bottom tab navigation
- [ ] Swipeable views
- [ ] Touch-friendly tables → cards

### Phase 3: Charts & Interactions (Week 2)
- [ ] Plotly mobile config
- [ ] Touch gestures (pinch, pan, tap)
- [ ] Simplified chart mode
- [ ] Responsive legend/tooltips

### Phase 4: Offline & Sync (Week 2-3)
- [ ] IndexedDB schema & wrapper
- [ ] Cache strategies per data type
- [ ] Background sync for mutations
- [ ] Conflict resolution
- [ ] Online/offline UI states

### Phase 5: Push & Install (Week 3-4)
- [ ] VAPID key generation
- [ ] Push subscription management
- [ ] Push event handling
- [ ] Custom install prompt
- [ ] iOS "Add to Home Screen" guide

### Phase 6: Polish & Testing (Week 4)
- [ ] Lighthouse PWA audit >90
- [ ] Cross-browser: Chrome, Safari, Firefox, Edge
- [ ] Device testing: iOS Safari, Chrome Android
- [ ] Performance: <3s TTI on 3G
- [ ] Accessibility: WCAG 2.1 AA

---

## Dependencies

```toml
[tool.uv.sources]
# Service Worker generation
workbox = { version = ">=7.0", extras = ["cli"] }

# IndexedDB wrapper
idb = { version = ">=8.0" }

# Web Push
pywebpush = { version = ">=2.0" }

# PWA utilities (if using dash-extensions)
dash-extensions = { version = ">=0.1" }
```

---

## Configuration

```yaml
# config/pwa.yaml
pwa:
  name: "Options Radar"
  short_name: "OptRadar"
  description: "Real-time 0DTE options chain analytics"
  theme_color: "#6366f1"
  background_color: "#0b0d10"
  display: "standalone"
  orientation: "portrait-primary"
  scope: "/"
  start_url: "/"

manifest:
  icons:
    - src: "icons/icon-72.png"
      sizes: "72x72"
      type: "image/png"
    - src: "icons/icon-96.png"
      sizes: "96x96"
      type: "image/png"
    - src: "icons/icon-128.png"
      sizes: "128x128"
      type: "image/png"
    - src: "icons/icon-144.png"
      sizes: "144x144"
      type: "image/png"
    - src: "icons/icon-152.png"
      sizes: "152x152"
      type: "image/png"
    - src: "icons/icon-192.png"
      sizes: "192x192"
      type: "image/png"
      purpose: "any maskable"
    - src: "icons/icon-384.png"
      sizes: "384x384"
      type: "image/png"
    - src: "icons/icon-512.png"
      sizes: "512x512"
      type: "image/png"

service_worker:
  cache_strategies:
    app_shell: "CacheFirst"
    api_data: "StaleWhileRevalidate"
    static_assets: "CacheFirst"
  api_cache_ttl_seconds: 300
  max_cache_size_mb: 50
  cleanup_interval_hours: 24

push:
  vapid_public_key: "ENV_VAR"
  vapid_private_key: "ENV_VAR"
  vapid_subject: "mailto:alerts@example.com"

offline:
  indexed_db_name: "options-radar-offline"
  max_chain_cache_age_hours: 24
  max_alert_history: 100
  pending_mutations_max: 50

install_prompt:
  min_visits: 3
  min_engagement_seconds: 30
  dismiss_cooldown_days: 7
```

---

## Web App Manifest (Generated)

```json
{
  "name": "Options Radar",
  "short_name": "OptRadar",
  "description": "Real-time 0DTE options chain analytics with alerts",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#0b0d10",
  "theme_color": "#6366f1",
  "orientation": "portrait-primary",
  "scope": "/",
  "icons": [...],
  "categories": ["finance", "productivity"],
  "shortcuts": [
    {
      "name": "SPY Chain",
      "url": "/chain/SPY",
      "description": "View SPY 0DTE chain"
    },
    {
      "name": "Alerts",
      "url": "/alerts",
      "description": "View active alerts"
    }
  ]
}
```

---

## Acceptance Criteria

- [ ] Lighthouse PWA score >90 (all categories)
- [ ] Works offline: shows cached chains, alerts, rules
- [ ] Installs on iOS (Add to Home Screen) and Android (WebAPK)
- [ ] Push notifications received when app closed
- [ ] Mobile layout: no horizontal scroll, touch targets ≥48px
- [ ] Charts usable on mobile: pinch-zoom, pan, readable
- [ ] Data syncs automatically when coming online
- [ ] Pending actions (dismiss alert, save rule) queue offline
- [ ] Cache auto-cleanup prevents storage bloat
- [ ] Works on iOS Safari 15+, Chrome Android 100+
- [ ] Accessible: screen reader, keyboard nav, contrast

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| iOS PWA limitations (no push, storage limits) | Graceful degradation, clear messaging, focus on in-app notifications |
| Service Worker debugging difficulty | Workbox devtools, comprehensive logging, test matrix |
| Cache invalidation complexity | Versioned caches, clear update strategy, user-visible update banner |
| IndexedDB quota exceeded | LRU eviction, user-configurable limits, quota monitoring |
| Mobile chart performance | Simplified mode, canvas/WebGL, data decimation |

---

## Future Enhancements

- Background fetch for periodic updates
- Widget/Glance support (iOS Lock Screen, Android Widget)
- Share API (share chain snapshot)
- File System Access API (export data)
- Badging API (unread count on icon)
- Periodic Background Sync (refresh every 15min)