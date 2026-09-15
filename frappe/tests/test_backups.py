import gzip
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from frappe.utils.backups import backup_sqlite_database


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
