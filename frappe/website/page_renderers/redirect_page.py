import nts
from nts.website.utils import build_response


class RedirectPage:
	def __init__(self, path, http_status_code=301):
		self.path = path
		self.http_status_code = http_status_code

	def can_render(self):
		return True

	def render(self):
		return build_response(
			self.path,
			"",
			self.http_status_code,
			{
				"Location": nts.flags.redirect_location or (nts.local.response or {}).get("location"),
				"Cache-Control": "no-store, no-cache, must-revalidate",
			},
		)
