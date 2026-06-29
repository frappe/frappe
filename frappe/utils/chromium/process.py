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

		# Optional: override the binary path (e.g. custom build or system install).
		# If not set, Playwright uses its own bundled Chromium installed via
		# `bench setup-chrome` (which runs `playwright install chromium --with-deps`).
		executable_path = None
		if custom_path := site_config.get("chromium_path", ""):
			import shutil

			executable_path = shutil.which(custom_path) or custom_path

		self._launch_playwright_browser(executable_path=executable_path)

	def _launch_playwright_browser(self, executable_path=None):
		"""Launch Chromium via Playwright.

		Playwright manages the process lifecycle — no subprocess management,
		no stderr polling, no manual port selection needed.
		"""
		from playwright.sync_api import sync_playwright

		self._playwright = sync_playwright().start()
		try:
			self._browser = self._playwright.chromium.launch(
				executable_path=executable_path,
				args=CHROMIUM_LAUNCH_ARGS,
				headless=not self.debug_mode,
			)
		except Exception as e:
			self._playwright.stop()
			self._playwright = None
			frappe.log_error(f"Error launching Chromium: {e}")
			frappe.throw(
				_(
					"Could not start Chromium. Run 'bench setup-chrome' to install it, then retry."
					" Check error logs for details."
				)
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
