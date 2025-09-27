import os
import platform
import subprocess
import time
from pathlib import Path
from typing import ClassVar

import requests

import frappe
from frappe import _

# TODO: close browser when worker is killed.


class ChromePDFGenerator:
	EXECUTABLE_PATHS: ClassVar[dict[str, list[str]]] = {
		"linux": ["chrome-linux", "headless_shell"],
		"darwin": ["chrome-mac", "headless_shell"],
		"windows": ["chrome-win", "headless_shell.exe"],
	}

	_instance = None

	_browsers: ClassVar[list] = []

	def add_browser(self, browser):
		self._browsers.append(browser)

	def remove_browser(self, browser):
		self._browsers.remove(browser)

	def __new__(cls):
		# if instance or _chromium_process is not available create object else return current instance stored in cls._instance
		if cls._instance is None or not cls._instance._chromium_process:
			cls._instance = super().__new__(cls)
		return cls._instance

	def __init__(self):
		"""Initialize only once."""
		if hasattr(self, "_initialized"):  # Prevent multiple initializations
			return
		self._initialized = True  # Mark as initialized

		self._chromium_process = None
		self._chromium_path = None
		self._devtools_url = None
		self._initialize_chromium()

	def _initialize_chromium(self):
		# ideally browser is initailized from before request hook.
		# if _chromium_process is not available then initialize it.
		if self._chromium_process:
			return
		# get site config and load chromium settings.
		site_config = frappe.get_common_site_config()

		# only when we want to chromium on separate docker / server ( not implemented/tested yet )
		self.CHROMIUM_WEBSOCKET_URL = site_config.get("chromium_websocket_url", "")
		if self.CHROMIUM_WEBSOCKET_URL:
			frappe.warn("Using external chromium websocket url. Make sure it is accessible.")
			self._devtools_url = self.CHROMIUM_WEBSOCKET_URL
			return

		# only when we want to use chromium from a specific path ( incase we don't have chromium in bench folder )
		self.CHROMIUM_BINARY_PATH = site_config.get("chromium_binary_path", "")
		"""
		Number of allowed open websocket connections to chromium.
		This number will basically define how many concurrent requests can be handled by one chromium instance.
		#TODO: Implement/Modify logic to handle multiple chromium instance in one class / per worker. currently we are starting one chromium.
		"""
		self.CHROME_OPEN_CONNECTIONS = site_config.get("chromium_max_concurrent", 1)
		# if we want to use persistent ( long running ) chromium for all sites.
		# current approch starts chrome per worker process.
		# TODO: Better Implement logic to support for persistent chrome proccess.
		self.USE_PERSISTENT_CHROMIUM = site_config.get("use_persistent_chromium", False)
		#  time to wait for chromium to start and provide dev tools url used in _set_devtools_url.
		self.START_TIMEOUT = site_config.get("chromium_start_timeout", 3)

		self._chromium_path = (
			self._find_chromium_executable() if not self.CHROMIUM_BINARY_PATH else self.CHROMIUM_BINARY_PATH
		)
		if self._verify_chromium_installation():
			if not self._devtools_url:
				self.start_chromium_process()

	def _find_chromium_executable(self):
		"""Finds the Chromium executable or raises an error if not found."""
		bench_path = frappe.utils.get_bench_path()
		"""Determine the path to the Chromium executable. chromium is downloaded by download_chromium in print_designer/install.py"""
		chromium_dir = os.path.join(bench_path, "chromium")

		if not os.path.exists(chromium_dir):
			frappe.throw(_("Chromium is not downloaded. Please run the setup first."))

		platform_name = platform.system().lower()

		if platform_name not in ["linux", "darwin", "windows"]:
			frappe.throw(f"Unsupported platform: {platform_name}")

		executable_name = self.EXECUTABLE_PATHS.get(platform_name)

		# Construct the full path to the executable
		exec_path = Path(chromium_dir).joinpath(*executable_name)
		if not exec_path.exists():
			frappe.throw(
				f"Chromium executable not found: {exec_path}. please run bench setup-new-pdf-backend"
			)

		return str(exec_path)

	def _verify_chromium_installation(self):
		"""Ensures Chromium is available and executable, raising clearer errors if not."""
		if not os.path.exists(self._chromium_path):
			frappe.throw(
				f"Chromium not available at the specified path. Please check the path: {self._chromium_path}"
			)
		if not os.access(self._chromium_path, os.X_OK):
			frappe.throw(f"Chromium not executable at {self._chromium_path}")
		return True

	def start_chromium_process(self, debug=False):
		"""
		Launches Chromium in headless mode with robust logging and error handling.
		chrome switches
		https://peter.sh/experiments/chromium-command-line-switches/

		NOTE: dbus issue in docker
		  https://source.chromium.org/chromium/chromium/src/+/main:content/app/content_main.cc;l=229-241?q=DBUS_SESSION_BUS_ADDRESS&ss=chromium
		"""
		try:
			if debug:
				command_args = [
					"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",  # path to locally installed chrome browser for debugging.
					"--remote-debugging-port=0",
					"--user-data-dir=/tmp/chromium-{}-user-data".format(
						frappe.local.site + frappe.utils.random_string(10)
					),
					"--disable-gpu",
					"--no-sandbox",
					"--no-first-run",
					"",
				]
			else:
				command_args = [
					self._chromium_path,
					# 0 will automatically select a random open port from the ephemeral port range.
					"--remote-debugging-port=0",
					"--disable-gpu",  # GPU is not available in production environment.
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
					"--headless",
					"--hide-scrollbars",
					"--mute-audio",
					"--blink-settings=primaryHoverType=2,availableHoverTypes=2,primaryPointerType=4,availablePointerTypes=4",
					"--no-sandbox",
					"--no-startup-window",
					# related to HeadlessExperimental flag enable when Implement Deterministic rendering. check page class for more info.
					# "--enable-surface-synchronization",
					# "--run-all-compositor-stages-before-draw",
					# "--disable-threaded-animation",
					# "--disable-threaded-scrolling",
					# "--disable-checker-imaging",
				]

			self._start_chromium_process(command_args)

		except Exception as e:
			frappe.log_error(f"Error starting Chromium: {e}")
			frappe.throw(_("Could not start Chromium. Check logs for details."))

	# Apply the decorator to monitor Chromium subprocess usage for development / debugging purposes.
	# it will print and write usage data to a file ( defaults to chrome_process_usage.json).
	# from print_designer.pdf_generator.monitor_subprocess import monitor_subprocess_usage
	# @monitor_subprocess_usage(interval=0.1)
	def _start_chromium_process(self, command_args):
		if platform.system().lower() == "windows":
			# hide cmd window
			startupinfo = subprocess.STARTUPINFO()
			startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
			startupinfo.wShowWindow = subprocess.SW_HIDE
			self._chromium_process = subprocess.Popen(
				command_args,
				stdout=subprocess.PIPE,
				stderr=subprocess.PIPE,
				startupinfo=startupinfo,
				text=True,
			)
		else:
			self._chromium_process = subprocess.Popen(
				command_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
			)
		return self._chromium_process

	def _set_devtools_url(self):
		"""
		Monitor Chromium's stderr for the DevTools WebSocket URL
		----------------
		other approch: if we choose port using find_available_port we can avoid this entirely and fetch_devtools_url() method.

		NOTE:	1) in current approch output to stderr is pretty consistent.
		                2) other approch may seem reliable but it is slow compared to this in testing.

		TODO:
		final approch can be decided later after testing in production.
		"""
		stderr = self._chromium_process.stderr
		start_time = time.time()

		while time.time() - start_time < self.START_TIMEOUT:
			# Read a single line from stderr and check if it contains the DevTools URL.
			# Not using select() because it is not supported on Windows for non-socket file descriptors.
			line = stderr.readline()
			# not sure if "DevTools listening on" is consistent in all chromium versions.
			if "DevTools listening on" in line:
				url_start = line.find("ws://")
				if url_start != -1:
					self._devtools_url = line[url_start:].strip()
					break

		if not self._devtools_url:
			self._chromium_process.terminate()
			raise TimeoutError("Chromium took too long to start.")

	def _close_browser(self):
		"""
		Close the headless Chromium browser.
		"""
		if self._browsers:
			frappe.log("Cannot close Chromium as there are active browser instances.")
			return
		if self._chromium_process:
			self._chromium_process.terminate()
		ChromePDFGenerator._instance = None
		self._chromium_process = None
		self._devtools_url = None
		frappe.log("Headless Chromium closed successfully.")

	# not used anywhere in the code. read _set_devtools_url for more info.  useful in case we want to take different approch to fetch devtools url.
	def fetch_devtools_url(self, port):
		if not port:
			return None
		url = f"http://127.0.0.1:{port}/json/version"
		try:
			response = requests.get(url)
			response.raise_for_status()  # Raise an exception for HTTP errors
			response_data = response.json()
			return response_data["webSocketDebuggerUrl"].strip()
		except requests.ConnectionError:
			frappe.log_error(
				f"Failed to connect to the Chrome DevTools Protocol. Is Chrome running with --remote-debugging-port={port}"
			)
		except requests.RequestException as e:
			frappe.log_error(f"An error occurred: {e}")
		return None
