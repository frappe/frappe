import atexit
import os
import subprocess
from urllib.parse import unquote


class PgTmp:
	def __init__(self, tmp_dir=None):
		self.tmp_dir = tmp_dir
		self.pg_connection_string = None
		self.pg_socket_dir = None

	def __enter__(self):
		self._start_pg_tmp()
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		self._stop_pg_tmp()

	def _start_pg_tmp(self):
		try:
			cmd = ["pg_tmp"]
			if self.tmp_dir:
				cmd.extend(["-d", self.tmp_dir])
			result = subprocess.run(cmd, capture_output=True, text=True, check=True)
			self.pg_connection_string = result.stdout.strip()
			self.pg_socket_dir = unquote(self.pg_connection_string.split("=")[1])
			atexit.register(self._stop_pg_tmp)
		except subprocess.CalledProcessError:
			raise RuntimeError("Failed to start pg_tmp. Is it installed and in your PATH?")
		except FileNotFoundError:
			raise RuntimeError("pg_tmp not found. Please install it or add it to your PATH.")

	def _stop_pg_tmp(self):
		if self.pg_socket_dir:
			subprocess.run(["pg_tmp", "-d", self.pg_socket_dir], check=True)
			self.pg_socket_dir = None
			self.pg_connection_string = None

	def get_connection_string(self):
		return self.pg_connection_string

	def get_socket_dir(self):
		return self.pg_socket_dir
