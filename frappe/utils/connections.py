import os.path
import socket
from pathlib import Path
from urllib.parse import urlparse

import frappe.utils
from frappe import get_conf
from frappe.exceptions import UrlSchemeNotSupported

REDIS_KEYS = ("redis_cache", "redis_queue")


def is_open(scheme, hostname, port, path, timeout=10):
	if scheme in ["redis", "rediss", "postgres", "mariadb"]:
		s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		conn = (hostname, int(port))
	elif scheme == "unix":
		s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
		conn = path
	else:
		raise UrlSchemeNotSupported(scheme)

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
	if db_type == "sqlite":
		db_path = Path(frappe.utils.get_site_path()) / "db" / f"{config.db_name}.db"
		return {db_type: db_path.is_file() and os.access(db_path, os.R_OK | os.W_OK)}
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
