import contextlib
import gzip
<<<<<<< HEAD
=======
import io
import os
import re
import shutil
>>>>>>> 012b769 (test(backup): cover MariaDB export naming, table filters, partial marker and sql_mode)
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

<<<<<<< HEAD
from frappe.utils.backups import backup_sqlite_database
=======
import frappe
from frappe.database.sqlite.mariadb_dump import (
	Column,
	MariaDBDumpError,
	MariaDBDumpWriter,
	parse_table_shape,
)
from frappe.storage.blob import put_blob
from frappe.storage.cache import get_cache_path
from frappe.storage.memory_driver import fake
from frappe.storage.tests import unique_bytes
from frappe.tests import IntegrationTestCase
from frappe.tests.test_query_builder import db_type_is, run_only_if
from frappe.utils.backups import (
	BackupGenerator,
	backup_sqlite_database,
	fetch_latest_backups,
	get_remote_blob_filters,
	new_backup,
)


class TestLatestBackup(IntegrationTestCase):
	def test_same_second_backups_resolve_to_the_newer_file(self):
		with TemporaryDirectory() as directory:
			full = Path(directory) / "20990101_000000-site-database.sql.gz"
			partial = Path(directory) / "20990101_000000-site-partial-database.sql.gz"
			full.touch()
			partial.touch()
			os.utime(full, (time.time() - 1, time.time() - 1))

			# list the older file first so glob order alone would pick it
			with patch("frappe.utils.backups.glob", return_value=[str(full), str(partial)]):
				self.assertEqual(fetch_latest_backups(partial=True)["database"], str(partial))
>>>>>>> 1a637ff (test(backup): cover the MariaDB dump of a SQLite site)


class TestSQLiteBackup(unittest.TestCase):
	def test_backup_includes_committed_wal_changes(self):
		with TemporaryDirectory() as directory:
			directory = Path(directory)
			database_path = directory / "live.db"
			backup_path = directory / "backup.db.gz"
			restored_path = directory / "restored.db"

			with sqlite3.connect(database_path) as database:
				database.execute("PRAGMA journal_mode=WAL")
				database.execute("PRAGMA wal_autocheckpoint=0")
				database.execute("CREATE TABLE test_value (value INTEGER)")
				database.execute("INSERT INTO test_value VALUES (1)")
				database.commit()
				database.execute("PRAGMA wal_checkpoint(TRUNCATE)")
				database.execute("UPDATE test_value SET value = 2")
				database.commit()

				backup_sqlite_database(database_path, backup_path)

			with gzip.open(backup_path, "rb") as backup, open(restored_path, "wb") as restored:
				restored.write(backup.read())

			with sqlite3.connect(restored_path) as restored:
				self.assertEqual(restored.execute("SELECT value FROM test_value").fetchone(), (2,))
				self.assertEqual(restored.execute("PRAGMA integrity_check").fetchone(), ("ok",))
<<<<<<< HEAD
=======


class TestRemoteBlobBackup(IntegrationTestCase):
	"""Files backups stream blobs from remote storage drivers into their archives."""

	def setUp(self):
		super().setUp()
		self.addCleanup(frappe.db.rollback)
		# Ignore existing blobs without deleting documents or touching their remote storage.
		existing_checksums = frappe.get_all("File Blob", pluck="checksum")
		self.enterContext(
			patch(
				"frappe.utils.backups.get_remote_blob_filters",
				side_effect=lambda is_private: {
					**get_remote_blob_filters(is_private),
					"checksum": ("not in", existing_checksums),
				},
			)
		)
		self.store = self.enterContext(fake())
		self.directory = Path(self.enterContext(TemporaryDirectory()))

	def get_generator(self, compress: bool = False) -> BackupGenerator:
		extension = "tgz" if compress else "tar"
		return BackupGenerator(
			frappe.conf.db_name,
			frappe.conf.db_user,
			frappe.conf.db_password,
			db_type=frappe.conf.db_type,
			backup_path_files=str(self.directory / f"files.{extension}"),
			backup_path_private_files=str(self.directory / f"private-files.{extension}"),
			compress_files=compress,
		)

	def backup_files(self, compress: bool = False) -> tuple[Path, Path]:
		generator = self.get_generator(compress)
		generator.backup_files()
		return Path(generator.backup_path_files), Path(generator.backup_path_private_files)

	def put_remote_blob(self, filename: str, is_private: bool = False) -> tuple[str, bytes]:
		content = unique_bytes()
		blob = put_blob(io.BytesIO(content), is_private=is_private, filename=filename)
		folder = "private" if is_private else "public"
		return f"{frappe.get_site_path(folder, 'files')}/{blob.name}/{filename}", content

	def read_member(self, archive: Path, name: str) -> bytes | None:
		with tarfile.open(archive) as tar:
			if name not in tar.getnames():
				return None
			return tar.extractfile(name).read()

	def test_remote_blobs_go_into_the_archive_of_their_privacy(self):
		# each remote blob lands next to the local files in the archive of its own privacy,
		# at <public|private>/files/<blob>/<filename>, with its exact bytes
		public_name, public_content = self.put_remote_blob("public.txt")
		private_name, private_content = self.put_remote_blob("private.txt", is_private=True)

		public, private = self.backup_files()

		self.assertEqual(self.read_member(public, public_name), public_content)
		self.assertIsNone(self.read_member(public, private_name))
		self.assertEqual(self.read_member(private, private_name), private_content)
		self.assertIsNone(self.read_member(private, public_name))
		with tarfile.open(public) as tar:
			self.assertIn(frappe.get_site_path("public", "files"), tar.getnames())

	def test_restore_puts_remote_blob_at_its_cache_path(self):
		# extract_files runs `tar xf --strip 2` in the site folder; the blob must land where a
		# cached copy sits, so the restored site serves it and relocation to local reuses it
		name, content = self.put_remote_blob("restore.txt")
		blob = frappe.get_doc("File Blob", name.split("/")[-2])
		public, _ = self.backup_files()

		site = self.directory / "site"
		site.mkdir()
		subprocess.run(["tar", "xf", str(public), "--strip", "2"], cwd=site, check=True)

		cache_path = os.path.relpath(get_cache_path(blob), os.path.realpath(frappe.get_site_path()))
		self.assertEqual((site / cache_path).read_bytes(), content)

	def test_compressed_backup_with_remote_blobs(self):
		# a .tgz cannot be appended to, so tar writes a plain .tar.part, blobs are added, then
		# gzip writes the .tgz and the plain tar is removed
		name, content = self.put_remote_blob("compressed.txt")

		public, _ = self.backup_files(compress=True)

		with tarfile.open(public, "r:gz") as tar:
			self.assertEqual(tar.extractfile(name).read(), content)
		self.assertEqual(list(self.directory.glob("*.tar.part")), [])

	def test_compressed_backup_without_remote_blobs_keeps_the_tar_gzip_pipe(self):
		# sites with no remote blobs keep the single `tar | gzip` command, with no plain tar on disk
		with patch.object(BackupGenerator, "compress_archive") as compress_archive:
			public, private = self.backup_files(compress=True)

		compress_archive.assert_not_called()
		for archive in (public, private):
			with tarfile.open(archive, "r:gz") as tar:
				self.assertTrue(tar.getnames())

	def test_missing_remote_object_is_skipped(self):
		# a blob row whose object is gone must not fail the backup; the other blobs still go in
		present_name, present_content = self.put_remote_blob("present.txt")
		missing_name, _ = self.put_remote_blob("missing.txt")
		self.store.blobs.pop((False, missing_name.split("/files/", 1)[1]))

		public, _ = self.backup_files()

		self.assertEqual(self.read_member(public, present_name), present_content)
		self.assertIsNone(self.read_member(public, missing_name))

	def test_get_remote_blobs_filters_and_pages(self):
		# only Ready blobs of the asked privacy on a driver other than local come back, each
		# exactly once, even when every page holds a single row
		expected = {self.put_remote_blob(f"{index}.txt")[0].split("/")[-2] for index in range(3)}
		self.put_remote_blob("private.txt", is_private=True)
		for driver, status in (("local", "Ready"), ("memory", "Pending")):
			frappe.get_doc(
				doctype="File Blob",
				key=f"{driver}/{status}.txt",
				checksum=frappe.generate_hash(length=64),
				driver=driver,
				status=status,
			).insert()

		with patch("frappe.utils.backups.REMOTE_BLOB_BATCH_SIZE", 1):
			names = [row.name for row in self.get_generator().get_remote_blobs(is_private=False)]

		self.assertCountEqual(names, expected)

	def test_failed_compressed_backup_leaves_no_plain_tar(self):
		# any failed step of a compressed backup (tar, blob append or gzip) must not leave the
		# plain .tar.part behind; a blob shorter than its recorded size fails the append
		name, _ = self.put_remote_blob("short.txt")
		frappe.db.set_value("File Blob", name.split("/")[-2], "file_size", 10**6)

		with self.assertRaises(OSError):
			self.backup_files(compress=True)

		self.assertEqual(list(self.directory.glob("*.tar.part")), [])

	def test_pipe_backup_path_gets_no_blobs(self):
		# Pilot streams backups through named pipes, which cannot be appended to; a piped archive
		# stays exactly as tar wrote it, so the backup succeeds without blob members
		name, _ = self.put_remote_blob("piped.txt")
		pipe = self.directory / "files.tar"
		received = self.directory / "received.tar"
		os.mkfifo(pipe)

		def drain():
			with open(pipe, "rb") as source, open(received, "wb") as target:
				shutil.copyfileobj(source, target)

		reader = threading.Thread(target=drain, daemon=True)
		reader.start()
		self.get_generator().backup_files()
		reader.join(timeout=30)

		with tarfile.open(received) as tar:
			names = tar.getnames()
		self.assertIn(frappe.get_site_path("public", "files"), names)
		self.assertNotIn(name, names)


@run_only_if(db_type_is.SQLITE)
class TestMariaDBCompatibleBackup(IntegrationTestCase):
	def write_dump(self, rows_by_table: dict[str, tuple[str, list[tuple]]]) -> str:
		with TemporaryDirectory() as directory:
			database_path = Path(directory) / "site.db"
			with contextlib.closing(sqlite3.connect(database_path)) as database:
				for table, (columns, rows) in rows_by_table.items():
					database.execute(f'CREATE TABLE "{table}" ({columns})')
					placeholders = ", ".join("?" * len(rows[0]))
					database.executemany(f'INSERT INTO "{table}" VALUES ({placeholders})', rows)
				database.commit()
			dump_path = Path(directory) / "dump.sql.gz"
			MariaDBDumpWriter(database_path).write(dump_path, "-- begin frappe metadata\n")
			with gzip.open(dump_path, "rt") as dump:
				return dump.read()

	def test_export_keeps_explicit_filters_and_stays_out_of_native_lookup(self):
		backup = new_backup(ignore_files=True, ignore_conf=True, include_doctypes="ToDo", for_mariadb=True)
		self.addCleanup(os.remove, backup.backup_path_conf)
		self.addCleanup(os.remove, backup.backup_path_db)

		self.assertTrue(backup.backup_path_db.endswith("-partial-database-mariadb.sql.gz"))
		self.assertNotEqual(fetch_latest_backups()["database"], backup.backup_path_db)
		with gzip.open(backup.backup_path_db, "rt") as dump:
			content = dump.read()
		self.assertIn("-- Partial Backup of Frappe Site", content)
		tables = set(re.findall(r"^create table `([^`]+)`", content, re.M | re.I))
		self.assertEqual(tables, {"tabToDo"})

	def test_dump_uses_mariadb_schema_and_literals(self):
		dump = self.write_dump(
			{
				"tabToDo": (
					"name varchar(140) primary key, idx int, description text, date date",
					[("todo-1", "", "it's a\nline \\ here", "2026-01-01 10:30:00")],
				),
				"table_without_doctype": ("path text default 'c:\\'", [("d:",)]),
			}
		)

		create = dump[dump.index("create table `tabToDo`") :]
		self.assertIn("name varchar(140) primary key", create)
		self.assertIn("`description` longtext", create)
		self.assertIn("COLLATE=utf8mb4_unicode_ci", create)
		self.assertIn("INSERT INTO `tabToDo` (`name`, `idx`, `description`, `date`) VALUES", dump)
		self.assertIn("('todo-1',0,'it\\'s a\\nline \\\\ here','2026-01-01')", dump)
		self.assertNotIn('"tabToDo"', dump)
		self.assertIn("SET SESSION sql_mode='STRICT_TRANS_TABLES,", dump)
		self.assertNotIn("NO_BACKSLASH_ESCAPES", dump)
		self.assertIn("`path` longtext DEFAULT 'c:\\\\'", dump)

	def test_keeps_unique_index_on_columns_with_a_plain_index(self):
		dump = self.write_dump(
			{
				"tabToDo": (
					"name varchar(140) primary key, creation datetime(6) unique",
					[("todo-1", "2026-01-01 10:30:00")],
				)
			}
		)
		self.assertIn("index creation(creation)", dump)
		self.assertRegex(dump, r"CREATE UNIQUE INDEX IF NOT EXISTS `[^`]+` ON `tabToDo` \(`creation`\);")

	def test_refuses_keys_that_collide_in_mariadb_collation(self):
		with self.assertRaises(MariaDBDumpError) as error:
			self.write_dump(
				{
					"tabRole": (
						"name varchar(140) primary key, role_name varchar(140)",
						[
							("Gate Role", "Gate Role"),
							("gate role", "gate role"),
							("Résumé", "Résumé"),
							("resume", "resume"),
						],
					)
				}
			)
		self.assertIn("tabRole", str(error.exception))
		self.assertIn("'gate role'", str(error.exception))
		self.assertIn("'resume'", str(error.exception))

	def test_refuses_numbers_mariadb_cannot_store(self):
		with self.assertRaises(MariaDBDumpError) as error:
			self.write_dump(
				{
					"tabToDo": (
						"name varchar(140) primary key, idx int",
						[("todo-1", "NaN"), ("todo-2", 2147483648), ("todo-3", 2147483647)],
					),
					"table_without_doctype": ("amount real", [(1e13,), (999999999999.5,)]),
				}
			)
		self.assertIn("tabToDo.idx: 'NaN' is not a number", str(error.exception))
		self.assertIn(
			"tabToDo.idx: 2147483648 is outside the range of int(11) (row todo-2)", str(error.exception)
		)
		self.assertIn(
			"table_without_doctype.amount: 10000000000000.0 is outside the range of decimal(21,9)",
			str(error.exception),
		)
		self.assertNotIn("2147483647", str(error.exception))
		self.assertNotIn("999999999999.5", str(error.exception))

		currency = Column("price", "decimal(3,2) NOT NULL DEFAULT 0")
		self.assertTrue(currency.is_in_range(9.99))
		self.assertTrue(currency.is_in_range(9.994))
		self.assertFalse(currency.is_in_range(9.995))
		self.assertTrue(Column("qty", "int(11)").is_in_range(2147483647.4))

	def test_refuses_text_and_json_mariadb_cannot_store(self):
		with self.assertRaises(MariaDBDumpError) as error:
			self.write_dump(
				{
					"tabComment": (
						"name varchar(140) primary key, subject text",
						[("ascii", "a" * 65536), ("emoji", "😀" * 16384), ("fits", "😀" * 16383)],
					),
					"tabBackground Task": (
						"name varchar(140) primary key, arguments text",
						[("valid", '{"a": 1}'), ("empty", ""), ("nan", '{"a": NaN}'), ("null", None)],
					),
				}
			)
		self.assertIn(
			"tabComment.subject: value of 65536 bytes exceeds text (row ascii)", str(error.exception)
		)
		self.assertIn(
			"tabComment.subject: value of 65536 bytes exceeds text (row emoji)", str(error.exception)
		)
		self.assertIn("tabBackground Task.arguments: '' is not valid JSON (row empty)", str(error.exception))
		self.assertIn(
			"""tabBackground Task.arguments: '{"a": NaN}' is not valid JSON (row nan)""", str(error.exception)
		)
		self.assertNotIn("(row fits)", str(error.exception))
		self.assertNotIn("(row valid)", str(error.exception))
		self.assertNotIn("(row null)", str(error.exception))

	def test_sequence_continues_after_the_highest_name(self):
		dump = self.write_dump(
			{
				"tabWeb Form List Column": ("name bigint primary key", [(3,), (7,)]),
				"__frappe_sqlite_sequences": (
					"name text primary key, current int, increment int, min_value int, max_value int, cycle int, declared int",
					[("web_form_list_column_id_seq", 3, 1, 1, None, 0, 1)],
				),
			}
		)
		self.assertIn("SELECT SETVAL(`web_form_list_column_id_seq`, 7, 1);", dump)

	def test_parses_keys_from_create_table(self):
		shape = parse_table_shape(
			"CREATE TABLE `t` (`a` varchar(10) NOT NULL DEFAULT 'x,y', `c` varchar(10) DEFAULT 'c:\\\\', "
			"b int UNIQUE, PRIMARY KEY (`a`), KEY `ab` (`a`, b), UNIQUE `bu` (b(10))) ENGINE=InnoDB"
		)
		self.assertEqual(shape.primary_key, ("a",))
		self.assertEqual(shape.columns["a"].default, "'x,y'")
		self.assertEqual(shape.columns["c"].default, "'c:\\\\'")
		self.assertFalse(shape.columns["a"].is_nullable)
		self.assertEqual(
			[(i.name, i.columns, i.unique) for i in shape.indexes],
			[("b", ("b",), True), ("ab", ("a", "b"), False), ("bu", ("b",), True)],
		)
>>>>>>> 1a637ff (test(backup): cover the MariaDB dump of a SQLite site)
