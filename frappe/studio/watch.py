"""Watch every installed app's `<app>/studio` folder and import changed JSON into the DB.

Lets apps, pages and components generated on disk (by the CLI or an AI agent) show up without a
`bench migrate`. Started automatically per site by the `before_request` hook
under `bench serve`, or explicitly via `bench --site <site> studio-watch`.

Only `.json` is watched: an exported page's script lives in a sibling `.ts` that the runtime loads
straight off disk, and the vite dev server already hot-reloads those.
"""

import os
import threading

import frappe

from studio.sync_json import get_studio_folders, sync_file

try:
	from watchdog.events import FileSystemEventHandler
	from watchdog.observers import Observer

	WATCHDOG_AVAILABLE = True
except ImportError:
	# watchdog is a dev-only dependency (see pyproject.toml). Keep the module importable — the
	# `before_request` hook imports it on every request — and let start_watcher report it.
	FileSystemEventHandler = object
	WATCHDOG_AVAILABLE = False

# Coalesce the burst of events one save produces — watchdog reports created + modified, and many
# editors write to a temp file and rename over the target.
DEBOUNCE_SECONDS = 0.3

# site -> observer, or None if this process won't watch it. Both outcomes are cached: the decision
# can't change while the process lives, and this runs on every request.
_watchers: dict[str, object | None] = {}
_watchers_lock = threading.Lock()


def ensure_watcher_running():
	"""`before_request` hook: decide once per site whether to watch, then stay out of the way.

	Runs on every request — including production, where the answer is always no — so every call
	after the first must cost nothing but the dict lookup.
	"""
	site = frappe.local.site
	if site in _watchers:
		return

	with _watchers_lock:
		if site not in _watchers:
			_watchers[site] = start_watcher(site) if can_watch() else None


def can_watch() -> bool:
	# Exports only happen in developer mode (studio.export.can_export), so without it there is
	# nothing on disk to sync back.
	if not frappe.conf.developer_mode:
		return False
	# Only inside `bench serve`'s reloader child, which werkzeug marks with WERKZEUG_RUN_MAIN.
	# Gunicorn never sets it, so production's workers don't each start a watcher and race to
	# import the same file. Use `bench studio-watch` there instead.
	return os.environ.get("WERKZEUG_RUN_MAIN") == "true"


def watch(site: str):
	"""Watch until interrupted. Entry point for `bench studio-watch`."""
	observer = start_watcher(site)
	if not observer:
		return

	try:
		while observer.is_alive():
			observer.join(1)
	except KeyboardInterrupt:
		observer.stop()
	observer.join()


def start_watcher(site: str):
	"""Start a background observer for `site`. Returns None if it can't run."""
	if not WATCHDOG_AVAILABLE:
		# say so rather than silently leaving the site out of sync
		print("[studio-watch] watchdog not installed — run `bench setup requirements --dev studio`")
		return None

	folders = get_studio_folders()
	if not folders:
		print("[studio-watch] no studio folder found in any installed app")
		return None

	observer = Observer()
	observer.daemon = True
	handler = StudioSyncHandler(site)
	for folder in folders:
		observer.schedule(handler, folder, recursive=True)
	observer.start()

	print(f"[studio-watch] watching {len(folders)} studio folder(s) for {site}")
	return observer


class StudioSyncHandler(FileSystemEventHandler):
	"""Debounces watchdog events and imports the changed JSON.

	Deletes are deliberately ignored — a git checkout or branch switch would otherwise silently
	drop docs from the DB. `bench migrate` stays the way to reconcile removals.
	"""

	def __init__(self, site: str):
		super().__init__()
		self.site = site
		self.pending: set[str] = set()
		self.lock = threading.Lock()
		self.timer: threading.Timer | None = None

	def on_created(self, event):
		self.queue(event.src_path, event.is_directory)

	def on_modified(self, event):
		self.queue(event.src_path, event.is_directory)

	def on_moved(self, event):
		# editors commonly write a temp file and rename it over the target
		self.queue(event.dest_path, event.is_directory)

	def queue(self, path: str, is_directory: bool):
		if is_directory or not path.endswith(".json"):
			return

		with self.lock:
			self.pending.add(path)
			self.restart_timer()

	def restart_timer(self):
		if self.timer:
			self.timer.cancel()
		self.timer = threading.Timer(DEBOUNCE_SECONDS, self.flush)
		self.timer.daemon = True
		self.timer.start()

	def flush(self):
		with self.lock:
			paths, self.pending = self.pending, set()

		# `frappe.local` is a ContextVar, so this timer thread starts without one and needs its
		# own connection. Connecting per flush also avoids holding one open while idle.
		frappe.init(self.site)
		frappe.connect()
		try:
			for path in sorted(paths):
				self.sync(path)
		finally:
			frappe.destroy()

	def sync(self, path: str):
		try:
			if info := sync_file(path):
				# the import ran the doc's on_update, which broadcasts studio_doc_update
				# (source "disk") after this commit — that's what refreshes open editors/previews
				frappe.db.commit()
				print(f"[studio-watch] synced {info['doctype']} from {os.path.basename(path)}")
		except Exception:
			# A half-written or malformed file must not take the watcher down with it.
			frappe.db.rollback()
			print(f"[studio-watch] failed to sync {path}\n{frappe.get_traceback()}")
