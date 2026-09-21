from frappe.tests.microbenchmarks.utils import NanoBenchmark

ROOTS = {
	"trusted": ("/frappe-bench/apps", "/frappe-bench/sites/test.local", "/frappe-bench/env"),
	"untrusted": ("/tmp",),
}

SETUP = "from frappe._audit_hook import is_allowed_path"

bench_audit_hook_allowed_fast_path = NanoBenchmark(
	statement="is_allowed_path('/frappe-bench/apps/frappe/hooks.py', ROOTS)",
	setup=SETUP,
	globals={"ROOTS": ROOTS},
)

bench_audit_hook_traversal_slow_path = NanoBenchmark(
	statement="is_allowed_path('/frappe-bench/sites/test.local/public/../../../etc/passwd', ROOTS)",
	setup=SETUP,
	globals={"ROOTS": ROOTS},
)

bench_audit_hook_denied = NanoBenchmark(
	statement="is_allowed_path('/etc/passwd', ROOTS)",
	setup=SETUP,
	globals={"ROOTS": ROOTS},
)

bench_audit_hook_realpath_baseline = NanoBenchmark(
	statement="os.path.realpath('/frappe-bench/apps/frappe/hooks.py')",
	setup="import os",
)
