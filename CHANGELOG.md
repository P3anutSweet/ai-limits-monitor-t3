# Changelog

## 2026-11-16: first public release

- A live page for T3 Code's right-panel Preview tab, served on this PC only (`127.0.0.1:47823`). It has a narrow-panel layout, light and dark themes, mascots, meters with an even-pace tick, and status cards. It refreshes every 30 seconds.
- Data: the desktop edition's `latest.json` when it is fresh (`source: auto`), or the same usage readers as the desktop edition (`ai_limits_core_v1.py`).
- Security: the page answers only loopback `Host` names, serves only GET requests and token-free data, and sends no-store and nosniff headers plus a content security policy. The port is reserved exclusively, so a second copy stops with a message.
- Robustness: a `latest.json` snapshot is size-capped (2 MiB), must not be dated in the future, and is checked field by field. Only the displayed fields are passed on. Everything the page shows is escaped, long text wraps in narrow cards, and a missing mascot image shows the service's initial instead.
- Settings file `ai_limits_t3_settings.json` plus `AI_LIMITS_T3_<KEY>` environment overrides. `--demo` and `--once`.
- Mascot images under CC BY 4.0, with provenance in `avatars/`.
