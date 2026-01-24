import json

import frappe
from frappe.exceptions import SiteNotSpecifiedError
from frappe.utils.bench_helper import CliCtxObj


def _execute(context: CliCtxObj, method, args=None, kwargs=None, profile=False, extra_args=None):
	for site in context.sites:
		ret = ""
		try:
			frappe.init(site)
			frappe.connect()

			if args:
				try:
					fn_args = eval(args)
				except NameError:
					fn_args = [args]
			else:
				fn_args = ()

			if kwargs:
				fn_kwargs = eval(kwargs)
			else:
				fn_kwargs = {}

			if extra_args:
				# parse extra_args
				# if it starts with --, it is a kwarg
				# otherwise it is an arg
				# if it is a kwarg, the next argument is the value
				# if the next argument starts with --, the value is True
				# if there is no next argument, the value is True

				# examples:
				# bench execute method arg1 arg2 -> args=[arg1, arg2]
				# bench execute method --a 1 --b 2 -> kwargs={a: 1, b: 2}
				# bench execute method arg1 --a 1 -> args=[arg1], kwargs={a: 1}

				# we need to convert values to python objects if possible
				def parse_value(value):
					try:
						return json.loads(value)
					except Exception:
						return value

				extra_args = list(extra_args)
				while extra_args:
					arg = extra_args.pop(0)
					if arg.startswith("--"):
						key = arg[2:]
						if extra_args and not extra_args[0].startswith("--"):
							value = parse_value(extra_args.pop(0))
						else:
							value = True
						fn_kwargs[key] = value
					else:
						fn_args += (parse_value(arg),)

			pr = None
			if profile:
				import cProfile

				pr = cProfile.Profile()
				pr.enable()

			try:
				fn = frappe.get_attr(method)
			except Exception:
				fn = None

			if fn:
				ret = fn(*fn_args, **fn_kwargs)
			else:
				# eval is safe here because input is from console
				code = compile(method, "<bench execute>", "eval")
				ret = eval(code, globals(), locals())  # nosemgrep
				if callable(ret):
					suffix = "(*fn_args, **fn_kwargs)"
					code = compile(method + suffix, "<bench execute>", "eval")
					ret = eval(code, globals(), locals())  # nosemgrep

			if profile and pr:
				import pstats
				from io import StringIO

				pr.disable()
				s = StringIO()
				pstats.Stats(pr, stream=s).sort_stats("cumulative").print_stats(0.5)
				print(s.getvalue())

			if frappe.db:
				frappe.db.commit()
		finally:
			frappe.destroy()
		if ret:
			from frappe.utils.response import json_handler

			print(json.dumps(ret, default=json_handler).strip('"'))

	if not context.sites:
		raise SiteNotSpecifiedError
