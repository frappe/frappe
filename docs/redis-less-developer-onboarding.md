# Redis-less Frappe — Developer Onboarding

**Branch:** `feat/redis-less-developer-onboarding`  
**Author:** Varun Krishnamurthy <varun@vyogolabs.tech>  
**Commits:** `37fbfe9087`, `bdd1b2b452`, `db069101dd`, `8559f41b2a`  
**Status:** Ready for upstream PR (pending write-access to `frappe/frappe`)

---

## Overview

This feature allows Frappe (and ERPNext) to start and run **without a Redis instance**.  
When Redis is unavailable, Frappe automatically falls back to an in-memory cache rather than crashing.

**Goal:** Reduce developer onboarding friction. Setting up Redis is unnecessary for local dev/testing. A developer should be able to clone the repo, run `bench start`, and have a working site immediately.

---

## Problem Statement

Currently, Frappe requires Redis for:
1. **Caching** — `frappe.cache.get/set/…` calls throughout the codebase
2. **Background jobs** — `enqueue()` pushes work onto RQ (Redis Queue)
3. **Scheduler** — `rq-scheduler` dequeues from Redis

Without Redis, all three fail at startup with `ConnectionRefusedError`, and the site never comes up.

---

## Solution

### Auto-detection and fallback

`frappe/utils/redis_wrapper.py` — `setup_cache()` function:

```python
# Before (hard failure)
frappe.cache = RedisWrapper.from_url(redis_url)

# After (graceful fallback)
try:
    wrapper = RedisWrapper.from_url(redis_url)
    wrapper.ping()
    frappe.cache = wrapper
except redis.exceptions.ConnectionError:
    frappe.cache = MemoryCacheWrapper()
    frappe.local.use_memory_cache = True
```

A flag `frappe.local.use_memory_cache` is set so other subsystems can detect the mode.

You can also force memory-cache mode explicitly via `site_config.json`:
```json
{
  "use_memory_cache": true
}
```
or
```json
{
  "cache_backend": "memory"
}
```

---

## Files Changed

### 1. `frappe/utils/redis_wrapper.py`

**What was added:** `MemoryCacheWrapper` class and `setup_cache()` auto-detection.

`MemoryCacheWrapper` is a pure-Python drop-in that mirrors the `RedisWrapper` API using an in-memory `dict`. It supports:

| Method | Behaviour |
|---|---|
| `get / set / delete` | Standard key-value ops |
| `hget / hset / hdel / hgetall / hkeys` | Hash ops on nested dicts |
| `lpush / rpush / lrange / llen / lrem` | List ops |
| `expire / ttl / persist` | TTL management (via `time.time()`) |
| `exists / keys / scan_iter` | Key inspection |
| `incrby / decrby` | Atomic increment/decrement |
| `flush / flushall` | Clear all keys |
| `pubsub` | Returns a no-op stub (publish/subscribe silently discarded) |
| `execute_command` | Returns `{}` (stub — prevents crash in `system_health_report.py`) |

Cache is stored per-process in `frappe.local._memory_cache` (cleared on each request init, persistent across requests in long-lived processes like gunicorn workers).

> ⚠️ **Important:** `MemoryCacheWrapper` is **not shared** between processes. Each worker has its own copy. This is acceptable for development/single-node use, but is not suitable for production multi-worker deployments.

---

### 2. `frappe/utils/background_jobs.py`

**What was changed:** `enqueue()` runs jobs synchronously in Redis-less mode.

```python
def enqueue(method, ...):
    if frappe.local.conf.get("use_memory_cache") or isinstance(frappe.cache, MemoryCacheWrapper):
        if enqueue_after_commit:
            # Register to run after the current transaction commits
            # (avoids InnoDB lock-wait timeout — job would re-acquire the same row lock)
            frappe.db.after_commit.add(lambda: _run_sync(method, kwargs))
        else:
            _run_sync(method, kwargs)
        return
    # ... normal RQ enqueue path
```

**Why `after_commit` matters:** During setup wizard, `System Settings` is locked with `SELECT ... FOR UPDATE` for the full duration. If `enqueue()` ran inline before commit, the enqueued job would try to re-lock `System Settings` → InnoDB lock-wait timeout → wizard fails.

`get_queues()` also returns `[]` in Redis-less mode so that any queue-listing code doesn't crash.

---

### 3. `frappe/utils/scheduler.py`

**What was changed:** Scheduler sleeps instead of running jobs when Redis-less.

```python
def start_scheduler():
    if isinstance(frappe.cache, MemoryCacheWrapper):
        # No Redis queue → nothing to dequeue. Sleep forever so the process
        # stays alive (Procfile expects it) but doesn't consume CPU.
        while True:
            time.sleep(3600)
        return
    # ... normal scheduler path
```

**Why:** Without this, the scheduler would either crash (`get_redis_conn()` fails) or — worse — try to run scheduled jobs synchronously inside its own open DB connection, blocking every web request.

---

### 4. `frappe/commands/site.py`

**What was added:** `bench setup-wizard` CLI command.

#### Usage

```bash
# Minimum required options
bench --site mysite setup-wizard \
  --country India \
  --timezone Asia/Kolkata \
  --currency INR

# Full options (ERPNext)
bench --site mysite setup-wizard \
  --language English \
  --country Australia \
  --timezone Australia/Sydney \
  --currency AUD \
  --full-name "Administrator" \
  --email admin@mycompany.com \
  --password changeme \
  --company-name "My Company Pty Ltd" \
  --company-abbr MC \
  --chart-of-accounts "Standard"

# Run in background (returns immediately; progress logged to stdout)
bench --site mysite setup-wizard \
  --country India --timezone Asia/Kolkata --currency INR \
  --background
```

#### All options

| Option | Default | Description |
|---|---|---|
| `--language` | `English` | System language |
| `--country` | *(required)* | Country name |
| `--timezone` | *(required)* | Timezone string |
| `--currency` | *(required)* | ISO currency code |
| `--full-name` | `Administrator` | Admin full name |
| `--email` | `admin@example.com` | Admin email |
| `--password` | `admin` | Admin password |
| `--company-name` | *(none)* | Company name (ERPNext only) |
| `--company-abbr` | *(none)* | Company abbreviation (ERPNext only) |
| `--chart-of-accounts` | `Standard` | CoA template (ERPNext only) |
| `--background` | off | Fork to background, return immediately |

#### Why this command is needed

The browser setup wizard communicates progress via **socketio** (`publish_realtime("setup_task", ...)`). In a Redis-less or minimal container environment, socketio is disabled. The browser shows a frozen "Starting Frappe..." screen for the entire duration of setup (~1–8 min), giving no feedback. Users think it has hung.

The CLI command bypasses the browser entirely — it calls `setup_complete()` directly, which is idempotent (safe to run again on an already-configured site).

#### `--background` implementation

Uses `os.fork()`. The parent prints the child PID and exits cleanly. The child runs setup then calls `os._exit(0)` to avoid running click teardown hooks in the child process. Works on all Unix-like systems (Linux, macOS).

---

## Deployment Notes

### Container / S2I environments (SNE image)

The `run-no-redis.sh` script (in `docker-test/`, gitignored) already:
- Removes `worker`, `socketio`, and `schedule` from the Procfile
- Adds `--nothreading` to gunicorn (critical — prevents concurrent request DB lock contention during setup)
- Sets `use_memory_cache: true` in site config
- Optionally triggers `bench setup-wizard` automatically via `AUTO_SETUP=true` env var

### Bare metal / `bench start`

No special configuration needed. Just run `bench start` normally. If Redis is not running, Frappe will log:

```
Redis unavailable — falling back to MemoryCacheWrapper (in-memory cache)
```

and continue. Then run the setup wizard:

```bash
bench --site mysite setup-wizard --country "India" --timezone "Asia/Kolkata" --currency INR
```

### Production

No change. If Redis is available and reachable, the normal `RedisWrapper` path is taken. This feature only activates on Redis connection failure.

---

## Testing

All changes were tested end-to-end in a containerised ERPNext (SNE image) with Redis completely absent:

1. **Site startup** — Frappe started cleanly; logs showed `MemoryCacheWrapper` fallback ✅
2. **Setup wizard via CLI** — `bench execute ... setup_complete` returned `{"status": "ok"}` ✅
3. **Setup wizard via browser** — Completed after ~8 min (ERPNext `make_records` is slow); `/desk` loaded ✅
4. **System health report** — Previously crashed with `AttributeError: 'MemoryCacheWrapper' has no attribute 'execute_command'`; now works ✅
5. **`bench setup-wizard` command** — Confirmed command registered and callable ✅

Unit test coverage added in `frappe/tests/test_caching.py` (covers `MemoryCacheWrapper` operations and `setup_cache()` fallback path).

---

## Known Limitations

| Limitation | Impact | Workaround |
|---|---|---|
| Cache not shared between workers | Cache misses in multi-worker setups | Use single worker in dev (`--workers 1`) or use Redis for production |
| Pub/sub silently discarded | Realtime events (desk notifications, progress bars) don't work | Expected — acceptable for dev use |
| Scheduled jobs disabled | Background tasks (`send_email_digest` etc.) don't run | Run manually via `bench execute` or use Redis for jobs |
| `bench setup-wizard --background` Unix-only | Can't use `--background` on Windows | Run without `--background` on Windows |

---

## Commits Summary

| Commit | Description |
|---|---|
| `37fbfe9087` | `feat: Redis-less Frappe for developer onboarding` — core `MemoryCacheWrapper` + `setup_cache()` fallback |
| `bdd1b2b452` | `fix: disable scheduler and fix enqueue in Redis-less mode` — `after_commit` enqueue fix + scheduler sleep |
| `db069101dd` | `fix: add execute_command stub to MemoryCacheWrapper` — prevents crash in `system_health_report.py` |
| `8559f41b2a` | `feat: add bench setup-wizard CLI command` — browser-free setup wizard |

---

## PR Readiness Checklist

- [x] All commits pushed to `vyogotech/frappe` `develop` branch
- [x] Feature branch `feat/redis-less-developer-onboarding` up to date with `develop`
- [x] Tested end-to-end in containerised ERPNext
- [x] No breaking changes (Redis path unchanged; fallback only activates on connection failure)
- [ ] PR to `frappe/frappe` upstream — pending write access / collaborator invite
