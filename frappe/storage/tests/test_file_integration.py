# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
import hashlib
import io
import os
import zipfile

import frappe
from frappe.client import attach_file
from frappe.storage import backfill, get_driver, put_blob
from frappe.storage.blob import validate_upload
from frappe.storage.gc import MIN_AGE_HOURS
from frappe.storage.memory_driver import fake
from frappe.storage.tests import file_permissions_enforced, storage_v2, unique_bytes, unique_png
from frappe.storage.tests.test_gc_backfill import backdate
from frappe.tests import IntegrationTestCase
from frappe.utils import add_to_date, get_files_path, now_datetime

WEAK_USER = "storage-v2-weak-user@example.com"


def unique_html():
	return unique_bytes(b"<!DOCTYPE html><html><body>")


class TestFileStorageIntegration(IntegrationTestCase):
	def make_file(self, content, file_name="storage-v2.png", is_private=0, **kwargs):
		file = frappe.get_doc(
			doctype="File", file_name=file_name, content=content, is_private=is_private, **kwargs
		).insert()
		self.delete_later("File", file.name)
		if file.get("blob"):
			self.delete_later("File Blob", file.blob)
		return file

	def delete_later(self, doctype, name):
		self.addCleanup(
			frappe.delete_doc, doctype, name, force=1, ignore_permissions=True, ignore_missing=True
		)

	def make_weak_user(self):
		if not frappe.db.exists("User", WEAK_USER):
			frappe.get_doc(
				doctype="User", email=WEAK_USER, first_name="Storage Weak", send_welcome_email=0
			).insert(ignore_permissions=True)

	def make_legacy_row(self, content):
		"""Insert a private v1 File row with bytes on disk and no blob link."""
		filename = f"storage-v2-legacy-{frappe.generate_hash(length=10)}.png"
		path = get_files_path(filename, is_private=1)
		with open(path, "wb") as f:
			f.write(content)
		self.addCleanup(lambda: os.path.exists(path) and os.remove(path))

		doc = frappe.new_doc("File")
		doc.update(
			{"file_name": filename, "file_url": f"/private/files/{filename}", "is_private": 1, "is_folder": 0}
		)
		doc.name = frappe.generate_hash(length=10)
		doc.owner = doc.modified_by = "Administrator"
		doc.creation = doc.modified = now_datetime()
		doc.db_insert()
		self.delete_later("File", doc.name)
		return doc.name, path

	def test_upload_stores_a_blob_and_reads_it_back(self):
		with storage_v2(), fake() as store:
			for is_private, file_name, prefix in (
				(0, "photo.PNG", "/files"),
				(1, "my photo.png", "/private/files"),
			):
				with self.subTest(is_private=is_private):
					content = unique_png()
					file = self.make_file(content, file_name, is_private=is_private)

					blob = frappe.get_doc("File Blob", file.blob)
					self.assertEqual(blob.checksum, hashlib.sha256(content).hexdigest())
					self.assertEqual((blob.status, blob.is_private), ("Ready", is_private))
					self.assertEqual(blob.key, f"{blob.name}/{file_name}")
					# the URL is the same on every driver
					self.assertEqual(file.file_url, f"{prefix}/{blob.name}/{file_name}")
					self.assertTrue(store.exists(blob.key, is_private=bool(is_private)))
					self.assertEqual(frappe.get_doc("File", file.name).get_content(), content)

					# the same bytes again share the blob and the first upload's URL
					second = self.make_file(content, "two.png", is_private=is_private)
					self.assertEqual((second.blob, second.file_url), (blob.name, file.file_url))
					self.assertEqual(second.file_name, "two.png")
					self.assertEqual(frappe.db.count("File Blob", {"checksum": blob.checksum}), 1)

					# GC owns the bytes; a File delete never removes them synchronously
					file.delete()
					self.assertTrue(frappe.db.exists("File Blob", blob.name))
					self.assertTrue(store.exists(blob.key, is_private=bool(is_private)))

			# text that is not utf-8 is decoded with the next candidate encoding
			content = "café ".encode("windows-1250") + frappe.generate_hash(length=16).encode()
			file = self.make_file(content, "latin.txt", is_private=1)
			self.assertEqual(frappe.get_doc("File", file.name).get_content(), content.decode("windows-1250"))

	def test_only_the_local_driver_has_a_disk_path(self):
		with storage_v2():
			for is_private in (0, 1):
				with self.subTest(is_private=is_private):
					content = unique_png()
					file = self.make_file(content, "on disk.png", is_private=is_private)
					key = frappe.db.get_value("File Blob", file.blob, "key")
					self.addCleanup(get_driver("local").delete, key, is_private=bool(is_private))

					# nginx serves the URL path from the site folder
					site_path = frappe.get_site_path() if is_private else frappe.get_site_path("public")
					path = file.get_full_path()
					self.assertEqual(os.path.realpath(path), os.path.realpath(site_path + file.file_url))
					with open(path, "rb") as f:
						self.assertEqual(f.read(), content)
					self.assertTrue(file.exists_on_disk())

		with storage_v2(), fake() as store:
			file = self.make_file(unique_png(), "in-memory.png", is_private=1)
			self.assertRaises(frappe.ValidationError, file.get_full_path)

			store.delete(frappe.db.get_value("File Blob", file.blob, "key"), is_private=True)
			self.assertFalse(file.exists_on_disk())
			self.assertRaises(OSError, file.validate_file_on_disk)

	def test_privacy_change_repoints_the_blob(self):
		with storage_v2(), fake() as store:
			file = self.make_file(unique_png(), "unchanged.png", is_private=1)
			blob_before = file.blob
			# a doc rebuilt from a dict must not repoint its blob without a real change
			file.handle_is_private_changed()
			self.assertEqual(file.blob, blob_before)

			for case in ("flip", "drift"):
				with self.subTest(case=case):
					file = self.make_file(unique_png(), "flip.png", is_private=0)
					old_blob = frappe.get_doc("File Blob", file.blob)
					if case == "flip":
						file.is_private = 1
					else:
						# a subclass flipped is_private without validate(); before_save repoints
						frappe.db.set_value("File", file.name, "is_private", 1, update_modified=False)
						file = frappe.get_doc("File", file.name)
					file.save()
					self.delete_later("File Blob", file.blob)

					self.assertNotEqual(file.blob, old_blob.name)
					new_blob = frappe.get_doc("File Blob", file.blob)
					self.assertEqual(new_blob.is_private, 1)
					self.assertEqual(file.file_url, f"/private/files/{new_blob.name}/flip.png")
					self.assertTrue(store.exists(new_blob.key, is_private=True))
					# the old blob is left for GC
					self.assertTrue(frappe.db.exists("File Blob", old_blob.name))
					self.assertTrue(store.exists(old_blob.key, is_private=False))

	def test_copied_row_adopts_the_blob_behind_its_url(self):
		# amend rebuilds attachments from a bare file_url; the copy relinks the blob
		# and refreshes its modified, so a concurrent GC pass cannot delete it
		cutoff = add_to_date(now_datetime(), hours=-MIN_AGE_HOURS)
		with storage_v2(), fake():
			for is_private, fields in ((1, {"file_name": "amended.png", "is_private": 1}), (0, {})):
				with self.subTest(is_private=is_private):
					original = self.make_file(unique_png(), "amended.png", is_private=is_private)
					backdate(original.blob)

					copy = frappe.get_doc(
						{"doctype": "File", "file_url": original.file_url, **fields}
					).insert()
					self.delete_later("File", copy.name)

					self.assertEqual((copy.blob, copy.file_url), (original.blob, original.file_url))
					self.assertGreater(frappe.db.get_value("File Blob", original.blob, "modified"), cutoff)

	def test_disguised_html_is_rejected(self):
		with storage_v2(), fake():
			png_blob = put_blob(io.BytesIO(unique_png()), filename="ok.png")
			self.delete_later("File Blob", png_blob.name)
			validate_upload(png_blob, "ok.png")

			html_blob = put_blob(io.BytesIO(unique_html()), filename="evil.png")
			self.delete_later("File Blob", html_blob.name)
			self.assertEqual(html_blob.mime_type, "text/html")
			self.assertRaises(frappe.ValidationError, validate_upload, html_blob, "evil.png")
			# the same bytes under an honest extension pass
			validate_upload(html_blob, "page.html")

			# the sniff check also runs on File.insert with content
			self.assertRaises(frappe.ValidationError, self.make_file, unique_html(), "disguised.png")

	def test_thumbnails_and_xlsx_read_from_another_driver(self):
		from PIL import Image

		from frappe.utils.xlsxutils import make_xlsx, read_xlsx_file_from_attached_file

		buffer = io.BytesIO()
		Image.new("RGB", (600, 400), "red").save(buffer, format="PNG")
		rows = [["Account", "Parent"], [frappe.generate_hash(length=8), "Assets"]]
		with storage_v2(), fake():
			image = self.make_file(buffer.getvalue(), "remote photo.png")
			thumbnail_url = image.make_thumbnail()

			sheet = self.make_file(make_xlsx(rows, "Sheet1").getvalue(), "accounts.xlsx")
			self.assertEqual(read_xlsx_file_from_attached_file(file_url=sheet.file_url), rows)

		self.assertEqual(thumbnail_url, f"/files/{image.blob}/remote photo_small.png")
		path = frappe.get_site_path("public", thumbnail_url.lstrip("/"))
		self.addCleanup(os.rmdir, os.path.dirname(path))
		self.addCleanup(os.remove, path)
		with Image.open(path) as thumbnail:
			self.assertEqual(thumbnail.size, (300, 200))
		self.assertEqual(frappe.db.get_value("File", image.name, "thumbnail_url"), thumbnail_url)

	def test_unzip_extracts_a_zip_from_any_storage(self):
		# flag off: a v1 zip on local disk takes the same read path
		for enabled in (True, False):
			# unique names: v1 renames a member whose path already holds other bytes
			suffix = frappe.generate_hash(length=8)
			members = {f"a-{suffix}.txt": b"alpha " + suffix.encode(), f"b-{suffix}.txt": b"beta"}
			archive = io.BytesIO()
			with zipfile.ZipFile(archive, "w") as z:
				for name, data in members.items():
					z.writestr(name, data)

			with self.subTest(storage_v2=enabled), storage_v2(enabled), fake():
				zip_file = self.make_file(archive.getvalue(), "bundle.zip", is_private=1)
				self.assertEqual(bool(zip_file.get("blob")), enabled)
				children = zip_file.unzip()
				for child in children:
					self.delete_later("File", child.name)

				self.assertEqual(
					{child.file_name: frappe.get_doc("File", child.name).get_content() for child in children},
					{name: data.decode() for name, data in members.items()},
				)
				self.assertFalse(frappe.db.exists("File", zip_file.name))

	def test_legacy_upload_apis_store_blobs(self):
		from frappe.utils.file_manager import save_file

		self.make_weak_user()
		content = "storage v2 attach " + frappe.generate_hash(length=32)
		with storage_v2(), fake() as store:
			file = save_file(
				f"fm-{frappe.generate_hash(length=8)}.png", unique_png(), None, None, is_private=1
			)
			self.delete_later("File", file.name)
			self.delete_later("File Blob", file.blob)
			key = frappe.db.get_value("File Blob", file.blob, "key")
			self.assertTrue(store.exists(key, is_private=True))

			attach = {"filedata": content, "doctype": "Language", "docname": "en", "is_private": 1}
			with self.set_user(WEAK_USER):
				# read on Language is granted to All; write is not
				self.assertRaises(frappe.PermissionError, attach_file, filename="denied.txt", **attach)

			file = attach_file(filename="allowed.txt", **attach)
			self.delete_later("File", file.name)
			self.delete_later("File Blob", file.blob)
			self.assertTrue(file.blob)

	def test_new_row_needs_permission_on_the_private_blob_it_links(self):
		# knowing a private blob URL or name must not grant access through a new row
		self.make_weak_user()
		with storage_v2(), fake(), file_permissions_enforced():
			original = self.make_file(unique_png(), "secret.png", is_private=1)

			def copy(file_url):
				return frappe.get_doc(
					{"doctype": "File", "file_url": file_url, "file_name": "stolen.png", "is_private": 1}
				)

			# the stored URL, and the same blob under another download name
			urls = (original.file_url, f"/private/files/{original.blob}/renamed.png")
			with self.set_user(WEAK_USER):
				for url in urls:
					with self.subTest(url=url):
						self.assertRaises(frappe.PermissionError, copy(url).insert)
			self.assertFalse(frappe.db.exists("File", {"blob": original.blob, "file_name": "stolen.png"}))

			# a trusted caller may still relink it
			with self.set_user(WEAK_USER):
				trusted = copy(urls[1]).insert(ignore_permissions=True)
			self.delete_later("File", trusted.name)
			self.assertEqual(trusted.blob, original.blob)

		# a blob link is checked before ingestion reads the linked bytes, under either version
		for enabled in (True, False):
			with self.subTest(storage_v2=enabled), storage_v2(enabled), fake(), file_permissions_enforced():
				with storage_v2():
					secret = self.make_file(unique_png(), "secret.png", is_private=1)
				rows = (
					({"file_url": "/private/files/stolen.png"}, frappe.PermissionError),
					({}, frappe.PermissionError),
					({"file_url": "https://example.com/a.txt"}, frappe.ValidationError),
				)
				with self.set_user("test@example.com"):
					for fields, error in rows:
						row = frappe.get_doc(
							doctype="File", file_name="stolen.png", is_private=1, blob=secret.blob, **fields
						)
						self.assertRaises(error, row.insert)
				self.assertEqual(frappe.db.count("File", {"blob": secret.blob}), 1)

	def test_existing_row_needs_permission_on_the_private_blob_it_links(self):
		with storage_v2(), fake(), file_permissions_enforced():
			secret = self.make_file(unique_png(), "secret.png", is_private=1)
			with self.set_user("test@example.com"):
				own = self.make_file(unique_png(), "own.png", is_private=0)
				own.blob = secret.blob
				own.is_private = 1
				self.assertRaises(frappe.PermissionError, own.save)

				# optimize_file reads the blob a client-supplied doc names
				own.reload()
				own.blob = secret.blob
				self.assertRaises(frappe.PermissionError, own.optimize_file)

				# the user's own privacy flip writes a new blob, which is trusted
				own.reload()
				own.is_private = 1
				own.save()
				self.delete_later("File Blob", own.blob)
				self.assertTrue(own.file_url.startswith(f"/private/files/{own.blob}/"))
				own_blob = own.blob

				own.blob = secret.blob
				self.assertRaises(frappe.PermissionError, own.save)
			self.assertEqual(frappe.db.get_value("File", own.name, "blob"), own_blob)
			self.assertEqual(frappe.db.count("File", {"blob": secret.blob}), 1)

	def test_optimize_repoints_the_attach_field(self):
		from PIL import Image

		buffer = io.BytesIO()
		Image.effect_noise((1200, 900), 100).convert("RGB").save(buffer, format="JPEG", quality=100)
		with storage_v2(), fake():
			user = frappe.get_doc("User", "test@example.com")
			file = self.make_file(
				buffer.getvalue(),
				"optimize.jpg",
				attached_to_doctype="User",
				attached_to_name=user.name,
				attached_to_field="user_image",
			)
			self.addCleanup(frappe.db.set_value, "User", user.name, "user_image", user.user_image)
			frappe.db.set_value("User", user.name, "user_image", file.file_url)
			old_blob = file.blob

			file.optimize_file()
			self.delete_later("File Blob", file.blob)

			self.assertNotEqual(file.blob, old_blob)
			self.assertEqual(frappe.db.get_value("User", user.name, "user_image"), file.file_url)

	def test_blob_row_rejects_a_foreign_file_url(self):
		with storage_v2(), fake():
			file = self.make_file(unique_png(), "traversal.png", is_private=1)
			cases = (
				(f"/files/../../private/files/{file.blob}/traversal.png", file.validate_file_path),
				("/somewhere/else.png", file.validate_file_url),
			)
			for file_url, validate in cases:
				with self.subTest(file_url=file_url):
					file.file_url = file_url
					self.assertRaises(frappe.ValidationError, validate)

	def test_legacy_row_through_backfill_and_relocation(self):
		content = unique_png()
		name, path = self.make_legacy_row(content)
		file_url = frappe.db.get_value("File", name, "file_url")
		with storage_v2(), fake() as store, file_permissions_enforced():
			# blob still NULL: every seam delegates to FileV1 and reads the disk path
			doc = frappe.get_doc("File", name)
			self.assertFalse(doc.get("blob"))
			self.assertIsNone(doc.validate_file_path())
			self.assertIsNone(doc.validate_file_url())
			self.assertIsNone(doc.validate_file_on_disk())
			self.assertTrue(doc.exists_on_disk())
			self.assertEqual(doc.get_full_path(), path)
			self.assertEqual(doc.get_content(), content)

			# a backfilled row keeps its legacy URL and still saves
			backfill.run(filters=[["name", "=", name]])
			linked = frappe.get_doc("File", name)
			blob = linked.blob
			self.delete_later("File Blob", blob)
			self.assertTrue(blob)
			self.assertEqual(linked.file_url, file_url)
			linked.save()
			self.assertEqual(linked.file_url, file_url)

			# relocation: bytes move to another driver, the v1 file goes
			store.write(f"{blob}/moved.png", io.BytesIO(content), is_private=True)
			frappe.db.set_value("File Blob", blob, {"driver": store.name, "key": f"{blob}/moved.png"})
			os.remove(path)

			# amend rebuilds attachments from the v1 file_url
			def copy():
				return frappe.get_doc(
					{"doctype": "File", "file_url": file_url, "file_name": "copy.png", "is_private": 1}
				)

			with self.set_user("test@example.com"):
				self.assertRaises(frappe.PermissionError, copy().insert)

			for enabled in (True, False):
				with self.subTest(storage_v2=enabled), storage_v2(enabled):
					copied = copy().insert()
					self.delete_later("File", copied.name)
					self.assertEqual((copied.blob, copied.file_url), (blob, file_url))
					self.assertEqual(frappe.get_doc("File", copied.name).get_content(), content)

	def test_flag_off_is_legacy(self):
		content = unique_png()
		with storage_v2(False):
			file = self.make_file(content, "legacy.png", is_private=0)

			self.assertFalse(file.get("blob"))
			self.assertEqual(file.file_url, f"/files/{file.file_name}")
			self.assertFalse(frappe.db.exists("File Blob", {"checksum": hashlib.sha256(content).hexdigest()}))

	def test_remote_file_stores_no_bytes(self):
		with storage_v2(), fake() as store:
			file = frappe.get_doc(
				doctype="File", file_name="remote.png", file_url="https://example.com/remote.png"
			).insert()
			self.delete_later("File", file.name)

			self.assertFalse(file.get("blob"))
			self.assertEqual(file.file_url, "https://example.com/remote.png")
			self.assertFalse(store.blobs)
			# every byte-facing seam is a no-op for a remote reference
			self.assertIsNone(file.validate_file_path())
			self.assertIsNone(file.validate_file_url())
			self.assertIsNone(file.handle_is_private_changed())
			self.assertTrue(file.validate_file_on_disk())

	# --- storage seams and controller resolution ---

	def test_base_file_class_has_no_storage_implementation(self):
		from frappe.core.doctype.file.file import File as BaseFile

		doc = BaseFile({"doctype": "File", "file_name": "unresolved.txt"})
		seams = (
			"_ingest_new_content _read_content _open_stored_bytes _store_content get_full_path exists_on_disk"
			" validate_file_path validate_file_url validate_file_on_disk handle_is_private_changed"
			" _delete_file_on_disk"
		).split()
		for seam in seams:
			with self.subTest(seam=seam):
				with self.assertRaises(NotImplementedError) as caught:
					getattr(doc, seam)()
				self.assertIn("resolve_controller", str(caught.exception))

		# the one seam with a real default: keeping nothing is valid
		self.assertIsNone(doc._stash_original_content())

	def test_resolve_controller_splices_app_override(self):
		"""An app subclass of File keeps its methods on top of the storage class, and pickles."""
		import pickle

		from frappe.core.doctype.file.file import File as BaseFile
		from frappe.core.doctype.file.file import _ResolvedFileMeta
		from frappe.core.doctype.file.file_v1 import FileV1
		from frappe.core.doctype.file.file_v2 import FileV2
		from frappe.model.base_document import get_controller

		class AppFile(BaseFile):
			pass

		for enabled, storage_class in ((True, FileV2), (False, FileV1)):
			with self.subTest(storage_v2=enabled), storage_v2(enabled):
				self.assertIs(BaseFile.resolve_controller(), storage_class)
				# a class that already is a storage class is returned untouched
				self.assertIs(storage_class.resolve_controller(), storage_class)

				spliced = AppFile.resolve_controller()
				self.assertIsInstance(spliced, _ResolvedFileMeta)
				self.assertEqual(spliced.__name__, "AppFile")
				self.assertEqual(spliced.__mro__[:4], (spliced, AppFile, storage_class, BaseFile))

				# a runtime-spliced class pickles as the site's File controller
				self.assertIs(pickle.loads(pickle.dumps(spliced)), get_controller("File"))
				restored = pickle.loads(
					pickle.dumps(spliced({"doctype": "File", "file_name": "picklable.txt"}))
				)
				self.assertEqual(restored.file_name, "picklable.txt")
				self.assertIs(type(restored), get_controller("File"))
