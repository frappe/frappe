"""flow — a standalone client-server agent core (the brain).

Frappe/Flow is one client among many; the CLI is another. The daemon runs the loop,
owns a durable event log, and dispatches tools either in-process or back to a client.
"""

from importlib.metadata import PackageNotFoundError, version

try:
	__version__ = version("frappe-flow")
except PackageNotFoundError:
	__version__ = "0.0.0+unknown"
