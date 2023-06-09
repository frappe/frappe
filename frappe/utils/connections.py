import socket
from urllib.parse import urlparse

from frappe import get_conf

REDIS_KEYS = ("redis_cache", "redis_queue", "redis_socketio")


def is_open(scheme, hostname, port, path, timeout=10):
	if scheme == 'unix':
		s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
		conn = path
	else:
		s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		conn = (hostname, port)
	s.settimeout(timeout)
	try:
		s.connect(conn)
		s.shutdown(socket.SHUT_RDWR)
		return True
	except OSError:
		return False
	finally:
		s.close()


def check_database():
	config = get_conf()
	db_type = config.get("db_type", "mariadb")
	db_host = config.get("db_host", "localhost")
	db_port = config.get("db_port", 3306 if db_type == "mariadb" else 5432)
	return {db_type: is_open('other', db_host, db_port, None)}


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
