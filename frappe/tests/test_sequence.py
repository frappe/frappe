import frappe
from frappe.tests import IntegrationTestCase


class TestSequence(IntegrationTestCase):
	def generate_sequence_name(self) -> str:
		return self._testMethodName + "_" + frappe.generate_hash(length=5)

	def test_set_next_val(self):
		seq_name = self.generate_sequence_name()
		frappe.db.create_sequence(seq_name, check_not_exists=True, temporary=True)

		next_val = frappe.db.get_next_sequence_val(seq_name)
		frappe.db.set_next_sequence_val(seq_name, next_val + 1)
		self.assertEqual(next_val + 1, frappe.db.get_next_sequence_val(seq_name))

		next_val = frappe.db.get_next_sequence_val(seq_name)
		frappe.db.set_next_sequence_val(seq_name, next_val + 1, is_val_used=True)
		self.assertEqual(next_val + 2, frappe.db.get_next_sequence_val(seq_name))

	def test_create_sequence(self):
		seq_name = self.generate_sequence_name()
		frappe.db.create_sequence(seq_name, max_value=2, cycle=True, temporary=True)
		frappe.db.get_next_sequence_val(seq_name)
		frappe.db.get_next_sequence_val(seq_name)
		self.assertEqual(1, frappe.db.get_next_sequence_val(seq_name))

		seq_name = self.generate_sequence_name()
		frappe.db.create_sequence(seq_name, max_value=2, temporary=True)
		frappe.db.get_next_sequence_val(seq_name)
		frappe.db.get_next_sequence_val(seq_name)

		try:
			frappe.db.get_next_sequence_val(seq_name)
		except frappe.db.SequenceGeneratorLimitExceeded:
			pass
		else:
			self.fail("NEXTVAL didn't raise any error upon sequence's end")

		# without this, we're not able to move further
		# as postgres doesn't allow moving further in a transaction
		# when an error occurs
		frappe.db.rollback()

		seq_name = self.generate_sequence_name()
		frappe.db.create_sequence(seq_name, min_value=10, max_value=20, increment_by=5, temporary=True)
		self.assertEqual(10, frappe.db.get_next_sequence_val(seq_name))
		self.assertEqual(15, frappe.db.get_next_sequence_val(seq_name))
		self.assertEqual(20, frappe.db.get_next_sequence_val(seq_name))

	def test_recreate_preserves_definition_and_counter(self):
		# Re-creating with check_not_exists must be a no-op: neither the counter
		# nor the definition may change. Use a bounded, cycling sequence so a
		# clobbered definition would surface as a wrong value instead of cycling.
		seq_name = self.generate_sequence_name()
		frappe.db.create_sequence(seq_name, max_value=2, cycle=True, check_not_exists=True, temporary=True)
		self.assertEqual(1, frappe.db.get_next_sequence_val(seq_name))

		# Recreating with default args must not reset the cap to unbounded.
		frappe.db.create_sequence(seq_name, check_not_exists=True, temporary=True)
		self.assertEqual(2, frappe.db.get_next_sequence_val(seq_name))
		self.assertEqual(1, frappe.db.get_next_sequence_val(seq_name))  # cycled, cap intact

	def test_set_next_val_creates_missing_sequence(self):
		# Setting a value before the sequence exists (e.g. an explicit integer name
		# on a brand-new autoincrement doctype) must persist, so the next value
		# continues after it instead of restarting and colliding.
		if frappe.db.db_type != "sqlite":
			self.skipTest("SETVAL requires an existing sequence on MariaDB/Postgres")
		seq_name = self.generate_sequence_name()
		frappe.db.set_next_sequence_val(seq_name, 50, is_val_used=True)
		self.assertEqual(51, frappe.db.get_next_sequence_val(seq_name))

	def test_create_sequence_adopts_implicit_row(self):
		# A row auto-created by set_next_val carries no real definition, so a later
		# create_sequence must be able to declare it instead of being ignored. The
		# declaration is authoritative: a custom step starts from its own definition
		# rather than skewing off the placeholder counter.
		if frappe.db.db_type != "sqlite":
			self.skipTest("implicit-row adoption is SQLite-specific")
		seq_name = self.generate_sequence_name()
		frappe.db.set_next_sequence_val(seq_name, 5, is_val_used=True)
		frappe.db.create_sequence(seq_name, min_value=10, max_value=20, increment_by=5, temporary=True)
		self.assertEqual(10, frappe.db.get_next_sequence_val(seq_name))
		self.assertEqual(15, frappe.db.get_next_sequence_val(seq_name))
		self.assertEqual(20, frappe.db.get_next_sequence_val(seq_name))

	def test_autoincrement_naming_seeds_sequence(self):
		# Naming an autoincrement doctype fetches a value before insert without a
		# create_sequence call, so the sequence has to seed itself lazily from any
		# existing rows. This is the path that originally failed on SQLite.
		from frappe.core.doctype.doctype.test_doctype import new_doctype

		doctype = "seq_autoinc_" + frappe.generate_hash(length=5)
		dt = new_doctype(doctype, autoname="autoincrement").insert(ignore_permissions=True)
		self.addCleanup(dt.delete, ignore_permissions=True)

		for expected in range(1, 4):
			self.assertEqual(expected, frappe.new_doc(doctype).save(ignore_permissions=True).name)

	def test_create_missing_sequences_returns_list(self):
		from frappe.database.sequence import create_missing_sequences

		self.assertIsInstance(create_missing_sequences(), list)
