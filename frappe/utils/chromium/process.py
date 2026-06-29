from typing import ClassVar

import frappe
from frappe import _

# Chrome flags for headless PDF/screenshot use.
# Playwright adds --headless and --remote-debugging-pipe automatically — don't duplicate them.
# https://peter.sh/experiments/chromium-command-line-switches/
CHROMIUM_LAUNCH_ARGS = [
	"--disable-gpu",
	"--disable-field-trial-config",
	"--disable-background-networking",
	"--disable-background-timer-throttling",
	"--disable-backgrounding-occluded-windows",
	"--disable-back-forward-cache",
	"--disable-breakpad",
	"--disable-client-side-phishing-detection",
	"--disable-component-extensions-with-background-pages",
	"--disable-component-update",
	"--no-default-browser-check",
	"--disable-default-apps",
	"--disable-dev-shm-usage",
	"--disable-extensions",
	"--disable-features=ImprovedCookieControls,LazyFrameLoading,GlobalMediaControls,DestroyProfileOnBrowserClose,MediaRouter,DialMediaRouteProvider,AcceptCHFrame,AutoExpandDetailsElement,CertificateTransparencyComponentUpdater,AvoidUnnecessaryBeforeUnloadCheckSync,Translate,HttpsUpgrades,PaintHolding,ThirdPartyStoragePartitioning,LensOverlay,PlzDedicatedWorker",
	"--allow-pre-commit-input",
	"--disable-hang-monitor",
	"--disable-ipc-flooding-protection",
	"--disable-popup-blocking",
	"--disable-prompt-on-repost",
	"--disable-renderer-backgrounding",
	"--force-color-profile=srgb",
	"--metrics-recording-only",
	"--no-first-run",
	"--password-store=basic",
	"--use-mock-keychain",
	"--no-service-autorun",
	"--export-tagged-pdf",
	"--disable-search-engine-choice-screen",
	"--unsafely-disable-devtools-self-xss-warnings",
	"--enable-use-zoom-for-dsf=false",
	"--use-angle",
	"--hide-scrollbars",
	"--mute-audio",
	"--blink-settings=primaryHoverType=2,availableHoverTypes=2,primaryPointerType=4,availablePointerTypes=4",
	"--no-sandbox",
	"--no-startup-window",
]


class ChromiumManager:
	_instance = None
	_browsers: ClassVar[list] = []

	def add_browser(self, browser):
		self._browsers.append(browser)

	def remove_browser(self, browser):
		if browser in self._browsers:
			self._browsers.remove(browser)

	def __new__(cls):
		# Rebuild singleton when the Playwright browser connection is lost.
		if cls._instance is None:
			cls._instance = super().__new__(cls)
		elif getattr(cls._instance, "_browser", None) is not None:
			if not cls._instance._browser.is_connected():
				cls._instance = super().__new__(cls)
		return cls._instance

	def __init__(self):
		if hasattr(self, "_initialized"):
			return
		self._initialized = True
		self._playwright = None
		self._browser = None
		self._initialize_chromium()

	def _initialize_chromium(self):
		site_config = frappe.get_common_site_config()
		self.debug_mode = frappe.conf.developer_mode and bool(frappe.form_dict.get("pdf_debug"))

		# Connect to an external Chromium over CDP (separate docker/server).
		ws_url = site_config.get("chromium_websocket_url", "")
		if ws_url:
			frappe.warn("Using external chromium websocket url. Make sure it is accessible.")
			self._connect_playwright_cdp(ws_url)
			return

		# Optional: point at a custom binary via chromium_path in common_site_config.json.
		# If not set, Playwright uses chrome-headless-shell installed by bench setup-chrome.
		executable_path = None
		if custom_path := site_config.get("chromium_path", ""):
			import shutil

			executable_path = shutil.which(custom_path) or custom_path

		self._launch_playwright_browser(executable_path=executable_path)

	def _launch_playwright_browser(self, executable_path=None):
		"""Launch chrome-headless-shell via Playwright.

		Uses chrome-headless-shell (~136 MB, headless-only) instead of full
		Chromium (~280 MB). Playwright manages the process lifecycle entirely —
		no subprocess management, no stderr polling, no port selection needed.

		If chrome-headless-shell is missing it is installed automatically on
		first use (one-time cost, then cached in ~/.cache/ms-playwright/).
		"""
		from playwright.sync_api import sync_playwright

		self._playwright = sync_playwright().start()
		try:
			self._browser = self._playwright.chromium.launch(
				channel="chrome-headless-shell",
				executable_path=executable_path,
				args=CHROMIUM_LAUNCH_ARGS,
				headless=True,
			)
		except Exception as e:
			if "Executable doesn't exist" in str(e) or "playwright install" in str(e).lower():
				# chrome-headless-shell not yet installed — auto-install on first use.
				# Cached in ~/.cache/ms-playwright/ so this only runs once per machine.
				# In Docker, run bench setup-chrome at build time to avoid this cost.
				frappe.log("chrome-headless-shell not found — auto-installing via playwright")
				self._auto_install_chromium()
				self._browser = self._playwright.chromium.launch(
					channel="chrome-headless-shell",
					executable_path=executable_path,
					args=CHROMIUM_LAUNCH_ARGS,
					headless=True,
				)
			else:
				self._playwright.stop()
				self._playwright = None
				frappe.log_error(f"Error launching Chromium: {e}")
				frappe.throw(_("Could not start Chromium. Check error logs for details."))

	def _auto_install_chromium(self):
		"""Install chrome-headless-shell using the current venv's playwright."""
		import subprocess
		import sys

		# Use sys.executable so we always call the playwright from the active venv,
		# not whatever playwright happens to be on $PATH.
		try:
			subprocess.run(
				[sys.executable, "-m", "playwright", "install", "chrome-headless-shell", "--with-deps"],
				check=True,
				text=True,
			)
		except subprocess.CalledProcessError as e:
			self._playwright.stop()
			self._playwright = None
			frappe.throw(
				_(f"Failed to auto-install chrome-headless-shell: {e}. Run 'bench setup-chrome' manually.")
			)

	def _connect_playwright_cdp(self, ws_url):
		"""Connect to an externally managed Chromium instance over CDP."""
		from playwright.sync_api import sync_playwright

		self._playwright = sync_playwright().start()
		self._browser = self._playwright.chromium.connect_over_cdp(ws_url)

	def new_context(self):
		"""Create a new isolated browser context (like a fresh incognito window).

		context.close() automatically closes all pages inside it — no need to
		track and close pages individually.
		"""
		return self._browser.new_context()

	def _close_browser(self):
		"""Close the Playwright browser and stop the Playwright runtime."""
		if self._browsers:
			frappe.log("Cannot close Chromium as there are active browser instances.")
			return
		try:
			if self._browser:
				self._browser.close()
		except Exception:
			frappe.log_error("Error closing Playwright browser")
		try:
			if self._playwright:
				self._playwright.stop()
		except Exception:
			frappe.log_error("Error stopping Playwright runtime")
		ChromiumManager._instance = None
		self._browser = None
		self._playwright = None
		frappe.log("Headless Chromium closed successfully.")

	def detach_debug_browser(self):
		"""Keep the debug browser open for inspection; reset the singleton.

		The next PDF request will start with a fresh browser instance.
		"""
		# Don't close — the developer is inspecting the browser window.
		ChromiumManager._instance = None
		self._initialized = False
		self._browser = None
		self._playwright = None
