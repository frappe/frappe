# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import base64
import os
import shutil
import tempfile
import zipfile
from contextlib import contextmanager
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import frappe
from frappe import _
from frappe.core.api.file import (
	create_new_folder,
	get_attached_images,
	get_files_in_folder,
	move_file,
	unzip_file,
)
from frappe.core.doctype.file.exceptions import FileTypeNotAllowed
from frappe.core.doctype.file.utils import get_corrupted_image_msg, get_extension, get_web_image
from frappe.desk.form.utils import add_comment, remove_attach
from frappe.exceptions import ValidationError
from frappe.tests import IntegrationTestCase
from frappe.utils import get_files_path, set_request

if TYPE_CHECKING:
	from frappe.core.doctype.file.file import File

test_content1 = "Hello"
test_content2 = "Hello World"


def remove_attach_with_fid(fid):
	frappe.form_dict.fid = fid
	try:
		remove_attach()
	finally:
		frappe.form_dict.pop("fid", None)


def make_test_doc(ignore_permissions=False):
	d = frappe.new_doc("ToDo")
	d.description = "Test"
	d.assigned_by = frappe.session.user
	d.save(ignore_permissions)
	return d.doctype, d.name


@contextmanager
def make_test_image_file(private=False):
	file_path = frappe.get_app_path("frappe", "tests/data/sample_image_for_optimization.jpg")
	with open(file_path, "rb") as f:
		file_content = f.read()

	test_file = frappe.get_doc(
		{
			"doctype": "File",
			"file_name": "sample_image_for_optimization.jpg",
			"content": file_content,
			"is_private": private,
		}
	).insert()
	# remove those flags
	_test_file: File = frappe.get_doc("File", test_file.name)

	try:
		yield _test_file
	finally:
		_test_file.delete()


class TestSimpleFile(IntegrationTestCase):
	def setUp(self):
		self.attached_to_doctype, self.attached_to_docname = make_test_doc()
		self.test_content = test_content1
		_file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "test1.txt",
				"attached_to_doctype": self.attached_to_doctype,
				"attached_to_name": self.attached_to_docname,
				"content": self.test_content,
			}
		)
		_file.save()
		self.saved_file_url = _file.file_url

	def test_save(self):
		_file = frappe.get_doc("File", {"file_url": self.saved_file_url})
		content = _file.get_content()
		self.assertEqual(content, self.test_content)


class TestBinaryFileContent(IntegrationTestCase):
	def test_ole_xls_content_not_decoded(self):
		from frappe.core.doctype.file.file import OLE_FILE_SIGNATURE

		attached_to_doctype, attached_to_docname = make_test_doc()
		xls_content = OLE_FILE_SIGNATURE + b"\x00\x01Sheet1\x00Amount\x00" + b"\x20" * 64
		_file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": f"statement-{frappe.generate_hash(length=8)}.xls",
				"attached_to_doctype": attached_to_doctype,
				"attached_to_name": attached_to_docname,
				"content": xls_content,
			}
		)
		_file.save()

		saved_file = frappe.get_doc("File", _file.name)
		content = saved_file.get_content()
		self.assertIsInstance(content, bytes)
		self.assertTrue(content.startswith(OLE_FILE_SIGNATURE))


class TestFSRollbacks(IntegrationTestCase):
	def test_rollback_from_file_system(self):
		file_name = content = frappe.generate_hash()
		file = frappe.new_doc("File", file_name=file_name, content=content).insert()
		self.assertTrue(file.exists_on_disk())

		frappe.db.rollback()
		self.assertFalse(file.exists_on_disk())


class TestExtensionValidations(IntegrationTestCase):
	@IntegrationTestCase.change_settings("System Settings", {"allowed_file_extensions": "JPG\nCSV"})
	def test_allowed_extension(self):
		set_request(method="POST", path="/")
		file_name = content = frappe.generate_hash()
		bad_file = frappe.new_doc("File", file_name=f"{file_name}.png", content=content)
		self.assertRaises(FileTypeNotAllowed, bad_file.insert)

		bad_file = frappe.new_doc("File", file_name=f"{file_name}.csv", content=content).insert()
		frappe.db.rollback()
		self.assertFalse(bad_file.exists_on_disk())

	@IntegrationTestCase.change_settings("System Settings", {"allowed_file_extensions": "JPG\nCSV"})
	def test_allowlist_blocks_extension_without_known_mimetype(self):
		set_request(method="POST", path="/")
		file_name = content = frappe.generate_hash()
		bad_file = frappe.new_doc("File", file_name=f"{file_name}.phtml", content=content)
		self.assertRaises(FileTypeNotAllowed, bad_file.insert)


class TestBase64File(IntegrationTestCase):
	def setUp(self):
		self.attached_to_doctype, self.attached_to_docname = make_test_doc()
		self.test_content = base64.b64encode(test_content1.encode("utf-8"))
		_file: frappe.Document = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "test_base64.txt",
				"attached_to_doctype": self.attached_to_doctype,
				"attached_to_name": self.attached_to_docname,
				"content": self.test_content,
				"decode": True,
			}
		)
		_file.save()
		self.saved_file_url = _file.file_url

	def test_saved_content(self):
		_file: frappe.Document = frappe.get_doc("File", {"file_url": self.saved_file_url})
		content = _file.get_content()
		self.assertEqual(content, test_content1)


class TestSameFileName(IntegrationTestCase):
	def test_saved_content(self):
		self.attached_to_doctype, self.attached_to_docname = make_test_doc()
		self.test_content1 = test_content1
		self.test_content2 = test_content2
		_file1 = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "testing.txt",
				"attached_to_doctype": self.attached_to_doctype,
				"attached_to_name": self.attached_to_docname,
				"content": self.test_content1,
			}
		)
		_file1.save()
		_file2 = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "testing.txt",
				"attached_to_doctype": self.attached_to_doctype,
				"attached_to_name": self.attached_to_docname,
				"content": self.test_content2,
			}
		)
		_file2.save()
		self.saved_file_url1 = _file1.file_url
		self.saved_file_url2 = _file2.file_url

		_file = frappe.get_doc("File", {"file_url": self.saved_file_url1})
		content1 = _file.get_content()
		self.assertEqual(content1, self.test_content1)
		_file = frappe.get_doc("File", {"file_url": self.saved_file_url2})
		content2 = _file.get_content()
		self.assertEqual(content2, self.test_content2)

	def test_saved_content_private(self):
		_file1 = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "testing-private.txt",
				"content": test_content1,
				"is_private": 1,
			}
		).insert()
		_file2 = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "testing-private.txt",
				"content": test_content2,
				"is_private": 1,
			}
		).insert()

		_file = frappe.get_doc("File", {"file_url": _file1.file_url})
		self.assertEqual(_file.get_content(), test_content1)

		_file = frappe.get_doc("File", {"file_url": _file2.file_url})
		self.assertEqual(_file.get_content(), test_content2)


class TestSameContent(IntegrationTestCase):
	def setUp(self):
		self.attached_to_doctype1, self.attached_to_docname1 = make_test_doc()
		self.attached_to_doctype2, self.attached_to_docname2 = make_test_doc()
		self.test_content1 = test_content1
		self.test_content2 = test_content1
		self.orig_filename = "hello.txt"
		self.dup_filename = "hello2.txt"
		_file1 = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": self.orig_filename,
				"attached_to_doctype": self.attached_to_doctype1,
				"attached_to_name": self.attached_to_docname1,
				"content": self.test_content1,
			}
		)
		_file1.save()

		_file2 = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": self.dup_filename,
				"attached_to_doctype": self.attached_to_doctype2,
				"attached_to_name": self.attached_to_docname2,
				"content": self.test_content2,
			}
		)

		_file2.save()

	def test_saved_content(self):
		self.assertFalse(os.path.exists(get_files_path(self.dup_filename)))

	def test_attachment_limit(self):
		doctype, docname = make_test_doc()
		from frappe.custom.doctype.property_setter.property_setter import make_property_setter

		limit_property = make_property_setter("ToDo", None, "max_attachments", 1, "int", for_doctype=True)
		file1 = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "test-attachment",
				"attached_to_doctype": doctype,
				"attached_to_name": docname,
				"content": "test",
			}
		)

		file1.insert()

		file2 = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "test-attachment",
				"attached_to_doctype": doctype,
				"attached_to_name": docname,
				"content": "test2",
			}
		)

		self.assertRaises(frappe.exceptions.AttachmentLimitReached, file2.insert)
		limit_property.delete()
		frappe.clear_cache(doctype="ToDo")

	def test_create_attachment_copy(self):
		doctype, docname = make_test_doc()
		source_file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": f"existing-file-{frappe.generate_hash(length=8)}.txt",
				"content": "Existing attachment content",
			}
		).insert()
		comment_count_before = frappe.db.count(
			"Comment", {"reference_doctype": doctype, "reference_name": docname}
		)

		copied_file = source_file.create_attachment_copy(doctype, docname)
		comment_count_after = frappe.db.count(
			"Comment", {"reference_doctype": doctype, "reference_name": docname}
		)

		self.assertNotEqual(copied_file.name, source_file.name)
		self.assertEqual(copied_file.file_url, source_file.file_url)
		self.assertEqual(copied_file.attached_to_doctype, doctype)
		self.assertEqual(copied_file.attached_to_name, docname)
		self.assertEqual(
			copied_file.folder,
			frappe.db.get_value("File", {"is_attachments_folder": 1}),
		)
		self.assertEqual(comment_count_after, comment_count_before + 1)

	def test_create_attachment_copy_respects_attachment_limit(self):
		doctype, docname = make_test_doc()
		from frappe.custom.doctype.property_setter.property_setter import make_property_setter

		limit_property = make_property_setter("ToDo", None, "max_attachments", 1, "int", for_doctype=True)
		source_file_1 = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": f"existing-limit-file-{frappe.generate_hash(length=8)}.txt",
				"content": "Existing attachment content 1",
			}
		).insert()
		source_file_2 = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": f"existing-limit-file-{frappe.generate_hash(length=8)}.txt",
				"content": "Existing attachment content 2",
			}
		).insert()

		try:
			source_file_1.create_attachment_copy(doctype, docname)
			self.assertRaises(
				frappe.exceptions.AttachmentLimitReached,
				source_file_2.create_attachment_copy,
				doctype,
				docname,
			)
		finally:
			limit_property.delete()
			frappe.clear_cache(doctype="ToDo")

	def test_utf8_bom_content_decoding(self):
		utf8_bom_content = test_content1.encode("utf-8-sig")
		_file: frappe.Document = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "utf8bom.txt",
				"attached_to_doctype": self.attached_to_doctype1,
				"attached_to_name": self.attached_to_docname1,
				"content": utf8_bom_content,
				"decode": False,
			}
		)
		_file.save()
		saved_file = frappe.get_doc("File", _file.name)
		file_content_decoded = saved_file.get_content(encodings=["utf-8"])
		self.assertEqual(file_content_decoded[0], "\ufeff")
		file_content_properly_decoded = saved_file.get_content(encodings=["utf-8-sig", "utf-8"])
		self.assertEqual(file_content_properly_decoded, test_content1)

	def test_toggle_is_private_renames_on_name_collision(self):
		file_name = f"toggle_collision_{frappe.generate_hash(length=6)}.txt"
		private_file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": file_name,
				"content": "private original",
				"is_private": 1,
			}
		).insert()
		public_file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": file_name,
				"content": "public different",
				"is_private": 0,
			}
		).insert()
		self.addCleanup(frappe.delete_doc, "File", private_file.name, force=True)
		self.addCleanup(frappe.delete_doc, "File", public_file.name, force=True)

		# this used to raise FileExistsError; it must now auto-rename instead
		public_file.is_private = 1
		public_file.save()

		public_file.reload()
		self.assertNotEqual(public_file.file_url, private_file.file_url)
		self.assertTrue(public_file.file_url.startswith("/private/files/"))
		self.assertEqual(public_file.get_content(), "public different")
		# the pre-existing private file must be completely untouched
		self.assertEqual(private_file.get_content(), "private original")


class TestFile(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self.delete_test_data()
		self.upload_file()

	def tearDown(self):
		try:
			frappe.get_doc("File", {"file_name": "file_copy.txt"}).delete()
		except frappe.DoesNotExistError:
			pass

	def delete_test_data(self):
		test_file_data = frappe.get_all(
			"File",
			pluck="name",
			filters={"is_home_folder": 0, "is_attachments_folder": 0},
			order_by="creation desc",
		)
		for f in test_file_data:
			frappe.delete_doc("File", f, force=True)

	def upload_file(self):
		_file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "file_copy.txt",
				"attached_to_name": "",
				"attached_to_doctype": "",
				"folder": self.get_folder("Test Folder 1", "Home").name,
				"content": "Testing file copy example.",
			}
		)
		_file.save()
		self.saved_folder = _file.folder
		self.saved_name = _file.name
		self.saved_filename = get_files_path(_file.file_name)

	def get_folder(self, folder_name, parent_folder="Home"):
		return frappe.get_doc(
			{"doctype": "File", "file_name": _(folder_name), "is_folder": 1, "folder": _(parent_folder)}
		).insert()

	def tests_after_upload(self):
		self.assertEqual(self.saved_folder, _("Home/Test Folder 1"))
		file_folder = frappe.db.get_value("File", self.saved_name, "folder")
		self.assertEqual(file_folder, _("Home/Test Folder 1"))

	def test_file_copy(self):
		folder = self.get_folder("Test Folder 2", "Home")

		file = frappe.get_doc("File", {"file_name": "file_copy.txt"})
		move_file([{"name": file.name}], folder.name, file.folder)
		file = frappe.get_doc("File", {"file_name": "file_copy.txt"})

		self.assertEqual(_("Home/Test Folder 2"), file.folder)

	def test_folder_depth(self):
		result1 = self.get_folder("d1", "Home")
		self.assertEqual(result1.name, "Home/d1")
		result2 = self.get_folder("d2", "Home/d1")
		self.assertEqual(result2.name, "Home/d1/d2")
		result3 = self.get_folder("d3", "Home/d1/d2")
		self.assertEqual(result3.name, "Home/d1/d2/d3")
		result4 = self.get_folder("d4", "Home/d1/d2/d3")
		_file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "folder_copy.txt",
				"attached_to_name": "",
				"attached_to_doctype": "",
				"folder": result4.name,
				"content": "Testing folder copy example",
			}
		)
		_file.save()

	def test_folder_copy(self):
		folder = self.get_folder("Test Folder 2", "Home")
		folder = self.get_folder("Test Folder 3", "Home/Test Folder 2")
		_file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "folder_copy.txt",
				"attached_to_name": "",
				"attached_to_doctype": "",
				"folder": folder.name,
				"content": "Testing folder copy example",
			}
		)
		_file.save()

		move_file([{"name": folder.name}], "Home/Test Folder 1", folder.folder)

		file = frappe.get_doc("File", {"file_name": "folder_copy.txt"})
		file_copy_txt = frappe.get_value("File", {"file_name": "file_copy.txt"})
		if file_copy_txt:
			frappe.get_doc("File", file_copy_txt).delete()

		self.assertEqual(_("Home/Test Folder 1/Test Folder 3"), file.folder)

	def test_default_folder(self):
		d = frappe.get_doc({"doctype": "File", "file_name": _("Test_Folder"), "is_folder": 1})
		d.save()
		self.assertEqual(d.folder, "Home")

	def test_on_delete(self):
		file = frappe.get_doc("File", {"file_name": "file_copy.txt"})
		file.delete()

		self.assertEqual(frappe.db.get_value("File", _("Home/Test Folder 1"), "file_size"), 0)

		folder = self.get_folder("Test Folder 3", "Home/Test Folder 1")
		_file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "folder_copy.txt",
				"attached_to_name": "",
				"attached_to_doctype": "",
				"folder": folder.name,
				"content": "Testing folder copy example",
			}
		)
		_file.save()

		folder = frappe.get_doc("File", "Home/Test Folder 1/Test Folder 3")
		self.assertRaises(ValidationError, folder.delete)

	def test_same_file_url_update(self):
		attached_to_doctype1, attached_to_docname1 = make_test_doc()
		attached_to_doctype2, attached_to_docname2 = make_test_doc()

		file1 = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "file1.txt",
				"attached_to_doctype": attached_to_doctype1,
				"attached_to_name": attached_to_docname1,
				"is_private": 1,
				"content": test_content1,
			}
		).insert()

		file2 = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "file2.txt",
				"attached_to_doctype": attached_to_doctype2,
				"attached_to_name": attached_to_docname2,
				"is_private": 1,
				"content": test_content1,
			}
		).insert()

		self.assertEqual(file1.is_private, 1)
		self.assertEqual(file2.is_private, 1)
		self.assertEqual(file1.file_url, file2.file_url)
		self.assertTrue(os.path.exists(file1.get_full_path()))

		file1.is_private = 0
		file1.save()

		file2 = frappe.get_doc("File", file2.name)

		# file1 flipped correctly.
		self.assertEqual(file1.is_private, 0)
		self.assertTrue(file1.file_url.startswith("/files/"))

		# file2 must be untouched — this is the fix. Old behaviour propagated
		# file1's is_private and file_url to file2 via update_existing_file_docs.
		self.assertEqual(file2.is_private, 1)
		self.assertTrue(file2.file_url.startswith("/private/files/"))

		# Bytes readable at both paths after the flip.
		self.assertTrue(os.path.exists(file1.get_full_path()))
		self.assertTrue(os.path.exists(file2.get_full_path()))

	def test_parent_directory_validation_in_file_url(self):
		file1 = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "parent_dir.txt",
				"is_private": 1,
				"content": test_content1,
			}
		).insert()

		file1.file_url = "/private/files/../test.txt"
		self.assertRaises(ValidationError, file1.save)

		# No validation to see if file exists
		file1.reload()
		file1.file_url = "/private/files/parent_dir2.txt"
		self.assertRaises(OSError, file1.save)

	def test_file_url_validation(self):
		test_file: File = frappe.new_doc("File")
		test_file.update({"file_name": "logo", "file_url": "https://frappe.io/files/frappe.png"})

		self.assertIsNone(test_file.validate())

		# bad path
		test_file.file_url = "/usr/bin/man"
		self.assertRaisesRegex(
			ValidationError, f"Cannot access file path {test_file.file_url}", test_file.validate
		)

		test_file.file_url = None
		test_file.file_name = "/usr/bin/man"
		self.assertRaisesRegex(ValidationError, "There is some problem with the file url", test_file.validate)

		test_file.file_url = None
		test_file.file_name = "_file"
		self.assertRaisesRegex(IOError, "does not exist", test_file.validate)

		test_file.file_url = None
		test_file.file_name = "/private/files/_file"
		self.assertRaisesRegex(ValidationError, "File name cannot have", test_file.validate)

	def test_make_thumbnail(self):
		# test web image
		test_file: File = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "logo",
				"file_url": frappe.utils.get_url("/_test/assets/image.jpg"),
			}
		).insert(ignore_permissions=True)

		test_file.make_thumbnail()
		self.assertEqual(test_file.thumbnail_url, "/files/image_small.jpg")

		# test web image without extension
		test_file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "logo",
				"file_url": frappe.utils.get_url("/_test/assets/image"),
			}
		).insert(ignore_permissions=True)

		test_file.make_thumbnail()
		self.assertTrue(test_file.thumbnail_url.endswith("_small.jpg"))

		# test local image
		test_file.db_set("thumbnail_url", None)
		test_file.reload()
		test_file.file_url = "/files/image_small.jpg"
		test_file.make_thumbnail(suffix="xs", crop=True)
		self.assertEqual(test_file.thumbnail_url, "/files/image_small_xs.jpg")

		frappe.clear_messages()
		test_file.db_set("thumbnail_url", None)
		test_file.reload()
		test_file.file_url = frappe.utils.get_url("unknown.jpg")
		test_file.make_thumbnail(suffix="xs")
		self.assertEqual(
			frappe.message_log[0].get("message"),
			f"File '{frappe.utils.get_url('unknown.jpg')}' not found",
		)
		self.assertEqual(test_file.thumbnail_url, None)

	def test_file_unzip(self):
		file_path = frappe.get_app_path("frappe", "www/_test/assets/file.zip")
		public_file_path = frappe.get_site_path("public", "files")
		try:
			import shutil

			shutil.copy(file_path, public_file_path)
		except Exception:
			pass

		test_file = frappe.get_doc(
			{
				"doctype": "File",
				"file_url": "/files/file.zip",
			}
		).insert(ignore_permissions=True)

		self.assertListEqual(
			[file.file_name for file in unzip_file(test_file.name)],
			["css_asset.css", "image.jpg", "js_asset.min.js"],
		)

		test_file = frappe.get_doc(
			{
				"doctype": "File",
				"file_url": frappe.utils.get_url("/_test/assets/image.jpg"),
			}
		).insert(ignore_permissions=True)
		self.assertRaisesRegex(ValidationError, "not a zip file", test_file.unzip)

	@IntegrationTestCase.change_settings("System Settings", {"max_zip_extract_size": 0})
	def test_file_unzip_respects_dedicated_extract_size_setting(self):
		file_path = frappe.get_app_path("frappe", "www/_test/assets/file.zip")
		public_file_path = frappe.get_site_path("public", "files")
		try:
			shutil.copy(file_path, public_file_path)
		except Exception:
			pass

		test_file = frappe.get_doc(
			{
				"doctype": "File",
				"file_url": "/files/file.zip",
			}
		).insert(ignore_permissions=True)
		self.addCleanup(test_file.delete)

		file_count_before = frappe.db.count("File")

		# a dedicated, tighter zip-extraction budget must be enforced even though
		# max_file_size (used for ordinary uploads) stays at its generous default
		with patch.dict(frappe.conf, {"max_zip_extract_size": 1000}):
			self.assertRaisesRegex(ValidationError, "maximum allowed size", test_file.unzip)

		self.assertTrue(frappe.db.exists("File", test_file.name))
		self.assertEqual(frappe.db.count("File"), file_count_before)

	def test_file_unzip_requires_read_permission(self):
		file_path = frappe.get_app_path("frappe", "www/_test/assets/file.zip")
		with open(file_path, "rb") as f:
			zip_content = f.read()

		try:
			frappe.set_user("test@example.com")
			test_file = frappe.get_doc(
				{
					"doctype": "File",
					"file_name": "file.zip",
					"content": zip_content,
					"is_private": 1,
				}
			).insert()

			file_count_before = frappe.db.count("File")

			# block unzip
			frappe.set_user("test4@example.com")
			self.assertRaises(frappe.PermissionError, unzip_file, test_file.name)
			self.assertTrue(frappe.db.exists("File", test_file.name))
			self.assertEqual(frappe.db.count("File"), file_count_before)

			# allow unzip
			frappe.set_user("test@example.com")
			self.assertListEqual(
				[file.file_name for file in unzip_file(test_file.name)],
				["css_asset.css", "image.jpg", "js_asset.min.js"],
			)
		finally:
			frappe.set_user("Administrator")

	def test_file_unzip_rolls_back_children_on_mid_extraction_failure(self):
		fixture_dir = tempfile.mkdtemp()
		zip_path = os.path.join(fixture_dir, "corrupt.zip")
		with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_STORED) as zf:
			zf.writestr("a.txt", "hello-a")
			zf.writestr("b.txt", "hello-b")
			zf.writestr("c.txt", "hello-c")

		# flip a byte in the last member's stored (uncompressed) data so it fails
		# its CRC check on read, without touching the central directory metadata
		with open(zip_path, "rb") as f:
			data = bytearray(f.read())
		corrupt_offset = data.rfind(b"hello-c")
		self.assertNotEqual(corrupt_offset, -1)
		data[corrupt_offset] ^= 0xFF
		with open(zip_path, "wb") as f:
			f.write(data)

		public_file_path = frappe.get_site_path("public", "files")
		shutil.copy(zip_path, public_file_path)

		test_file = frappe.get_doc(
			{
				"doctype": "File",
				"file_url": "/files/corrupt.zip",
			}
		).insert(ignore_permissions=True)
		self.addCleanup(test_file.delete)

		file_count_before = frappe.db.count("File")

		# a.txt and b.txt extract fine and get saved before c.txt fails its CRC check;
		# the whole call must still roll back to a clean no-op
		self.assertRaisesRegex(ValidationError, "not a valid zip file", test_file.unzip)

		self.assertTrue(frappe.db.exists("File", test_file.name))
		self.assertEqual(frappe.db.count("File"), file_count_before)
		self.assertFalse(frappe.db.exists("File", {"file_name": "a.txt"}))
		self.assertFalse(frappe.db.exists("File", {"file_name": "b.txt"}))

	def test_create_file_without_file_url(self):
		test_file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "logo",
				"content": "frappe",
			}
		).insert()
		assert test_file is not None

	def test_symlinked_files_folder(self):
		files_dir = os.path.abspath(get_files_path())
		with convert_to_symlink(files_dir):
			file = frappe.get_doc(
				{
					"doctype": "File",
					"file_name": "symlinked_folder_test.txt",
					"content": "42",
				}
			)
			file.save()
			file.content = ""
			file._content = ""
			file.save().reload()
			self.assertIn("42", file.get_content())

	@IntegrationTestCase.change_settings(
		"System Settings", {"allow_guests_to_upload_files": 1, "allowed_doctypes_for_guest_uploads": "ToDo"}
	)
	def test_guest_upload_to_non_allowed_doctype(self):
		"""Verify Guest cannot upload to a restricted DocType."""
		from werkzeug.test import EnvironBuilder
		from werkzeug.wrappers import Request

		from frappe.handler import upload_file

		builder = EnvironBuilder(path="/", base_url="http://localhost")
		frappe.local.request = Request(builder.get_environ())

		frappe.set_user("Guest")
		frappe.form_dict.doctype = "User"
		frappe.form_dict.docname = "Administrator"

		try:
			self.assertRaises(frappe.PermissionError, upload_file)
		finally:
			frappe.set_user("Administrator")
			frappe.form_dict.pop("doctype", None)
			frappe.form_dict.pop("docname", None)
			if hasattr(frappe.local, "request"):
				del frappe.local.request

	@IntegrationTestCase.change_settings(
		"System Settings",
		{"allow_guests_to_upload_files": 1, "allowed_doctypes_for_guest_uploads": "User\nToDo"},
	)
	def test_guest_upload_to_allowed_doctype(self):
		"""Verify Guest can upload to an explicitly whitelisted DocType."""
		from werkzeug.test import EnvironBuilder
		from werkzeug.wrappers import Request

		from frappe.handler import upload_file

		builder = EnvironBuilder(path="/", base_url="http://localhost")
		frappe.local.request = Request(builder.get_environ())

		frappe.set_user("Administrator")
		todo = frappe.get_doc({"doctype": "ToDo", "description": "Test Target"}).insert()

		frappe.set_user("Guest")
		frappe.form_dict.doctype = "ToDo"
		frappe.form_dict.docname = todo.name
		frappe.form_dict.file_url = "https://frappe.io/assets/img/logo.png"
		frappe.form_dict.file_name = "guest_logo.png"

		file_doc = None
		try:
			file_doc = upload_file()
			self.assertEqual(file_doc.attached_to_name, todo.name)
		finally:
			frappe.set_user("Administrator")

			if file_doc:
				file_doc.delete()
			todo.delete()

			frappe.form_dict.pop("doctype", None)
			frappe.form_dict.pop("docname", None)
			frappe.form_dict.pop("file_url", None)
			frappe.form_dict.pop("file_name", None)

			if hasattr(frappe.local, "request"):
				del frappe.local.request

	@IntegrationTestCase.change_settings(
		"System Settings", {"allow_guests_to_upload_files": 1, "allowed_doctypes_for_guest_uploads": ""}
	)
	def test_guest_upload_for_empty_whitelist(self):
		"""Verify Guest can upload anywhere if the configuration whitelist string is left completely empty."""
		from werkzeug.test import EnvironBuilder
		from werkzeug.wrappers import Request

		from frappe.handler import upload_file

		builder = EnvironBuilder(path="/", base_url="http://localhost")
		frappe.local.request = Request(builder.get_environ())

		frappe.set_user("Guest")
		frappe.form_dict.doctype = "User"
		frappe.form_dict.docname = "Administrator"
		frappe.form_dict.file_url = "https://frappe.io/assets/img/logo.png"
		frappe.form_dict.file_name = "guest_fallback.png"

		file_doc = None
		try:
			file_doc = upload_file()
			self.assertEqual(file_doc.attached_to_name, "Administrator")
		finally:
			frappe.set_user("Administrator")
			if file_doc:
				file_doc.delete()

			frappe.form_dict.pop("doctype", None)
			frappe.form_dict.pop("docname", None)
			frappe.form_dict.pop("file_url", None)
			frappe.form_dict.pop("file_name", None)

			if hasattr(frappe.local, "request"):
				del frappe.local.request


@contextmanager
def convert_to_symlink(directory):
	"""Moves a directory to temp directory and symlinks original path for testing"""
	try:
		new_directory = shutil.move(directory, tempfile.mkdtemp())
		os.symlink(new_directory, directory)
		yield
	finally:
		os.unlink(directory)
		shutil.move(new_directory, directory)


class TestAttachment(IntegrationTestCase):
	test_doctype = "Test For Attachment"
	test_child_doctype = "Test For Attachment Child"
	test_submittable_doctype = "Test For Attachment Submittable"

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.get_doc(
			doctype="DocType",
			name=cls.test_child_doctype,
			module="Custom",
			custom=1,
			istable=1,
			fields=[
				{"label": "Row Attachment", "fieldname": "row_attachment", "fieldtype": "Attach"},
			],
		).insert(ignore_if_duplicate=True)
		frappe.get_doc(
			doctype="DocType",
			name=cls.test_submittable_doctype,
			module="Custom",
			custom=1,
			is_submittable=1,
			fields=[
				{"label": "Title", "fieldname": "title", "fieldtype": "Data"},
				{"label": "Attachment", "fieldname": "attachment", "fieldtype": "Attach"},
			],
			permissions=[
				{"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "submit": 1}
			],
		).insert(ignore_if_duplicate=True)
		frappe.get_doc(
			doctype="DocType",
			name=cls.test_doctype,
			module="Custom",
			custom=1,
			fields=[
				{"label": "Title", "fieldname": "title", "fieldtype": "Data"},
				{"label": "Attachment", "fieldname": "attachment", "fieldtype": "Attach"},
				{
					"label": "Items",
					"fieldname": "items",
					"fieldtype": "Table",
					"options": cls.test_child_doctype,
				},
			],
		).insert(ignore_if_duplicate=True)

	@classmethod
	def tearDownClass(cls):
		frappe.db.rollback()
		frappe.delete_doc("DocType", cls.test_doctype)
		frappe.delete_doc("DocType", cls.test_child_doctype)
		frappe.delete_doc("DocType", cls.test_submittable_doctype)

	def test_file_attachment_on_update(self):
		doc = frappe.get_doc(doctype=self.test_doctype, title="test for attachment on update").insert()

		file = frappe.get_doc(
			{"doctype": "File", "file_name": "test_attach.txt", "content": "Test Content"}
		).save()

		doc.attachment = file.file_url
		doc.save()

		exists = frappe.db.exists(
			"File",
			{
				"file_name": "test_attach.txt",
				"file_url": file.file_url,
				"attached_to_doctype": self.test_doctype,
				"attached_to_name": doc.name,
				"attached_to_field": "attachment",
			},
		)

		self.assertTrue(exists)

	def test_url_attachment_is_attached_to_duplicated_document(self):
		doc = frappe.get_doc(doctype=self.test_doctype, title="test url attachment on duplicate")
		doc.attachment = "https://example.com/spec.pdf"
		doc.insert()

		duplicate = frappe.copy_doc(doc).insert()

		self.assertTrue(
			frappe.db.exists(
				"File",
				{
					"file_url": "https://example.com/spec.pdf",
					"attached_to_doctype": self.test_doctype,
					"attached_to_name": duplicate.name,
					"attached_to_field": "attachment",
				},
			)
		)

	def test_no_file_created_for_non_file_attach_value(self):
		doc = frappe.get_doc(doctype=self.test_doctype, title="test non file attach value")
		doc.attachment = "not a file"
		doc.insert()

		self.assertFalse(
			frappe.db.exists(
				"File",
				{
					"attached_to_doctype": self.test_doctype,
					"attached_to_name": doc.name,
					"attached_to_field": "attachment",
				},
			)
		)

	def test_delete_file_referenced_in_attach_field(self):
		doc = frappe.get_doc(doctype=self.test_doctype, title="test delete referenced file").insert()
		file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "test_referenced.txt",
				"content": "Referenced Content",
				"attached_to_doctype": self.test_doctype,
				"attached_to_name": doc.name,
				"attached_to_field": "attachment",
			}
		).save()
		doc.attachment = file.file_url
		doc.save()

		self.assertRaises(frappe.LinkExistsError, remove_attach_with_fid, file.name)

		doc.attachment = None
		doc.save()
		remove_attach_with_fid(file.name)
		self.assertFalse(frappe.db.exists("File", file.name))

	def test_delete_file_referenced_in_child_table_attach_field(self):
		doc = frappe.get_doc(doctype=self.test_doctype, title="test delete child referenced file").insert()
		file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "test_child_referenced.txt",
				"content": "Child Referenced Content",
				"attached_to_doctype": self.test_doctype,
				"attached_to_name": doc.name,
				"attached_to_field": "row_attachment",
			}
		).save()
		doc.append("items", {"row_attachment": file.file_url})
		doc.save()

		self.assertRaises(frappe.LinkExistsError, remove_attach_with_fid, file.name)

		doc.items = []
		doc.save()
		remove_attach_with_fid(file.name)
		self.assertFalse(frappe.db.exists("File", file.name))

	def test_direct_deletion_of_referenced_file_is_blocked(self):
		doc = frappe.get_doc(doctype=self.test_doctype, title="test direct delete").insert()
		file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "test_direct_delete.txt",
				"content": "Direct Delete Content",
				"attached_to_doctype": self.test_doctype,
				"attached_to_name": doc.name,
				"attached_to_field": "attachment",
			}
		).save()
		doc.attachment = file.file_url
		doc.save()

		self.assertRaises(frappe.LinkExistsError, frappe.delete_doc, "File", file.name)

		frappe.delete_doc("File", file.name, force=True)
		self.assertFalse(frappe.db.exists("File", file.name))

	def test_delete_file_sharing_url_with_another_file_is_allowed(self):
		doc = frappe.get_doc(doctype=self.test_doctype, title="test shared url delete").insert()
		file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "test_shared_url.txt",
				"content": "Shared Url Content",
				"attached_to_doctype": self.test_doctype,
				"attached_to_name": doc.name,
				"attached_to_field": "attachment",
			}
		).save()
		duplicate = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "test_shared_url_copy.txt",
				"content": "Shared Url Content",
				"attached_to_doctype": self.test_doctype,
				"attached_to_name": doc.name,
				"attached_to_field": "attachment",
			}
		).save()
		doc.attachment = file.file_url
		doc.save()

		self.assertEqual(duplicate.file_url, file.file_url)

		frappe.delete_doc("File", duplicate.name)
		self.assertFalse(frappe.db.exists("File", duplicate.name))

	def test_delete_file_referenced_on_submitted_document_is_allowed(self):
		doc = frappe.get_doc(doctype=self.test_submittable_doctype, title="test submitted delete").insert()
		file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "test_submitted.txt",
				"content": "Submitted Content",
				"attached_to_doctype": self.test_submittable_doctype,
				"attached_to_name": doc.name,
				"attached_to_field": "attachment",
			}
		).save()
		doc.attachment = file.file_url
		doc.save()
		doc.submit()

		frappe.delete_doc("File", file.name)
		self.assertFalse(frappe.db.exists("File", file.name))

	def test_document_delete_cascades_referenced_attachment(self):
		doc = frappe.get_doc(doctype=self.test_doctype, title="test cascade delete").insert()
		file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "test_cascade.txt",
				"content": "Cascade Content",
				"attached_to_doctype": self.test_doctype,
				"attached_to_name": doc.name,
				"attached_to_field": "attachment",
			}
		).save()
		doc.attachment = file.file_url
		doc.save()

		doc.delete()
		self.assertFalse(frappe.db.exists("File", file.name))


class TestCopyAttachmentsFromAmendedFrom(IntegrationTestCase):
	"""Test that attached_to_field and folder are copied when amending a document."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from frappe.core.doctype.doctype.test_doctype import new_doctype

		cls.test_doctype = "Test Amendable Attachment"
		new_doctype(
			cls.test_doctype,
			is_submittable=1,
			fields=[
				{"label": "Title", "fieldname": "title", "fieldtype": "Data"},
				{"label": "Attachment", "fieldname": "attachment", "fieldtype": "Attach"},
			],
		).insert(ignore_if_duplicate=True)

	@classmethod
	def tearDownClass(cls):
		frappe.db.rollback()
		frappe.delete_doc_if_exists("DocType", cls.test_doctype)

	def test_attached_to_field_and_folder_copied_on_amend(self):
		# Create custom folder
		custom_folder = frappe.get_doc(
			{"doctype": "File", "file_name": "Test Amend Folder", "is_folder": 1, "folder": "Home"}
		).insert()

		# Create original document and attach file with attached_to_field and custom folder
		doc = frappe.get_doc(doctype=self.test_doctype, title="Original").insert()
		file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "amend_test_attach.txt",
				"content": "Test Content",
				"attached_to_doctype": self.test_doctype,
				"attached_to_name": doc.name,
				"attached_to_field": "attachment",
				"folder": custom_folder.name,
			}
		).insert()

		doc.attachment = file.file_url
		doc.save()

		# Submit and cancel
		doc.submit()
		doc.cancel()

		# Amend document
		amended_doc = frappe.copy_doc(doc)
		amended_doc.docstatus = 0
		amended_doc.amended_from = doc.name
		amended_doc.save()

		# Verify copied file has attached_to_field and folder from original
		copied_files = frappe.get_all(
			"File",
			filters={
				"attached_to_doctype": self.test_doctype,
				"attached_to_name": amended_doc.name,
				"file_name": "amend_test_attach.txt",
			},
			fields=["name", "attached_to_field", "folder"],
		)
		self.assertEqual(len(copied_files), 1, "Exactly one file should be copied to amended doc")
		self.assertEqual(copied_files[0].attached_to_field, "attachment")
		self.assertEqual(copied_files[0].folder, custom_folder.name)


class TestAttachmentsAccess(IntegrationTestCase):
	def setUp(self) -> None:
		frappe.db.delete("File", {"is_folder": 0})

	def test_list_private_attachments(self):
		frappe.set_user("test4@example.com")
		self.attached_to_doctype, self.attached_to_docname = make_test_doc()

		frappe.new_doc(
			"File",
			file_name="test_user_attachment.txt",
			attached_to_doctype=self.attached_to_doctype,
			attached_to_name=self.attached_to_docname,
			content="Testing User",
			is_private=1,
		).insert()

		frappe.new_doc(
			"File",
			file_name="test_user_standalone.txt",
			content="User Home",
			is_private=1,
		).insert()

		frappe.set_user("test@example.com")

		frappe.new_doc(
			"File",
			file_name="test_sm_attachment.txt",
			attached_to_doctype=self.attached_to_doctype,
			attached_to_name=self.attached_to_docname,
			content="Testing System Manager",
			is_private=1,
		).insert()

		frappe.new_doc(
			"File",
			file_name="test_sm_standalone.txt",
			content="System Manager Home",
			is_private=1,
		).insert()

		system_manager_files = [file.file_name for file in get_files_in_folder("Home")["files"]]
		system_manager_attachments_files = [
			file.file_name for file in get_files_in_folder("Home/Attachments")["files"]
		]

		frappe.set_user("test4@example.com")
		user_files = [file.file_name for file in get_files_in_folder("Home")["files"]]
		user_attachments_files = [file.file_name for file in get_files_in_folder("Home/Attachments")["files"]]

		self.assertIn("test_sm_standalone.txt", system_manager_files)
		self.assertNotIn("test_sm_standalone.txt", user_files)

		self.assertIn("test_user_standalone.txt", user_files)
		self.assertNotIn("test_user_standalone.txt", system_manager_files)

		self.assertIn("test_sm_attachment.txt", system_manager_attachments_files)
		self.assertIn("test_user_attachment.txt", system_manager_attachments_files)
		self.assertIn("test_user_attachment.txt", user_attachments_files)

	def tearDown(self) -> None:
		frappe.set_user("Administrator")
		frappe.db.rollback()


class TestFileUtils(IntegrationTestCase):
	def test_extract_images_from_doc(self):
		is_private = not frappe.get_meta("ToDo").make_attachments_public

		# with filename in data URI
		todo = frappe.get_doc(
			doctype="ToDo",
			description='Test <img src="data:image/png;filename=pix.png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=">',
		).insert()
		self.assertTrue(frappe.db.exists("File", {"attached_to_name": todo.name, "is_private": is_private}))
		self.assertRegex(todo.description, r"<img src=\"(.*)/files/pix\.png(.*)\">")
		self.assertListEqual(get_attached_images("ToDo", [todo.name])[todo.name], ["/private/files/pix.png"])

		# without filename in data URI
		todo = frappe.get_doc(
			doctype="ToDo",
			description='Test <img src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=">',
		).insert()
		filename = frappe.db.exists("File", {"attached_to_name": todo.name})
		self.assertIn(f'<img src="{frappe.get_doc("File", filename).file_url}', todo.description)

	def test_extract_images_from_comment(self):
		"""
		Ensure that images are extracted from comments and become private attachments.
		"""
		is_private = not frappe.get_meta("ToDo").make_attachments_public
		test_doc = frappe.get_doc(doctype="ToDo", description="comment test").insert()
		comment = add_comment(
			"ToDo",
			test_doc.name,
			'<div class="ql-editor read-mode"><img src="data:image/png;filename=pix.png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="></div>',
			frappe.session.user,
			frappe.session.user,
		)

		self.assertTrue(
			frappe.db.exists("File", {"attached_to_name": test_doc.name, "is_private": is_private})
		)
		self.assertRegex(comment.content, r"<img src=\"(.*)/files/pix\.png(.*)\">")

	def test_extract_images_from_communication(self):
		"""
		Ensure that images are extracted from communication and become public attachments.
		"""
		is_private = not frappe.get_meta("Communication").make_attachments_public
		communication = frappe.get_doc(
			doctype="Communication",
			communication_type="Communication",
			communication_medium="Email",
			content='<div class="ql-editor read-mode"><img src="data:image/png;filename=pix.png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="></div>',
			recipients="to <to@test.com>",
			cc=None,
			bcc=None,
			sender="sender@test.com",
		).insert(ignore_permissions=True)

		self.assertTrue(
			frappe.db.exists("File", {"attached_to_name": communication.name, "is_private": is_private})
		)
		self.assertRegex(communication.content, r"<img src=\"(.*)/files/pix\.png(.*)\">")

	def test_broken_image(self):
		"""Ensure that broken inline images don't cause errors."""
		is_private = not frappe.get_meta("Communication").make_attachments_public
		communication = frappe.get_doc(
			doctype="Communication",
			communication_type="Communication",
			communication_medium="Email",
			content='<div class="ql-editor read-mode"><img src="data:image/png;filename=pix.png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CY="></div>',
			recipients="to <to@test.com>",
			cc=None,
			bcc=None,
			sender="sender@test.com",
		).insert(ignore_permissions=True)

		self.assertFalse(
			frappe.db.exists("File", {"attached_to_name": communication.name, "is_private": is_private})
		)
		self.assertIn(f'<img src="#broken-image" alt="{get_corrupted_image_msg()}">', communication.content)

	def test_create_new_folder(self):
		folder = create_new_folder("test_folder", "Home")
		self.assertTrue(folder.is_folder)

	def test_get_web_image_follows_redirect_to_allowed_address(self):
		from io import BytesIO

		from PIL import Image as PILImage

		buf = BytesIO()
		PILImage.new("RGB", (2, 2)).save(buf, format="JPEG")
		image_bytes = buf.getvalue()

		redirect_response = MagicMock(is_redirect=True, headers={"Location": "http://8.8.4.4/final.jpg"})
		final_response = MagicMock(is_redirect=False, content=image_bytes)
		final_response.raise_for_status.return_value = None

		with patch("requests.get", side_effect=[redirect_response, final_response]) as mock_get:
			_, _, extn = get_web_image("http://8.8.8.8/initial.jpg")

		self.assertEqual(mock_get.call_count, 2)
		self.assertEqual(extn, "jpg")

	def test_get_web_image_rejects_redirect_to_restricted_address(self):
		redirect_response = MagicMock(is_redirect=True, headers={"Location": "http://127.0.0.1/secret"})

		with patch("requests.get", side_effect=[redirect_response]) as mock_get:
			self.assertRaisesRegex(
				ValidationError,
				"restricted address",
				get_web_image,
				"http://8.8.8.8/initial.jpg",
			)

		mock_get.assert_called_once()


class TestFileOptimization(IntegrationTestCase):
	def test_optimize_file(self):
		with make_test_image_file() as test_file:
			original_size = test_file.file_size
			original_content_hash = test_file.content_hash

			test_file.optimize_file()
			optimized_size = test_file.file_size
			updated_content_hash = test_file.content_hash

			self.assertLess(optimized_size, original_size)
			self.assertNotEqual(original_content_hash, updated_content_hash)

	def test_optimize_svg(self):
		file_path = frappe.get_app_path("frappe", "tests/data/sample_svg.svg")
		with open(file_path, "rb") as f:
			file_content = f.read()
		test_file = frappe.get_doc(
			{"doctype": "File", "file_name": "sample_svg.svg", "content": file_content}
		).insert()
		self.assertRaises(TypeError, test_file.optimize_file)
		test_file.delete()

	def test_optimize_textfile(self):
		test_file = frappe.get_doc(
			{"doctype": "File", "file_name": "sample_text.txt", "content": "Text files cannot be optimized"}
		).insert()
		self.assertRaises(NotImplementedError, test_file.optimize_file)
		test_file.delete()

	def test_optimize_folder(self):
		test_folder = frappe.get_doc("File", "Home/Attachments")
		self.assertRaises(TypeError, test_folder.optimize_file)

	def test_revert_optimized_file_on_rollback(self):
		with make_test_image_file() as test_file:
			image_path = test_file.get_full_path()
			size_before_optimization = os.stat(image_path).st_size
			test_file.optimize_file()
			frappe.db.rollback()
			size_after_rollback = os.stat(image_path).st_size

			self.assertEqual(size_before_optimization, size_after_rollback)

	def test_image_header_guessing(self):
		file_path = frappe.get_app_path("frappe", "tests/data/sample_image_for_optimization.jpg")
		with open(file_path, "rb") as f:
			file_content = f.read()

		self.assertEqual(get_extension("", None, file_content), "jpg")


class TestGuestFileAndAttachments(IntegrationTestCase):
	def setUp(self) -> None:
		frappe.db.delete("File", {"is_folder": 0})
		frappe.get_doc(
			doctype="DocType",
			name="Test For Attachment",
			module="Custom",
			custom=1,
			fields=[
				{"label": "Title", "fieldname": "title", "fieldtype": "Data"},
				{"label": "Attachment", "fieldname": "attachment", "fieldtype": "Attach"},
			],
		).insert(ignore_if_duplicate=True)

	def tearDown(self) -> None:
		frappe.set_user("Administrator")
		frappe.db.rollback()
		frappe.delete_doc("DocType", "Test For Attachment")

	def test_attach_unattached_guest_file(self):
		"""Ensure that unattached files are attached on doc update."""
		f = frappe.new_doc(
			"File",
			file_name="test_private_guest_attachment.txt",
			content="Guest Home",
			is_private=1,
		).insert(ignore_permissions=True)

		d = frappe.new_doc("Test For Attachment")
		d.title = "Test for attachment on update"
		d.attachment = f.file_url
		d.assigned_by = frappe.session.user
		d.save()

		self.assertTrue(
			frappe.db.exists(
				"File",
				{
					"file_name": "test_private_guest_attachment.txt",
					"file_url": f.file_url,
					"attached_to_doctype": "Test For Attachment",
					"attached_to_name": d.name,
					"attached_to_field": "attachment",
				},
			)
		)

	def test_list_private_guest_single_file(self):
		"""Ensure that guests are not able to read private standalone guest files."""
		frappe.set_user("Guest")

		file = frappe.new_doc(
			"File",
			file_name="test_private_guest_single_txt",
			content="Private single File",
			is_private=1,
		).insert(ignore_permissions=True)

		self.assertFalse(file.is_downloadable())

	def test_list_private_guest_attachment(self):
		"""Ensure that guests are not able to read private guest attachments."""
		frappe.set_user("Guest")

		self.attached_to_doctype, self.attached_to_docname = make_test_doc(ignore_permissions=True)

		file = frappe.new_doc(
			"File",
			file_name="test_private_guest_attachment.txt",
			attached_to_doctype=self.attached_to_doctype,
			attached_to_name=self.attached_to_docname,
			content="Private Attachment",
			is_private=1,
		).insert(ignore_permissions=True)

		self.assertFalse(file.is_downloadable())

	def test_private_remains_private_even_if_same_hash(self):
		file_name = "test" + frappe.generate_hash()
		content = file_name.encode()

		doc_pub: File = frappe.new_doc("File")  # type: ignore
		doc_pub.file_url = f"/files/{file_name}.txt"
		doc_pub.content = content
		doc_pub.save()

		doc_pri: File = frappe.new_doc("File")  # type: ignore
		doc_pri.file_url = f"/private/files/{file_name}.txt"
		doc_pri.is_private = False
		doc_pri.content = content
		doc_pri.save()

		doc_pub.reload()
		doc_pri.reload()

		self.assertEqual(doc_pub.is_private, 0)
		self.assertEqual(doc_pri.is_private, 1)

		self.assertEqual(doc_pub.file_url, f"/files/{file_name}.txt")
		self.assertEqual(doc_pri.file_url, f"/private/files/{file_name}.txt")

		self.assertEqual(doc_pub.get_content(), content)
		self.assertEqual(doc_pri.get_content(), content)

		# Deleting a public File should not delete the private File's disk file
		doc_pub.delete()
		self.assertTrue(os.path.exists(doc_pri.get_full_path()))

		# TODO: Migrate existing Files that have a mismatch between `is_private` and `file_url` prefix?
		# self.assertFalse(os.path.exists(doc_pub.get_full_path()))

		self.assertEqual(doc_pri.get_content(), content)
		doc_pri.delete()
		self.assertFalse(os.path.exists(doc_pri.get_full_path()))

	def test_toggling_is_private_does_not_leak_shared_file(self):
		"""Flipping is_private on one File must not silently change another
		File row that happens to share the same content_hash."""
		file_name = "shared" + frappe.generate_hash()
		content = file_name.encode()

		# Row A: private upload
		doc_a: File = frappe.new_doc("File")  # type: ignore
		doc_a.file_name = f"{file_name}.txt"
		doc_a.is_private = 1
		doc_a.content = content
		doc_a.save()

		# Row B: independent private upload of identical bytes.
		doc_b: File = frappe.new_doc("File")  # type: ignore
		doc_b.file_name = f"{file_name}.txt"
		doc_b.is_private = 1
		doc_b.content = content
		doc_b.save()

		doc_a.reload()
		doc_b.reload()

		# Precondition: dedup collapsed both rows onto the same file_url.
		self.assertEqual(doc_a.content_hash, doc_b.content_hash)
		self.assertEqual(doc_a.file_url, doc_b.file_url)
		self.assertTrue(doc_a.file_url.startswith("/private/files/"))

		private_path = doc_a.get_full_path()
		self.assertTrue(os.path.exists(private_path))

		# Flip A to public. B must NOT be affected.
		doc_a.is_private = 0
		doc_a.save()
		doc_a.reload()
		doc_b.reload()

		# A's row: flipped correctly
		self.assertEqual(doc_a.is_private, 0)
		self.assertTrue(doc_a.file_url.startswith("/files/"))

		# B's row: unchanged (the actual regression this test guards)
		self.assertEqual(doc_b.is_private, 1, "B's is_private silently changed to public — data leak")
		self.assertTrue(
			doc_b.file_url.startswith("/private/files/"),
			"B's file_url was rewritten to the public path — data leak",
		)

		self.assertTrue(os.path.exists(doc_a.get_full_path()))
		self.assertTrue(os.path.exists(doc_b.get_full_path()))
		self.assertEqual(doc_a.get_content(), content)
		self.assertEqual(doc_b.get_content(), content)

		# Cleanup: deleting A's row should remove ONLY the public copy;
		# B's private copy must survive because B still references it.
		doc_a_path = doc_a.get_full_path()
		doc_a.delete()
		self.assertFalse(
			os.path.exists(doc_a_path),
			"Public copy not cleaned up after A's deletion",
		)
		self.assertTrue(
			os.path.exists(doc_b.get_full_path()),
			"B's private copy was wrongly deleted when A's row was removed",
		)
		self.assertEqual(doc_b.get_content(), content)

		# Deleting B removes the last reference to the private copy.
		doc_b_path = doc_b.get_full_path()
		doc_b.delete()
		self.assertFalse(
			os.path.exists(doc_b_path),
			"Private copy not cleaned up after B's deletion",
		)


class TestPublicFileRestriction(IntegrationTestCase):
	"""Test public file upload restriction for non-System Managers."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		# Create a test user without System Manager role
		if not frappe.db.exists("User", "test_restricted@example.com"):
			user = frappe.get_doc(
				{
					"doctype": "User",
					"email": "test_restricted@example.com",
					"first_name": "Test Restricted",
					"roles": [{"role": "Website Manager"}],
				}
			)
			user.insert(ignore_permissions=True)

	def tearDown(self):
		frappe.set_user("Administrator")

	@IntegrationTestCase.change_settings(
		"System Settings", {"only_allow_system_managers_to_upload_public_files": 1}
	)
	def test_non_system_manager_cannot_upload_public_file_when_setting_enabled(self):
		"""Non-System Manager should not be able to upload public files when setting is enabled."""
		frappe.set_user("test_restricted@example.com")

		file_doc = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "test_public_restricted.txt",
				"content": "Test content",
				"is_private": 0,
			}
		)

		self.assertRaises(frappe.PermissionError, file_doc.insert)

	@IntegrationTestCase.change_settings(
		"System Settings", {"only_allow_system_managers_to_upload_public_files": 1}
	)
	def test_non_system_manager_can_upload_private_file_when_setting_enabled(self):
		"""Non-System Manager should still be able to upload private files when setting is enabled."""
		frappe.set_user("test_restricted@example.com")

		file_doc = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "test_private_allowed.txt",
				"content": "Test content",
				"is_private": 1,
			}
		)

		file_doc.insert()
		self.assertTrue(file_doc.is_private)

	@IntegrationTestCase.change_settings(
		"System Settings", {"only_allow_system_managers_to_upload_public_files": 1}
	)
	def test_system_manager_can_upload_public_file_when_setting_enabled(self):
		"""System Manager should be able to upload public files even when setting is enabled."""
		frappe.set_user("Administrator")

		file_doc = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "test_public_admin.txt",
				"content": "Test content",
				"is_private": 0,
			}
		)

		file_doc.insert()
		self.assertFalse(file_doc.is_private)

	def test_non_system_manager_can_upload_public_file_when_setting_disabled(self):
		"""Non-System Manager should be able to upload public files when setting is disabled."""
		frappe.set_user("test_restricted@example.com")

		file_doc = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "test_public_allowed.txt",
				"content": "Test content",
				"is_private": 0,
			}
		)

		file_doc.insert()
		self.assertFalse(file_doc.is_private)
