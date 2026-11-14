import ipaddress
import socket
from urllib.parse import urljoin

from requests.models import PreparedRequest

MAX_URL_LENGTH = 2048


def absolute_url(base: str, href: str) -> str | None:
	"""`href` resolved against `base` and spelled as requests sends it, so a check reads the host that
	is requested. None for a malformed URL or one longer than MAX_URL_LENGTH."""
	request = PreparedRequest()
	try:
		request.prepare_url(urljoin(base, href.strip()), None)
	except ValueError:
		return None
	return request.url if len(request.url) <= MAX_URL_LENGTH else None


def canonical_host(host: str) -> str:
	"""The host as a resolver reads it, so `bücher.de` is `xn--bcher-kva.de`, `127.1` is `127.0.0.1`
	and `0:0::1` is `::1`."""
	host = host.strip(".").lower()
	try:
		return socket.inet_ntoa(socket.inet_aton(host))
	except OSError:
		pass
	try:
		address = ipaddress.ip_address(host)
		return str(getattr(address, "ipv4_mapped", None) or address)
	except ValueError:
		pass
	try:
		return host.encode("idna").decode("ascii")
	except UnicodeError:
		return host
