import hashlib
from datetime import datetime, timezone

import frappe


def anonymize_user(user):
	"""
	Create consistent anonymous ID from user email.
	Same email always produces same anonymous ID.
	"""
	if not user or user in frappe.STANDARD_USERS:
		return user

	# Use site-specific salt for additional security
	site_salt = frappe.local.site or "default"

	# Create deterministic hash
	hash_input = f"{user}:{site_salt}".encode()
	user_hash = hashlib.sha256(hash_input).hexdigest()

	# Return first 12 characters for readability
	return f"anon_{user_hash[:12]}"


def parse_interval(interval):
	"""
	Parse interval string or integer into seconds.

	Args:
	    interval: Can be:
	        - Integer: seconds (e.g., 3600)
	        - String: number + unit (e.g., "1h", "30m", "7d")

	Returns:
	    int: Total seconds

	Examples:
	    parse_interval(3600) -> 3600
	    parse_interval("1h") -> 3600
	    parse_interval("30m") -> 1800
	    parse_interval("7d") -> 604800
	"""
	if interval is None:
		return None

	# If already an integer, return as-is (assuming seconds)
	if isinstance(interval, int):
		return interval

	# Parse string format
	interval = str(interval).strip().lower()

	# Extract number and unit
	if interval[-1].isdigit():
		# No unit specified, assume seconds
		return int(interval)

	unit = interval[-1]
	try:
		number = int(interval[:-1])
	except ValueError:
		raise ValueError(f"Invalid interval format: {interval}")

	# Convert to seconds
	multipliers = {
		"s": 1,  # seconds
		"m": 60,  # minutes
		"h": 3600,  # hours
		"d": 86400,  # days
		"w": 604800,  # weeks
		"y": 31536000,  # years
	}

	if unit not in multipliers:
		raise ValueError(f"Invalid time unit '{unit}'. Use: s, m, h, d, w, y")

	return number * multipliers[unit]


def get_frappe_version() -> str:
	return getattr(frappe, "__version__", "unknown")


def utc_iso() -> str:
	return datetime.now(timezone.utc).isoformat()


def get_app_version(app_name: str) -> str:
	try:
		return frappe.get_attr(app_name + ".__version__")
	except Exception:
		return "0.0.1"


def ensure_http(url: str) -> str:
	return url if url.startswith(("http://", "https://")) else "https://" + url
