"""Locate, download and set up the bundled headless-Chromium binary.

Moved out of ``frappe.utils.print_utils`` since these helpers are not specific to
PDF/print — they provision the Chromium executable used by the whole
``frappe.utils.chromium`` stack (PDF generation, previews, scraping).
"""

import os

import click

import frappe

EXECUTABLE_PATHS = {
	"linux": ["chrome-linux", "headless_shell"],
	"darwin": ["chrome-mac", "headless_shell"],
	"windows": ["chrome-win", "headless_shell.exe"],
}


def setup_chromium():
	"""Setup Chromium at the bench level."""
	# Load Chromium version from common_site_config.json or use default

	try:
		executable = find_or_download_chromium_executable()
		click.echo(f"Chromium is already set up at {executable}")
	except Exception as e:
		click.echo(f"Failed to setup Chromium: {e}")
		raise RuntimeError(f"Failed to setup Chromium: {e}")
	return executable


def find_or_download_chromium_executable():
	"""Finds the Chromium executable or downloads if not found."""
	import platform
	import shutil
	from pathlib import Path

	if chromium_path := shutil.which(frappe.get_common_site_config().get("chromium_path", "")):
		return chromium_path

	bench_path = frappe.utils.get_bench_path()
	"""Determine the path to the Chromium executable."""
	chromium_dir = os.path.join(bench_path, "chromium")

	platform_name = platform.system().lower()

	executable_name = EXECUTABLE_PATHS.get(platform_name)
	if not executable_name:
		raise RuntimeError(f"Chromium is not supported on this platform: {platform_name}")

	# Construct the full path to the executable
	exec_path = Path(chromium_dir).joinpath(*executable_name)
	if not exec_path.exists():
		click.echo("Chromium is not available. downloading...")
		download_chromium()
	else:
		make_chromium_executable(str(exec_path))

	if not exec_path.exists():
		click.echo("Error while downloading chrome")

	return str(exec_path)


def download_chromium():
	import platform
	import shutil
	import zipfile

	import requests

	bench_path = frappe.utils.get_bench_path()
	"""Download and extract Chromium for the specific version at the bench level."""
	chromium_dir = os.path.join(bench_path, "chromium")

	# Remove old Chromium directory if it exists
	if os.path.exists(chromium_dir):
		click.echo("Removing old Chromium directory...")
		shutil.rmtree(chromium_dir, ignore_errors=True)

	os.makedirs(chromium_dir, exist_ok=True)

	download_url = get_chromium_download_url()
	file_name = os.path.basename(download_url)
	zip_path = os.path.join(chromium_dir, file_name)

	try:
		click.echo(f"Downloading Chromium from {download_url}...")
		# playwright's requires a user agent
		headers = {"User-Agent": "Wget/1.21.1"}
		with requests.get(download_url, stream=True, timeout=(10, 60), headers=headers) as r:
			r.raise_for_status()  # Raise an error for bad status codes
			total_size = int(r.headers.get("content-length", 0))  # Get total file size
			with (
				click.progressbar(length=total_size, label="Downloading Chromium") as bar,
				# zip_path is bench-internal (<bench>/chromium/<basename of download url>), not user input.
				# nosemgrep: frappe-semgrep-rules.rules.security.frappe-security-file-traversal
				open(zip_path, "wb") as f,
			):
				for chunk in r.iter_content(chunk_size=65536):
					f.write(chunk)
					bar.update(len(chunk))

		click.echo("Extracting Chromium...")
		with zipfile.ZipFile(zip_path, "r") as zip_ref:
			zip_ref.extractall(chromium_dir)

		if os.path.exists(zip_path):
			os.remove(zip_path)

		# There should be only one directory
		# Ensure the correct directory is renamed
		extracted = os.listdir(chromium_dir)[0]
		executable_path = EXECUTABLE_PATHS[platform.system().lower()]
		chrome_folder_name = executable_path[0]

		if extracted != chrome_folder_name:
			extracted_dir = os.path.join(chromium_dir, extracted)
			renamed_dir = os.path.join(chromium_dir, chrome_folder_name)
			if os.path.exists(extracted_dir):
				click.echo(f"Renaming {extracted_dir} to {renamed_dir}")
				os.rename(extracted_dir, renamed_dir)
			else:
				raise RuntimeError(f"Failed to rename extracted directory. Expected {chrome_folder_name}.")
			if os.path.exists(renamed_dir):
				executable_shell = os.path.join(renamed_dir, "chrome-headless-shell")
				if os.path.exists(executable_shell):
					os.rename(executable_shell, os.path.join(renamed_dir, "headless_shell"))
				else:
					raise RuntimeError("Failed to rename executable. Expected chrome-headless-shell.")
			# Make the `headless_shell` executable
			exec_path = os.path.join(renamed_dir, executable_path[1])
			make_chromium_executable(exec_path)

		click.echo(f"Chromium is ready to use at: {chromium_dir}")
	except requests.Timeout:
		click.echo("Download timed out. Check your internet connection.")
		raise RuntimeError("Download timed out.")
	except requests.ConnectionError:
		click.echo("Failed to connect to Chromium download server.")
		raise RuntimeError("Connection error.")
	except requests.RequestException as e:
		click.echo(f"Failed to download Chromium: {e}")
		raise RuntimeError(f"Failed to download Chromium: {e}")
	except zipfile.BadZipFile as e:
		click.echo(f"Failed to extract Chromium: {e}")
		raise RuntimeError(f"Failed to extract Chromium: {e}")


def get_chromium_download_url():
	# Avoid this unless it is going to run on a single type of platform and you have the correct binary hosted.
	common_config = frappe.get_common_site_config()

	chrome_download_url = common_config.get("chromium_download_url", None)

	if chrome_download_url:
		return chrome_download_url

	"""
	We are going to use chrome-for-testing builds but unfortunately it doesn't have linux arm64 https://github.com/GoogleChromeLabs/chrome-for-testing/issues/1
	so we will use playwright's fallback builds for linux arm64
	TODO: we will also use the fallback builds for windows arm
	https://community.arm.com/arm-community-blogs/b/tools-software-ides-blog/posts/native-chromium-builds-windows-on-arm
	"""
	"""
	To find the CHROME_VERSION AND CHROME_FALLBACK_VERSION, follow these steps:
	1. Visit the GitHub Actions page for Playwright: https://github.com/microsoft/playwright/actions/workflows/roll_browser_into_playwright.yml
	2. Open the latest job run.
	3. Navigate to the "Roll to New Browser Version" step.
	4. In the logs, look for a line similar to:
		Downloading Chromium 133.0.6943.16 (playwright build v1155)
		Here, the first number (e.g., 133.0.6943.16) is the CHROME_VERSION, and the second number (e.g., 1155) is the CHROME_FALLBACK_VERSION.
	"""
	# Using Google's chrome-for-testing-public builds for most platforms. (close to end user experience)
	# For Linux ARM64, we use Playwright's Chromium builds due to the lack of official support.

	download_path = {
		"linux64": "%s/linux64/chrome-headless-shell-linux64.zip",
		"mac-arm64": "%s/mac-arm64/chrome-headless-shell-mac-arm64.zip",
		"mac-x64": "%s/mac-x64/chrome-headless-shell-mac-x64.zip",
		"win32": "%s/win32/chrome-headless-shell-win32.zip",
		"win64": "%s/win64/chrome-headless-shell-win64.zip",
	}
	linux_arm_download_path = {
		"ubuntu20.04-arm64": "%s/chromium-headless-shell-linux-arm64.zip",
		"ubuntu22.04-arm64": "%s/chromium-headless-shell-linux-arm64.zip",
		"ubuntu24.04-arm64": "%s/chromium-headless-shell-linux-arm64.zip",
		"debian11-arm64": "%s/chromium-headless-shell-linux-arm64.zip",
		"debian12-arm64": "%s/chromium-headless-shell-linux-arm64.zip",
	}

	platform_key = calculate_platform()

	version = "133.0.6943.35"
	playwright_build_version = "1157"

	base_url = "https://storage.googleapis.com/chrome-for-testing-public/"
	playwright_base_url = "https://cdn.playwright.dev/dbazure/download/playwright/builds/chromium/"

	# Overwrite with values from common_site_config.json ( escape hatch )
	version = common_config.get("chromium_version", version)
	playwright_build_version = common_config.get("playwright_chromium_version", playwright_build_version)
	# make sure that you have all required flavours at correct urls
	base_url = common_config.get("chromium_download_base_url", base_url)
	playwright_base_url = common_config.get("playwright_chromium_download_base_url", playwright_base_url)

	if platform_key in download_path:
		relative_path = download_path[platform_key]
	elif platform_key in linux_arm_download_path:
		version = playwright_build_version
		base_url = playwright_base_url
		relative_path = linux_arm_download_path[platform_key]
	else:
		frappe.throw(
			f"No download path configured or Chromium download not available for platform: {platform_key}"
		)

	return f"{base_url}{relative_path % version}"


def make_chromium_executable(executable):
	"""Make the Chromium executable."""
	if os.path.exists(executable):
		# check if the file is executable
		if os.access(executable, os.X_OK):
			click.echo(f"Chromium executable is already executable: {executable}")
			return
		click.echo(f"Making Chromium executable: {executable}")
		os.chmod(executable, 0o755)  # Set executable permissions
		click.echo(f"Chromium executable permissions set: {executable}")
	else:
		raise RuntimeError(f"Chromium executable not found: {executable}.")


def calculate_platform():
	"""
	Determines the host platform and returns it as a string.
	Includes logic for Linux ARM, Linux x64, macOS (Intel and ARM), and Windows (32-bit and 64-bit).

	Returns:
	        str: The detected platform string (e.g., 'linux64', 'mac-arm64', etc.).
	"""
	import platform

	system = platform.system().lower()
	arch = platform.machine().lower()

	# Handle Linux ARM-specific logic
	if system == "linux" and arch == "aarch64":
		distro_info = get_linux_distribution_info()
		distro_id = distro_info.get("id", "")
		version = distro_info.get("version", "")
		major_version = int(version.split(".")[0]) if version else 0

		if distro_id == "ubuntu":
			if major_version < 20:
				return "ubuntu18.04-arm64"
			if major_version < 22:
				return "ubuntu20.04-arm64"
			if major_version < 24:
				return "ubuntu22.04-arm64"
			if major_version < 26:
				return "ubuntu24.04-arm64"
			return "<unknown>"

		if distro_id in ["debian", "raspbian"]:
			if major_version < 11:
				return "debian10-arm64"
			if major_version < 12:
				return "debian11-arm64"
			return "debian12-arm64"
		return "<unknown>"

	# Handle other platforms
	elif system == "linux" and arch == "x86_64":
		return "linux64"
	elif system == "darwin" and arch == "arm64":
		return "mac-arm64"
	elif system == "darwin" and arch == "x86_64":
		return "mac-x64"
	elif system == "windows" and arch == "x86":
		return "win32"
	elif system == "windows" and arch == "x86_64":
		return "win64"

	return "<unknown>"


def get_linux_distribution_info():
	# not tested
	"""Retrieve Linux distribution information using the `distro` library."""
	try:
		import distro
	except ImportError:
		return {"id": "", "version": ""}

	return {"id": distro.id().lower(), "version": distro.version()}
