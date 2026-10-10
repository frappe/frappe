import os

from frappe.tests.microbenchmarks.utils import NanoBenchmark
from frappe.utils import get_bench_path

# Real paths: realpath() returns early for one that doesn't exist, which would understate the
# cost now that every access is resolved.
BENCH = os.path.realpath(get_bench_path())
HOOKS_PY = os.path.join(BENCH, "apps", "frappe", "frappe", "hooks.py")
SITE_FILE = os.path.join(BENCH, "sites", "apps.txt")
TRAVERSAL = os.path.join(BENCH, "sites", "x", "..", "..", "..", "..", "etc", "passwd")

ROOTS = {
	"read": (os.path.join(BENCH, "apps"),),
	"write": (os.path.join(BENCH, "sites"),),
	"config": frozenset(),
}

GLOBALS = {"ROOTS": ROOTS, "HOOKS_PY": HOOKS_PY, "SITE_FILE": SITE_FILE, "TRAVERSAL": TRAVERSAL}
SETUP = "from frappe._audit_hook import is_allowed_path"

bench_audit_hook_read_allowed = NanoBenchmark(
	statement="is_allowed_path(HOOKS_PY, ROOTS, False)",
	setup=SETUP,
	globals=GLOBALS,
)

bench_audit_hook_write_allowed = NanoBenchmark(
	statement="is_allowed_path(SITE_FILE, ROOTS, True)",
	setup=SETUP,
	globals=GLOBALS,
)

bench_audit_hook_traversal_denied = NanoBenchmark(
	statement="is_allowed_path(TRAVERSAL, ROOTS, False)",
	setup=SETUP,
	globals=GLOBALS,
)

bench_audit_hook_realpath_baseline = NanoBenchmark(
	statement="os.path.realpath(HOOKS_PY)",
	setup="import os",
	globals=GLOBALS,
)
