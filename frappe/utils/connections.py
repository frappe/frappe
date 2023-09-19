import socket
from urllib.parse import urlparse

from frappe import get_conf

REDIS_KEYS = ("redis_cache", "redis_queue", "redis_socketio")


def is_open(ip, port, timeout=10):
	s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	s.settimeout(timeout)
	try:
		s.connect((ip, int(port)))
		s.shutdown(socket.SHUT_RDWR)
		return True
	except OSError:
		return False
	finally:
		s.close()


def check_database():
	config = get_conf()
	db_type = config.get("db_type", "mariadb")
	db_host = config.get("db_host", "127.0.0.1")
	db_port = config.get("db_port", 3306 if db_type == "mariadb" else 5432)
	return {db_type: is_open(db_host, db_port)}


def check_redis(redis_services=None):
	config = get_conf()
	services = redis_services or REDIS_KEYS
	status = {}
	for conn in services:
		redis_url = urlparse(config.get(conn)).netloc
		redis_host, redis_port = redis_url.split(":")
		status[conn] = is_open(redis_host, redis_port)
	return status


def check_connection(redis_services=None):
	service_status = {}
	service_status.update(check_database())
	service_status.update(check_redis(redis_services))
	return service_status
