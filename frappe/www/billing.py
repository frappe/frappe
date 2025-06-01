import nts
from nts.utils import cint

no_cache = 1


def get_context(context):
	nts.db.commit()  # nosemgrep
	context = nts._dict()
	context.boot = get_boot()
	return context


def get_boot():
	return nts._dict(
		{
			"site_name": nts.local.site,
			"read_only_mode": nts.flags.read_only,
			"csrf_token": nts.sessions.get_csrf_token(),
			"setup_complete": cint(nts.get_system_settings("setup_complete")),
		}
	)
