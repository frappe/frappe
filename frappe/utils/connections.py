import socket
from urllib.parse import urlparse

from frappe import get_conf
from frappe.exceptions import UrlSchemeNotSupported

REDIS_KEYS = ("redis_cache", "redis_queue")


def can_connect(sock: socket.socket, address: tuple[str, int] | str, timeout: int | float) -> bool:
	"""
	Check whether we can connect to a socket address.

	Args:
		sock: The socket object to use for the connection.
		address: The address to connect to (tuple for network, string for unix).
		timeout: Connection timeout in seconds.

	Returns:
		True if connection was successful, False otherwise.
	"""
	sock.settimeout(timeout)
	try:
		sock.connect(address)
		sock.shutdown(socket.SHUT_RDWR)
		return True
	except OSError:
		return False
	finally:
		sock.close()


def is_open(
	scheme: str,
	hostname: str | None,
	port: int | str | None,
	path: str | None,
	timeout: int | float = 10,
) -> bool:
	"""
	Check if a service is reachable via socket connection.

	Args:
		scheme: The URL scheme (redis, mariadb, etc.) or 'unix'.
		hostname: The remote host to connect to.
		port: The port number to connect to.
		path: The path to the unix socket (if scheme is 'unix').
		timeout: Connection timeout in seconds.

	Returns:
		True if the service is reachable, False otherwise.
	"""
	if scheme in ("redis", "rediss", "postgres", "mariadb"):
		if not hostname or not port:
			return False

		try:
			addresses = socket.getaddrinfo(hostname, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
		except (socket.gaierror, TypeError):
			return False

		# Try all addresses returned by getaddrinfo
		for family, socket_type, proto, _, address in addresses:
			s = socket.socket(family, socket_type, proto)
			if can_connect(s, address, timeout):
				return True
		return False

	if scheme == "unix":
		if not path:
			return False
		s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
		return can_connect(s, path, timeout)

	raise UrlSchemeNotSupported(scheme)


def check_database():
	config = get_conf()
	db_type = config.get("db_type", "mariadb")
	if db_socket := config.get("db_socket"):
		return {db_type: is_open("unix", None, None, db_socket)}
	db_host = config.get("db_host", "127.0.0.1")
	db_port = config.get("db_port", 3306 if db_type == "mariadb" else 5432)
	return {db_type: is_open(db_type, db_host, db_port, None)}


def check_redis(redis_services=None):
	config = get_conf()
	services = redis_services or REDIS_KEYS
	status = {}
	for srv in services:
		url = urlparse(config[srv])
		status[srv] = is_open(url.scheme, url.hostname, url.port, url.path)
	return status


def check_connection(redis_services=None):
	service_status = {}
	service_status.update(check_database())
	service_status.update(check_redis(redis_services))
	return service_status
