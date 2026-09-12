# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Tests for streaming backups - artifacts written to a pipe instead of a file.

A streamed artifact is read by a consumer as it is produced, so two properties
that are invisible on disk become load-bearing: the destination must be opened
exactly once for the whole artifact (a reader sees EOF the moment the last
writer closes), and the framework must never delete it (the pipe belongs to
whoever created it).
"""

import gzip
import os
import subprocess
import tempfile
import threading
from shutil import which
from unittest import skipIf
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase, timeout
from frappe.utils import CallbackManager
from frappe.utils.backups import BackupGenerator, is_stream_path, new_backup

SQLITE = frappe.conf.db_type == "sqlite"


class FifoReader:
	"""Drain a FIFO to EOF on a background thread, the way a consumer would."""

	def __init__(self, path: str):
		os.mkfifo(path)
		self.path = path
		self.data = b""
		self._thread = threading.Thread(target=self._read, daemon=True)
		self._thread.start()

	def _read(self):
		with open(self.path, "rb") as fifo:
			self.data = fifo.read()

	def result(self, timeout: int = 120) -> bytes:
		self._thread.join(timeout)
		if self._thread.is_alive():
			raise AssertionError(f"nothing closed the write end of {self.path} within {timeout}s")
		return self.data


class TestStreamingBackups(IntegrationTestCase):
	def generator(self, **kwargs) -> BackupGenerator:
		return BackupGenerator(
			frappe.conf.db_name,
			frappe.conf.db_user,
			frappe.conf.db_password,
			db_socket=frappe.conf.db_socket,
			db_host=frappe.conf.db_host,
			db_port=frappe.conf.db_port,
			db_type=frappe.conf.db_type,
			**kwargs,
		)

	def test_is_stream_path(self):
		with tempfile.TemporaryDirectory() as tmp:
			fifo = os.path.join(tmp, "fifo")
			regular = os.path.join(tmp, "regular")
			os.mkfifo(fifo)
			open(regular, "w").close()

			self.assertTrue(is_stream_path(fifo))
			self.assertTrue(is_stream_path("/dev/null"))
			self.assertFalse(is_stream_path(regular))
			self.assertFalse(is_stream_path(os.path.join(tmp, "missing")))
			self.assertFalse(is_stream_path(None))

	@timeout(300)
	@skipIf(SQLITE, "Metadata header is only written for MariaDB/Postgres")
	def test_database_reaches_the_reader_whole(self):
		"""The header and the dump must arrive as one stream.

		The generator writes a gzip metadata header and then the dump. If those
		were two separate opens of the destination, a reader on a pipe would see
		EOF after the header and the dump would be written to nobody.
		"""
		with tempfile.TemporaryDirectory() as tmp:
			fifo = os.path.join(tmp, "database.sql.gz")
			reader = FifoReader(fifo)

			new_backup(
				ignore_files=True,
				backup_path_db=fifo,
				backup_path_conf=os.path.join(tmp, "site_config_backup.json"),
				force=True,
			)

			dump = gzip.decompress(reader.result()).decode(errors="replace")
			self.assertIn("begin frappe metadata", dump)
			self.assertIn(frappe.__version__, dump)
			self.assertIn("tabDocType", dump)

	@timeout(300)
	def test_streamed_destination_is_left_alone(self):
		with tempfile.TemporaryDirectory() as tmp:
			fifo = os.path.join(tmp, "database.sql.gz")
			reader = FifoReader(fifo)
			rollback = CallbackManager()

			new_backup(
				ignore_files=True,
				backup_path_db=fifo,
				backup_path_conf=os.path.join(tmp, "site_config_backup.json"),
				force=True,
				rollback_callback=rollback,
			)
			reader.result()
			rollback.run()

			self.assertTrue(os.path.exists(fifo), "the consumer's pipe was deleted")
			self.assertTrue(is_stream_path(fifo))

	@timeout(300)
	def test_site_config_streams_to_a_pipe(self):
		with tempfile.TemporaryDirectory() as tmp:
			fifo = os.path.join(tmp, "site_config_backup.json")
			reader = FifoReader(fifo)

			odb = self.generator(backup_path_conf=fifo)
			odb.set_backup_file_name()
			odb.copy_site_config()

			with open(os.path.join(frappe.get_site_path(), "site_config.json"), "rb") as site_config:
				self.assertEqual(reader.result(), site_config.read())

	@timeout(600)
	def test_files_stream_to_pipes(self):
		with tempfile.TemporaryDirectory() as tmp:
			public = os.path.join(tmp, "files.tar")
			private = os.path.join(tmp, "private-files.tar")
			readers = [FifoReader(public), FifoReader(private)]

			odb = self.generator(backup_path_files=public, backup_path_private_files=private)
			odb.set_backup_file_name()
			odb.backup_files()

			for reader in readers:
				# a tar's magic sits at offset 257 of the first header block
				self.assertEqual(reader.result()[257:262], b"ustar")

	@timeout(300)
	@skipIf(not which("gpg"), "gpg is required to encrypt a backup")
	@skipIf(SQLITE, "Metadata header is only written for MariaDB/Postgres")
	def test_encrypted_database_streams_to_a_pipe(self):
		"""Encryption happens inside the pipeline, so it works on a stream.

		Encrypting used to mean rewriting a finished file in place, which a pipe
		cannot offer - the bytes are already gone.
		"""
		passphrase = "correct horse battery staple"

		with (
			tempfile.TemporaryDirectory() as tmp,
			self.change_settings("System Settings", encrypt_backup=1),
			patch(
				"frappe.utils.backups.get_or_generate_backup_encryption_key",
				return_value=passphrase,
			),
		):
			fifo = os.path.join(tmp, "database-enc.sql.gz")
			reader = FifoReader(fifo)

			new_backup(
				ignore_files=True,
				backup_path_db=fifo,
				backup_path_conf=os.path.join(tmp, "site_config_backup.json"),
				force=True,
			)

			decrypted = subprocess.run(
				[
					"gpg",
					"--batch",
					"--yes",
					"--quiet",
					"--pinentry-mode",
					"loopback",
					"--passphrase",
					passphrase,
					"--decrypt",
				],
				input=reader.result(),
				capture_output=True,
				check=True,
			).stdout

			self.assertIn("begin frappe metadata", gzip.decompress(decrypted).decode(errors="replace"))


class TestBackupCleanup(IntegrationTestCase):
	def generator(self, **kwargs) -> BackupGenerator:
		return BackupGenerator(
			frappe.conf.db_name,
			frappe.conf.db_user,
			frappe.conf.db_password,
			db_socket=frappe.conf.db_socket,
			db_host=frappe.conf.db_host,
			db_port=frappe.conf.db_port,
			db_type=frappe.conf.db_type,
			**kwargs,
		)

	def test_failed_step_deletes_files_but_not_streams(self):
		with tempfile.TemporaryDirectory() as tmp:
			fifo = os.path.join(tmp, "stream")
			regular = os.path.join(tmp, "regular")
			os.mkfifo(fifo)
			open(regular, "w").close()

			def failing_step():
				raise ValueError("dump failed")

			with self.assertRaises(ValueError):
				self.generator().delete_if_step_fails(failing_step, fifo, regular)

			self.assertTrue(os.path.exists(fifo))
			self.assertFalse(os.path.exists(regular))

	def test_rollback_removes_every_registered_path(self):
		"""Each registered rollback must delete its own path, not the last one."""
		with tempfile.TemporaryDirectory() as tmp:
			paths = [os.path.join(tmp, name) for name in ("public.tar", "private.tar")]
			for path in paths:
				open(path, "w").close()

			rollback = CallbackManager()
			self.generator(rollback_callback=rollback).delete_if_step_fails(lambda: None, *paths)
			rollback.run()

			for path in paths:
				self.assertFalse(os.path.exists(path), f"{path} survived the rollback")

	def test_rollback_tolerates_an_already_deleted_path(self):
		with tempfile.TemporaryDirectory() as tmp:
			path = os.path.join(tmp, "database.sql.gz")
			open(path, "w").close()

			rollback = CallbackManager()
			self.generator(rollback_callback=rollback).delete_if_step_fails(lambda: None, path)
			os.remove(path)
			rollback.run()
