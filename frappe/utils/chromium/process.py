from typing import ClassVar

import frappe
from frappe import _

# Chrome flags used for both headless (prod) and headed (debug) launches.
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
	# Excluded in debug (headed) mode — prevents the browser window from opening.
	"--no-startup-window",
]

# Flags that only apply in headless mode; removed when launching headed for debug.
_HEADLESS_ONLY_ARGS = {"--no-startup-window"}


def _is_debug_mode():
	return frappe.conf.developer_mode and bool(frappe.form_dict.get("pdf_debug"))


class ChromiumManager:
	_instance = None
	_browsers: ClassVar[list] = []

	def add_browser(self, browser):
		self._browsers.append(browser)

	def remove_browser(self, browser):
		if browser in self._browsers:
			self._browsers.remove(browser)

	def __new__(cls):
		is_debug = _is_debug_mode()

		if cls._instance is None:
			cls._instance = super().__new__(cls)
		elif is_debug:
			# Debug requests always get a fresh headed browser.
			# Close the existing headless singleton first to avoid an orphaned process.
			old = cls._instance
			try:
				if getattr(old, "_browser", None):
					old._browser.close()
			except Exception:
				pass
			try:
				if getattr(old, "_playwright", None):
					old._playwright.stop()
			except Exception:
				pass
			cls._instance = super().__new__(cls)
		elif getattr(cls._instance, "_browser", None) is not None:
			# Rebuild singleton when the browser connection drops.
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
		self.debug_mode = _is_debug_mode()

		# Connect to an external Chromium over CDP (separate docker/server).
		ws_url = site_config.get("chromium_websocket_url", "")
		if ws_url:
			frappe.warn("Using external chromium websocket url. Make sure it is accessible.")
			self._connect_playwright_cdp(ws_url)
			return

		# Optional: point at a custom binary via chromium_path in common_site_config.json.
		executable_path = None
		if custom_path := site_config.get("chromium_path", ""):
			import shutil

			executable_path = shutil.which(custom_path) or custom_path

		self._launch_playwright_browser(executable_path=executable_path)

	def _launch_playwright_browser(self, executable_path=None):
		"""Launch Chromium via Playwright.

		Two modes:
		- Prod (headless=True): chrome-headless-shell (~136 MB, headless-only, Docker-friendly).
		- Debug (headless=False): full Playwright Chromium (~280 MB) so the browser window is
		  visible and the developer can inspect the rendered content.

		In debug mode, full Chromium is auto-installed on first use. In prod, chrome-headless-shell
		is installed by `bench setup-chrome` (or auto-installed on first use if that was skipped).
		"""
		from playwright.sync_api import sync_playwright

		if self.debug_mode:
			# Full Playwright Chromium (channel="chromium"): supports headless=False for
			# interactive inspection. Install with: playwright install chromium
			channel = None if executable_path else "chromium"
			headless = False
			# --no-startup-window suppresses the OS window, defeating the purpose of headed mode.
			args = [a for a in CHROMIUM_LAUNCH_ARGS if a not in _HEADLESS_ONLY_ARGS]
		else:
			# No channel = Playwright's chromium-headless-shell (~94 MB, headless-only).
			# In Playwright ≥1.61 this is the default when no channel is specified.
			# Install with: playwright install chromium-headless-shell
			# When a custom executable_path is set, no channel is needed either.
			channel = None
			headless = True
			args = CHROMIUM_LAUNCH_ARGS

		self._playwright = sync_playwright().start()
		try:
			self._browser = self._playwright.chromium.launch(
				channel=channel,
				executable_path=executable_path,
				args=args,
				headless=headless,
			)
		except Exception as e:
			if "Executable doesn't exist" in str(e) or "playwright install" in str(e).lower():
				binary = "chromium" if self.debug_mode else "chromium-headless-shell"
				frappe.log(f"{binary} not found — auto-installing via playwright")
				self._auto_install_chromium()
				self._browser = self._playwright.chromium.launch(
					channel=channel,
					executable_path=executable_path,
					args=args,
					headless=headless,
				)
			else:
				self._playwright.stop()
				self._playwright = None
				frappe.log_error(f"Error launching Chromium: {e}")
				frappe.throw(_("Could not start Chromium. Check error logs for details."))

	def _auto_install_chromium(self):
		"""Install the appropriate Chromium binary using the current venv's playwright.

		- Debug mode: installs full Playwright Chromium (supports headless=False).
		- Prod mode: installs chrome-headless-shell (~136 MB, headless-only).

		Uses sys.executable to guarantee the venv's playwright is called, not whatever
		is on $PATH.
		"""
		import subprocess
		import sys

		# Install names differ from channel names:
		#   debug  → "chromium"             (full build, supports headless=False)
		#   prod   → "chromium-headless-shell" (lightweight shell, headless-only)
		package = "chromium" if self.debug_mode else "chromium-headless-shell"
		try:
			subprocess.run(
				[sys.executable, "-m", "playwright", "install", package, "--with-deps"],
				check=True,
				text=True,
			)
		except subprocess.CalledProcessError as e:
			self._playwright.stop()
			self._playwright = None
			frappe.throw(_(f"Failed to auto-install {package}: {e}. Run 'bench setup-chrome' manually."))

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
		"""Keep the debug browser window open for the developer to inspect.

		Resets the singleton so the next PDF request starts a fresh headless browser
		instead of reusing the headed debug one.
		"""
		ChromiumManager._instance = None
		self._initialized = False
		self._browser = None
		self._playwright = None
