# Changelog

## 1.1.0 (unreleased)

A fail-safe release. Every fix below closes a case where the SDK either injected a fault
the operator had switched off, or silently injected nothing while reporting to Gremlin that
it had. The minor bump is for one source-breaking change: `FailureFlag.enabled` is now a
read-only property.

### Fixed: the kill switch

- **`FAILURE_FLAGS_ENABLED` is parsed instead of merely detected.** The SDK previously
  enabled itself whenever the variable was present, whatever its value, so following the
  install docs' instruction to set it to `false` for proxy mode left the SDK live and
  injecting faults. `true`, `yes`, and `1` (case-insensitive) enable it; everything else,
  including `false` and `""`, does not. Unset was the only way off before.
- `enabled` is read from the environment on every access, so a `FailureFlag` constructed at
  import time is no longer stuck with a stale answer.

### Fixed: configuration that was silently discarded

- **`GREMLIN_SIDECAR_PORT` now accepts the forms the sidecar accepts.** The sidecar reads
  this variable as a listen address and requires a colon, so `:6032`, `0.0.0.0:6032`, and
  `localhost:6032` are its normal values -- and the SDK parsed it as a bare integer and
  discarded every one of them, quietly continuing to post to 5032. In a Pod where both
  containers share the variable, moving the port meant no experiment ever ran again. All
  four forms now resolve to the same endpoint; only the port is used, because a listen
  address says what the sidecar binds, not where to reach it.
- `FAILURE_FLAGS_ENDPOINT` must be `http` or `https`. `urlopen` would otherwise honour
  `file://`, reading a local file and parsing it as experiments.
- The fetch deadline is configurable: `FAILURE_FLAGS_TIMEOUT_MS` in milliseconds, or
  `timeout=` in seconds on the constructor.

### Fixed: effects that were silently ignored

Each of these brings the SDK back in line with the Go and Node SDKs, and each changes when
a fault actually fires.

- **An experiment with no `rate` is applied.** An absent or `null` rate means 1.0. It used
  to be fetched, reported as active, and never injected, so Gremlin recorded impact the
  application never felt. A `rate` that is present but is not a number in 0..1 is still
  skipped, and now says so in the debug log.
- **A fractional latency is applied.** JSON has one number type, so `{"latency": 1000}` and
  `{"latency": 1000.0}` are the same instruction, but only the whole number worked. A
  fractional `ms` inside a `latency` object was worse: it reported impact while sleeping
  zero.
- **A latency clause that resolves to no delay is no longer reported as impact.**
  `{"latency": {}}`, a negative delay, and a non-numeric `ms` all used to claim impact after
  sleeping zero. A negative delay also raised out of `time.sleep()` into the effect's own
  exception handler.
- **Infinite and `NaN` delays are rejected.** `time.sleep(inf)` hangs the caller forever.
- **The documented `name` key selects the exception type.** The cross-language error
  metadata form, `{"message": ..., "name": "TimeoutError"}`, was ignored: the SDK read only
  `module` and `className`, so the documented payload fell through to `ValueError`.
  `className` still wins when both are present.
- An experiment whose exception class cannot be loaded now raises a `ValueError` carrying
  the experiment's message rather than nothing at all. A class that resolves to a
  non-exception still falls back to `ValueError` rather than being called.

### Fixed: `invoke()` raising when it promised not to

`invoke()` documents that it never raises unless an active experiment says so. These all
broke that promise on the request path the library exists to protect:

- A non-string flag name (`None` out of a dict `.get()` is the ordinary way to get one)
  raised `TypeError: object of type 'NoneType' has no len()`.
- A non-callable `behavior=` raised `TypeError` whenever an experiment was active.
- A malformed sidecar response raised `KeyError('rate')`, or a `TypeError` for a non-dict
  experiment or a null effect.
- `labels` of the wrong type raised out of the request builder.

### Fixed: sidecar responses that are not trusted input

- **A `Content-Type` parameter no longer silences the SDK.** `application/json;
  charset=utf-8` is legal and common, and the header was compared exactly, so any proxy
  adding a parameter would have taken the whole Python fleet quiet with nothing but a debug
  log. Only the media type is compared now.
- A whitespace-only body with a positive `Content-Length` reached `json.loads("")` and
  raised out of the public `fetch()`.
- The no-experiment case is a bare `204`, which is now answered before the header checks
  instead of logging `unexpected Content-Type:` on every single call.

### Fixed: shared and borrowed state

- **`FailureFlag.data` is no longer a shared mutable default.** `data={}` was evaluated once
  at import, so every flag built without an explicit `data=` shared one dict process-wide.
- **`fetch()` no longer mutates the caller's `labels` dict.** It annotated the dict it was
  handed with `failure-flags-sdk-version`, so a module-level or reused dict silently grew a
  Gremlin key that then showed up in whatever else that dict fed. A copy is annotated now.
  As a side effect `labels=None` sends `{}` instead of raising.

### Breaking

- **`FailureFlag.enabled` is a read-only property.** Through 1.0.3 it was a plain attribute,
  so `flag.enabled = False` worked; it now raises `AttributeError`. Patch
  `FAILURE_FLAGS_ENABLED` in the environment instead. See the README for the migration.
