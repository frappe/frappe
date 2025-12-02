# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import base64
import os
import shutil
import tempfile
from contextlib import contextmanager
from typing import TYPE_CHECKING

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
from frappe.core.doctype.file.utils import get_corrupted_image_msg, get_extension
from frappe.desk.form.utils import add_comment
from frappe.exceptions import ValidationError
from frappe.tests import IntegrationTestCase
from frappe.utils import cint, get_files_path, set_request

if TYPE_CHECKING:
	from frappe.core.doctype.file.file import File

test_content1 = "Hello"
test_content2 = "Hello World"


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
			frappe.delete_doc("File", f)

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

		self.assertEqual(file1.is_private, file2.is_private, 1)
		self.assertEqual(file1.file_url, file2.file_url)
		self.assertTrue(os.path.exists(file1.get_full_path()))

		file1.is_private = 0
		file1.save()

		file2 = frappe.get_doc("File", file2.name)

		self.assertEqual(file1.is_private, file2.is_private, 0)
		self.assertEqual(file1.file_url, file2.file_url)
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

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		frappe.get_doc(
			doctype="DocType",
			name=cls.test_doctype,
			module="Custom",
			custom=1,
			fields=[
				{"label": "Title", "fieldname": "title", "fieldtype": "Data"},
				{"label": "Attachment", "fieldname": "attachment", "fieldtype": "Attach"},
			],
		).insert(ignore_if_duplicate=True)

	@classmethod
	def tearDownClass(cls):
		frappe.db.rollback()
		frappe.delete_doc("DocType", cls.test_doctype)

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


class TestPublicFileUploadPermissions(IntegrationTestCase):
	"""Test permission-based restrictions for public file uploads"""

	def setUp(self):
		frappe.set_user("Administrator")
		# Create test role
		if not frappe.db.exists("Role", "Test File Uploader"):
			frappe.get_doc({"doctype": "Role", "role_name": "Test File Uploader"}).insert()
		# Create test user
		if not frappe.db.exists("User", "test_file_uploader@example.com"):
			user = frappe.get_doc(
				{
					"doctype": "User",
					"email": "test_file_uploader@example.com",
					"first_name": "Test",
					"send_welcome_email": 0,
				}
			)
			user.insert()
			user.add_roles("Test File Uploader")
		# Create Permission Type for upload_public_files on File doctype if it doesn't exist
		if not frappe.db.exists("Permission Type", {"perm_type": "upload_public_files", "doc_type": "File"}):
			frappe.get_doc(
				{
					"doctype": "Permission Type",
					"perm_type": "upload_public_files",
					"doc_type": "File",
				}
			).insert(ignore_permissions=True)

	def tearDown(self):
		frappe.set_user("Administrator")
		# Clean up test files
		test_files = frappe.get_all("File", filters={"owner": "test_file_uploader@example.com"}, pluck="name")
		for file_name in test_files:
			try:
				frappe.delete_doc("File", file_name, force=1)
			except Exception:
				pass

	def test_administrator_can_upload_public_files(self):
		"""Administrator should be able to upload public files without restrictions"""
		frappe.set_user("Administrator")
		file_doc = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "test_public_file.txt",
				"content": "test content",
				"is_private": 0,
			}
		)
		file_doc.save()
		self.assertEqual(file_doc.is_private, 0)
		file_doc.delete()

	def test_user_with_permission_can_upload_public_files(self):
		"""User with upload_public_files permission should be able to upload public files"""
		from frappe.permissions import add_permission, update_permission_property

		# Grant upload_public_files permission to Test File Uploader role
		add_permission("File", "Test File Uploader", 0)
		update_permission_property("File", "Test File Uploader", 0, "read", 1)
		update_permission_property("File", "Test File Uploader", 0, "write", 1)

		# Set upload_public_files directly using SQL since update_permission_property might not handle it
		custom_docperm_name = frappe.db.get_value(
			"Custom DocPerm",
			{"parent": "File", "role": "Test File Uploader", "permlevel": 0},
		)
		if custom_docperm_name:
			frappe.db.set_value("Custom DocPerm", custom_docperm_name, "upload_public_files", 1)

		# Commit changes and clear all caches
		frappe.db.commit()

		# Verify permission was set
		custom_docperm_value = frappe.db.get_value(
			"Custom DocPerm",
			{"parent": "File", "role": "Test File Uploader", "permlevel": 0},
			"upload_public_files",
		)
		self.assertEqual(
			int(custom_docperm_value or 0), 1, "upload_public_files permission should be set to 1"
		)

		# Clear all caches and reload
		frappe.clear_cache()
		frappe.clear_cache(doctype="File")
		del frappe.local.role_permissions
		frappe.reload_doctype("File")

		frappe.set_user("test_file_uploader@example.com")

		# Verify permission check works
		self.assertTrue(
			frappe.has_permission("File", "upload_public_files", user="test_file_uploader@example.com"),
			"User should have upload_public_files permission",
		)

		file_doc = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "test_public_file.txt",
				"content": "test content",
				"is_private": 0,
			}
		)
		file_doc.save()
		self.assertEqual(file_doc.is_private, 0)
		file_doc.delete()

	def test_user_without_permission_cannot_upload_public_files(self):
		"""User without upload_public_files permission should not be able to upload public files"""
		from frappe.permissions import add_permission, update_permission_property

		# Grant read/write but NOT upload_public_files permission
		add_permission("File", "Test File Uploader", 0)
		update_permission_property("File", "Test File Uploader", 0, "read", 1)
		update_permission_property("File", "Test File Uploader", 0, "write", 1)

		# Set upload_public_files to 0 directly
		custom_docperm_name = frappe.db.get_value(
			"Custom DocPerm",
			{"parent": "File", "role": "Test File Uploader", "permlevel": 0},
		)
		if custom_docperm_name:
			frappe.db.set_value("Custom DocPerm", custom_docperm_name, "upload_public_files", 0)

		# Commit changes and clear all caches
		frappe.db.commit()
		frappe.clear_cache()
		frappe.reload_doctype("File")
		frappe.set_user("test_file_uploader@example.com")
		file_doc = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "test_public_file.txt",
				"content": "test content",
				"is_private": 0,
			}
		)
		with self.assertRaises(frappe.PermissionError):
			file_doc.save()

	def test_user_without_permission_can_upload_private_files(self):
		"""User without upload_public_files permission should still be able to upload private files"""
		from frappe.permissions import add_permission, update_permission_property

		# Grant read/write but NOT upload_public_files permission
		add_permission("File", "Test File Uploader", 0)
		update_permission_property("File", "Test File Uploader", 0, "read", 1)
		update_permission_property("File", "Test File Uploader", 0, "write", 1)

		# Set upload_public_files to 0 directly
		custom_docperm_name = frappe.db.get_value(
			"Custom DocPerm",
			{"parent": "File", "role": "Test File Uploader", "permlevel": 0},
		)
		if custom_docperm_name:
			frappe.db.set_value("Custom DocPerm", custom_docperm_name, "upload_public_files", 0)

		# Commit changes and clear all caches
		frappe.db.commit()
		frappe.clear_cache()
		frappe.reload_doctype("File")
		frappe.set_user("test_file_uploader@example.com")
		file_doc = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "test_private_file.txt",
				"content": "test content",
				"is_private": 1,
			}
		)
		file_doc.save()
		self.assertEqual(file_doc.is_private, 1)
		file_doc.delete()

	def test_user_cannot_toggle_private_to_public_without_permission(self):
		"""User without permission should not be able to toggle file from private to public"""
		from frappe.permissions import add_permission, update_permission_property

		# Grant read/write but NOT upload_public_files permission
		add_permission("File", "Test File Uploader", 0)
		update_permission_property("File", "Test File Uploader", 0, "read", 1)
		update_permission_property("File", "Test File Uploader", 0, "write", 1)

		# Set upload_public_files to 0 directly
		custom_docperm_name = frappe.db.get_value(
			"Custom DocPerm",
			{"parent": "File", "role": "Test File Uploader", "permlevel": 0},
		)
		if custom_docperm_name:
			frappe.db.set_value("Custom DocPerm", custom_docperm_name, "upload_public_files", 0)

		# Commit changes and clear all caches
		frappe.db.commit()
		frappe.clear_cache()
		frappe.reload_doctype("File")
		frappe.set_user("Administrator")
		# Create a private file as Administrator
		file_doc = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "test_private_file.txt",
				"content": "test content",
				"is_private": 1,
			}
		)
		file_doc.save()
		file_name = file_doc.name

		# Try to toggle to public as test user
		frappe.set_user("test_file_uploader@example.com")
		file_doc = frappe.get_doc("File", file_name)
		file_doc.is_private = 0
		with self.assertRaises(frappe.PermissionError):
			file_doc.save()

		# Cleanup
		frappe.set_user("Administrator")
		frappe.delete_doc("File", file_name, force=1)

	def test_permission_check_based_on_attached_doctype(self):
		"""Permission check should be based on attached_to_doctype, not just File doctype"""
		from frappe.permissions import add_permission, update_permission_property

		# Create a test doctype
		test_doctype = frappe.get_doc(
			{
				"doctype": "DocType",
				"name": "Test File Attachment",
				"module": "Core",
				"custom": 1,
				"fields": [{"fieldname": "test_field", "fieldtype": "Data", "label": "Test Field"}],
			}
		)
		if not frappe.db.exists("DocType", "Test File Attachment"):
			test_doctype.insert()

		# Note: upload_public_files is a standard right (in std_rights), so it doesn't need a Permission Type
		# It's available for all doctypes by default

		# Grant upload_public_files permission on Test File Attachment but NOT on File
		add_permission("Test File Attachment", "Test File Uploader", 0)
		update_permission_property("Test File Attachment", "Test File Uploader", 0, "read", 1)
		update_permission_property("Test File Attachment", "Test File Uploader", 0, "write", 1)

		# Set upload_public_files directly
		custom_docperm_name = frappe.db.get_value(
			"Custom DocPerm",
			{"parent": "Test File Attachment", "role": "Test File Uploader", "permlevel": 0},
		)
		if custom_docperm_name:
			frappe.db.set_value("Custom DocPerm", custom_docperm_name, "upload_public_files", 1)

		add_permission("File", "Test File Uploader", 0)
		update_permission_property("File", "Test File Uploader", 0, "read", 1)
		update_permission_property("File", "Test File Uploader", 0, "write", 1)

		# Set upload_public_files to 0 directly
		custom_docperm_name = frappe.db.get_value(
			"Custom DocPerm",
			{"parent": "File", "role": "Test File Uploader", "permlevel": 0},
		)
		if custom_docperm_name:
			frappe.db.set_value("Custom DocPerm", custom_docperm_name, "upload_public_files", 0)

		# Commit changes and clear all caches
		frappe.db.commit()
		frappe.clear_cache()
		frappe.reload_doctype("File")
		frappe.reload_doctype("Test File Attachment")

		# Create a test document
		test_doc = frappe.get_doc({"doctype": "Test File Attachment", "test_field": "test"})
		test_doc.insert()

		frappe.set_user("test_file_uploader@example.com")
		# Should be able to upload public file when attached to Test File Attachment
		file_doc = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "test_attached_file.txt",
				"content": "test content",
				"is_private": 0,
				"attached_to_doctype": "Test File Attachment",
				"attached_to_name": test_doc.name,
			}
		)
		file_doc.save()
		self.assertEqual(file_doc.is_private, 0)

		# Cleanup
		frappe.set_user("Administrator")
		file_doc.delete()
		test_doc.delete()
		frappe.delete_doc("DocType", "Test File Attachment", force=1)
