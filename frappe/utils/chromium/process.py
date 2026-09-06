import os
import platform
import subprocess
import threading
import time
from pathlib import Path

import psutil
import requests

import frappe
from frappe import _
from frappe.utils.chromium.download import find_or_download_chromium_executable
from frappe.utils.data import cint


class ChromiumManager:
	_instance = None
	# Serializes obtain/register/teardown under threaded serving: without it,
	# one request's per-request teardown can terminate the chromium another
	# request obtained but hasn't registered a browser on yet.
	_lock = threading.RLock()

	@classmethod
	def acquire(cls):
		"""Return (manager, token) with the token already registered, atomically.

		Holding a registered token keeps _close_browser from tearing chromium
		down while this request is using it."""
		with cls._lock:
			manager = cls()
			token = frappe.utils.random_string(10)
			manager.add_browser(token)
			return manager, token

	def release(self, token):
		"""Deregister the token and tear chromium down if nobody else holds one."""
		with ChromiumManager._lock:
			self.remove_browser(token)
			self._close_browser()

	def add_browser(self, browser):
		self._browsers.append(browser)

	def remove_browser(self, browser):
		if browser in self._browsers:
			self._browsers.remove(browser)

	def __new__(cls):
		# Rebuild singleton when chromium subprocess is missing or has exited.
		# subprocess.Popen stays truthy after the underlying process dies, so
		# `not cls._instance._chromium_process` never trips — use poll() instead.
		if (
			cls._instance is None
			or cls._instance._chromium_process is None
			or cls._instance._chromium_process.poll() is not None
		):
			cls._instance = super().__new__(cls)
		return cls._instance

	def __init__(self):
		"""Initialize only once."""
		if hasattr(self, "_initialized"):  # Prevent multiple initializations
			return
		self._initialized = True  # Mark as initialized

		self._browsers = []
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
			frappe.logger("pdf").warning("Using external chromium websocket url. Make sure it is accessible.")
			self._devtools_url = self.CHROMIUM_WEBSOCKET_URL
			return

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
		# Allow a single PDF request to opt into interactive Chromium debugging in developer mode only.
		self.debug_mode = frappe.conf.developer_mode and bool(frappe.form_dict.get("pdf_debug"))

		self._chromium_path = find_or_download_chromium_executable()
		if self._verify_chromium_installation():
			if not self._devtools_url:
				self.start_chromium_process(debug=self.debug_mode)

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
		self._reap_orphaned_chromium()
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
		# stdout is never read, and an unread PIPE fills the OS buffer and blocks
		# chromium on write; stderr is drained after the DevTools URL is captured.
		if platform.system().lower() == "windows":
			# hide cmd window
			startupinfo = subprocess.STARTUPINFO()
			startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
			startupinfo.wShowWindow = subprocess.SW_HIDE
			self._chromium_process = subprocess.Popen(
				command_args,
				stdout=subprocess.DEVNULL,
				stderr=subprocess.PIPE,
				errors="replace",
				startupinfo=startupinfo,
				text=True,
			)
		else:
			self._chromium_process = subprocess.Popen(
				command_args, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, errors="replace"
			)
		return self._chromium_process

	def _reap_orphaned_chromium(self):
		"""Kill chromium processes leaked by dead workers.

		Cleanup normally happens in the caller's `finally`, but a worker killed
		mid-render (dev auto-reload, SIGKILL, crash) never runs it and its
		chromium survives forever. Such processes are reparented to init/launchd
		(ppid 1), so kill anything running this bench's chromium binary whose
		parent is gone before starting a new one.
		"""
		chromium_path = os.path.realpath(self._chromium_path)
		for proc in psutil.process_iter(["exe", "ppid", "cmdline"]):
			try:
				if (
					proc.info["ppid"] == 1
					and proc.info["exe"] == chromium_path
					and "--headless" in (proc.info["cmdline"] or [])
				):
					for child in proc.children(recursive=True):
						child.kill()
					proc.kill()
			except (psutil.NoSuchProcess, psutil.AccessDenied):
				continue

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
		output = []

		while time.time() - start_time < self.START_TIMEOUT:
			# Read a single line from stderr and check if it contains the DevTools URL.
			# Not using select() because it is not supported on Windows for non-socket file descriptors.
			line = stderr.readline()
			if not line:
				break
			output.append(line)
			# not sure if "DevTools listening on" is consistent in all chromium versions.
			if "DevTools listening on" in line:
				url_start = line.find("ws://")
				if url_start != -1:
					self._devtools_url = line[url_start:].strip()
					break

		if self._devtools_url:
			self._drain_stderr(stderr)
			return

		self._raise_start_failure(output)

	def _drain_stderr(self, stderr):
		"""Keep reading chromium's stderr for the rest of its lifetime.

		Nothing consumes it after the DevTools URL line, and a chatty chromium
		(GPU fallback spam, broken resources) blocks on write once the ~64KB
		pipe buffer fills, hanging the render."""
		threading.Thread(target=stderr.read, daemon=True).start()

	def _raise_start_failure(self, output):
		"""Report why Chromium never handed us a DevTools URL, quoting its own stderr.

		stderr reaching EOF races the process becoming reapable, so give a dead Chromium
		a moment to be collected rather than misreporting it as a live one.
		"""
		try:
			exit_code = self._chromium_process.wait(timeout=1)
		except subprocess.TimeoutExpired:
			exit_code = None
		chromium_output = "".join(output).strip() or "<no output on stderr>"

		if exit_code is None:
			self._chromium_process.terminate()
			raise TimeoutError(
				f"Chromium did not report a DevTools URL within {self.START_TIMEOUT}s. "
				f"Raise `chromium_start_timeout` in site config if this machine is slow.\n"
				f"Chromium output:\n{chromium_output}"
			)

		raise RuntimeError(
			f"Chromium exited with code {exit_code} before reporting a DevTools URL.\n"
			f"Chromium output:\n{chromium_output}"
		)

	def _close_browser(self):
		"""
		Close the headless Chromium browser.
		"""
		with ChromiumManager._lock:
			self._close_browser_locked()

	def _close_browser_locked(self):
		if self._browsers:
			frappe.log("Cannot close Chromium as there are active browser instances.")
			return
		if getattr(self, "USE_PERSISTENT_CHROMIUM", False):
			return
		if self._chromium_process:
			self._chromium_process.terminate()
			try:
				self._chromium_process.wait(timeout=5)
			except subprocess.TimeoutExpired:
				self._chromium_process.kill()
				self._chromium_process.wait()
		ChromiumManager._instance = None
		self._chromium_process = None
		self._devtools_url = None
		frappe.log("Headless Chromium closed successfully.")

	def detach_debug_browser(self):
		"""
		Detach the generator from an interactive debug Chromium process.

		This keeps the debug browser window available for inspection, while ensuring
		the next PDF request starts with a fresh generator/process instead of reusing
		the old debug session.
		"""
		ChromiumManager._instance = None
		self._initialized = False
		self._chromium_process = None
		self._devtools_url = None

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
