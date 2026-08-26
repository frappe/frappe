import random
import time

import frappe
from frappe.tests.microbenchmarks.utils import NanoBenchmark
from frappe.utils import flt
from frappe.utils.caching import redis_cache, request_cache, site_cache
from frappe.utils.data import cint, get_datetime
from frappe.utils.safe_exec import safe_exec

# NOTE: decorated functions themselves are benchmarks, since they aren't wrapped by any other
# function calls we don't need to move them to timeit style statements.


@site_cache
def bench_site_cache_no_arg():
	time.sleep(0.1)
	return 42


@site_cache
def bench_site_cache_many_args(x=4, y="abc", z=1.22):
	time.sleep(0.1)
	return 42


@site_cache(ttl=600)
def bench_site_cache_with_ttl():
	time.sleep(0.1)
	return 42


@request_cache
def bench_request_cache_many_args(x=4, y="abc", z=1.22):
	time.sleep(0.1)
	return 42


def bench_redis_cache_deco_with_local_cache():
	for i in range(100):
		cache_in_redis(i)


def bench_redis_cache_deco_without_local_cache():
	for i in range(100):
		cache_in_redis(i)
	frappe.local.cache.clear()


@redis_cache
def cache_in_redis(num):
	time.sleep(0.001)
	return num


bench_frappe_dict_getattr = NanoBenchmark("d.x", setup="d=frappe._dict(); d.x=1")
bench_frappe_dict_setattr = NanoBenchmark("d.x = 1", setup="d=frappe._dict();")


bench_local_proxy = NanoBenchmark("value_setter = frappe.db.set_value")


bench_flt_typical = NanoBenchmark(
	"""flt(x, 2)""",
	setup="x = random.uniform(1, 10000)",
	globals={"flt": flt, "random": random},
)

# Rarely this is specified in code.
# But certain hot loops can benefit from this.
bench_flt_explicit_rounding = NanoBenchmark(
	"""flt(x, 2, rounding_method="Banker's Rounding")""",
	setup="x = random.uniform(1, 10000)",
	globals={"flt": flt, "random": random},
)

bench_flt_no_rounding = NanoBenchmark(
	"flt(x)",
	setup="x = random.uniform(1, 10000)",
	globals={"flt": flt, "random": random},
)

bench_flt_str = NanoBenchmark(
	"flt(x, 2)",
	setup="x = str(random.uniform(1, 10000))",
	globals={"flt": flt, "random": random},
)

bench_cint_on_string = NanoBenchmark(
	"""cint(x)""",
	setup="x = str(random.randint(1, 10000))",
	globals={"cint": cint, "random": random},
)


bench_get_system_settings = NanoBenchmark("""frappe.get_system_settings("rounding_method")""")


bench_unknown_translations = NanoBenchmark("""frappe._("Unknown Strngi", lang="de")""")
bench_no_translation_required = NanoBenchmark("""frappe._("Unknown Strngi", lang="en")""")
bench_valid_translation = NanoBenchmark("""frappe._("User", lang="de")""")

bench_parse_datetime = NanoBenchmark(
	"get_datetime('2042-12-22 00:01:02.000042')", setup="", globals={"get_datetime": get_datetime}
)


def test_fn(doctype: str, **kwargs):
	pass


bench_frappe_call = NanoBenchmark("frappe.call(fn, {})", globals={"fn": test_fn})


script = """
def incr(x):
	x = x + 1
	return x

a = incr(1)
"""


def bench_safe_exec():
	return safe_exec(script)
