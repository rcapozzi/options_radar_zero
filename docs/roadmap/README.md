# Options Radar Zero — Product Roadmap

**Version:** 0.2.0 (current) → 0.5.0 (target)
**Last Updated:** 2026-08-06
**Status:** Active Development

---

## Overview

This roadmap outlines the strategic direction for Options Radar Zero, evolving from a real-time 0DTE chain visualization tool into a comprehensive options trading workspace with alerts, custom rules, mobile access, advanced analytics, and portfolio management.

---

## Roadmap Items

| # | Title | Priority | Target | Effort | Status |
|---|-------|----------|--------|--------|--------|
| 1 | [Real-time WebSocket Alert System](./01-websocket-alert-system.md) | High | v0.3.0 | 2-3 weeks | 📋 Proposed |
| 2 | [Custom Alert Rules Engine](./02-custom-alert-rules-engine.md) | High | v0.3.0 | 2-3 weeks | 📋 Proposed |
| 3 | [Mobile-Responsive PWA with Offline Support](./03-mobile-pwa-offline.md) | Medium | v0.4.0 | 3-4 weeks | 📋 Proposed |
| 4 | [Advanced Greeks Analytics & Visualization](./04-advanced-greeks-analytics.md) | Medium-High | v0.4.0 | 3-4 weeks | 📋 Proposed |
| 5 | [Portfolio Integration & Position Management](./05-portfolio-position-management.md) | High | v0.5.0 | 4-5 weeks | 📋 Proposed |

---

## Dependency Graph

```
v0.2.0 (Current)
    │
    ├──▶ 1. WebSocket Alert System ◀──┐
    │                                  │
    ├──▶ 2. Custom Alert Rules ────────┤ (depends on #1)
    │                                  │
    ├──▶ 3. Mobile PWA ────────────────┤ (independent)
    │                                  │
    ├──▶ 4. Advanced Greeks ───────────┤ (independent)
    │                                  │
    └──▶ 5. Portfolio Management ──────┘ (depends on #1, #2, #4)
```

---

## Release Timeline (Estimated)

| Release | Target Date | Features |
|---------|-------------|----------|
| **v0.2.x** | Current | Chain visualization, volume/OI plots, caching |
| **v0.3.0** | Q3 2026 | WebSocket Alerts (#1), Custom Rules (#2) |
| **v0.4.0** | Q4 2026 | Mobile PWA (#3), Advanced Greeks (#4) |
| **v0.5.0** | Q1 2027 | Portfolio Integration (#5) |

---

## Strategic Themes

### 1. **Real-Time Intelligence** (v0.3.0)
Move from passive visualization to active monitoring. Traders get alerted on meaningful events without staring at charts.

### 2. **Democratized Quant** (v0.3.0 → v0.4.0)
Custom rules engine and advanced Greeks put institutional analytics in every trader's hands — no coding required.

### 3. **Trading Anywhere** (v0.4.0)
Mobile PWA with offline support means never missing a critical alert or position update.

### 4. **Unified Workspace** (v0.5.0)
One dashboard for market analysis + position management = faster decisions, fewer errors.

---

## Current Sprint Focus

**v0.2.x Maintenance:**
- [ ] Stabilize caching (flask-caching migration complete ✓)
- [ ] Fix demo.py import warnings issue (resolved ✓)
- [ ] Improve test coverage (>90% ✓)
- [ ] Documentation updates

**Next Sprint (v0.3.0 kickoff):**
- [ ] Design WebSocket protocol for alert ingestion
- [ ] Implement CEL-based rules engine prototype
- [ ] Define alert schema with external partners

---

## Success Metrics

| Metric | Current | v0.3.0 Target | v0.5.0 Target |
|--------|---------|---------------|---------------|
| Alert Latency | N/A | <500ms | <200ms |
| Mobile Usability | Poor | Good | Excellent |
| Greeks Coverage | Basic (4) | Full (10+) | Full + Portfolio |
| Position Tracking | Manual | Semi-auto | Full Auto |
| User Session Time | ~5 min | >15 min | >30 min |
| Alert Accuracy | N/A | >80% precision | >90% precision |

---

## Contributing

Roadmap items are living documents. To propose changes:
1. Open an issue with `roadmap` label
2. Discuss in issue thread
3. Update relevant spec file via PR
4. Maintainers review and merge

See [CONTRIBUTING.md](../CONTRIBUTING.md) for details.

---

## Related Documentation

- [Architecture Overview](../ARCHITECTURE.md)
- [API Reference](../api-reference.md)
- [Deployment Guide](../deployment.md)
- [Tastytrade API Docs](../tastytrade-api/docs/)