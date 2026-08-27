# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""The `Build` module: developer tooling for Module Def, Client Script and Translation.

The folder is also where `frappe/build.py` used to live, so the asset bundler's public names are
re-exported here. The bundler itself is `frappe.bundler` now; import it from there. This shim
exists so `from frappe.build import bundle` keeps working for apps that already do it.

"""

from frappe.bundler import *
