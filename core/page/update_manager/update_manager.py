# For license information, please see license.txt

from __future__ import unicode_literals
import webnotes
from webnotes import _

@webnotes.whitelist(allow_roles=["System Manager", "Administrator"])
def update_this_app():
	import conf
	if hasattr(conf, "expires_on"):
		return _("This feature is only applicable to self hosted instances")
	
	from webnotes.utils import execute_in_shell, cstr, get_base_path
	err, out = execute_in_shell("cd %s && exec ssh-agent lib/wnf.py --update origin master" % \
		(get_base_path(),))

	return "\n".join(filter(None, [cstr(err), cstr(out)]))
