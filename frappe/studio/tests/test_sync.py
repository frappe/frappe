import os
import shutil

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import add_to_date, now_datetime

from studio.studio.doctype.studio_app.test_studio_app import make_studio_app, make_studio_page
from studio.studio.doctype.studio_page.test_studio_page import (
	PAGE_SCRIPT,
	component_ref,
	exports_in_tempdir,
	make_component,
)
from studio.sync import before_app_uninstall, remove_orphaned_apps_and_pages, sync_studio_apps


def make_standard_app(frappe_app="frappe"):
	return make_studio_app(
		app_name="sync-" + frappe.generate_hash(length=8), is_standard=1, frappe_app=frappe_app
	)


def delete_rows(app):
	"""Drop the app and its pages from the DB without touching their exported files."""
	frappe.db.delete("Studio Page", {"studio_app": app.name})
	frappe.db.delete("Studio App", {"name": app.name})


class TestSync(IntegrationTestCase):
	def test_sync(self):
		with exports_in_tempdir():
			app = make_standard_app()
			page = make_studio_page(app.name, page_title="Board", route="/board")
			delete_rows(app)

			sync_studio_apps("frappe")

			self.assertEqual(frappe.db.get_value("Studio App", app.name, "app_title"), app.app_title)
			synced = frappe.get_doc("Studio Page", page.name)
			self.assertEqual(synced.route, "/board")
			self.assertTrue(synced.is_standard)

	def test_sync_updates(self):
		with exports_in_tempdir():
			app = make_standard_app()
			page = make_studio_page(app.name, page_title="Board", route="/board")
			path = page.get_folder_path(with_filename=True)
			data = frappe.parse_json(frappe.read_file(path))
			data.update({"route": "/kanban", "modified": str(add_to_date(now_datetime(), minutes=1))})
			with open(path, "w") as f:
				f.write(frappe.as_json(data))

			sync_studio_apps("frappe")

			self.assertEqual(frappe.db.get_value("Studio Page", page.name, "route"), "/kanban")

	def test_does_not_sync_script_to_db(self):
		with exports_in_tempdir():
			app = make_studio_app(app_name="sync-" + frappe.generate_hash(length=8))
			page = make_studio_page(app.name, script=PAGE_SCRIPT)
			app.reload()
			app.enable_app_export("frappe")
			delete_rows(app)

			sync_studio_apps("frappe")

			synced = frappe.get_doc("Studio Page", page.name)
			self.assertFalse(synced.script)
			self.assertEqual(synced.get_script_source(), PAGE_SCRIPT)

	def test_sync_exported_components(self):
		with exports_in_tempdir():
			app = make_standard_app()
			component = make_component("Card")
			make_studio_page(app.name, blocks=frappe.as_json([component_ref(component)]))
			frappe.db.delete("Studio Component", {"name": component.name})

			sync_studio_apps("frappe")

			self.assertEqual(
				frappe.db.get_value("Studio Component", component.name, "component_name"), "Card"
			)

	def test_before_app_uninstall_deletes_its_apps(self):
		with exports_in_tempdir():
			app = make_standard_app()
			page = make_studio_page(app.name)

			before_app_uninstall("frappe")

			self.assertFalse(frappe.db.exists("Studio App", app.name))
			self.assertFalse(frappe.db.exists("Studio Page", page.name))

	def test_remove_orphaned_apps_and_pages(self):
		with exports_in_tempdir():
			app = make_standard_app(frappe_app="studio")
			kept = make_studio_page(app.name, page_title="Kept", route="/kept")
			gone = make_studio_page(app.name, page_title="Gone", route="/gone")

			remove_orphaned_apps_and_pages()
			self.assertTrue(frappe.db.exists("Studio Page", kept.name))
			self.assertTrue(frappe.db.exists("Studio Page", gone.name))

			shutil.rmtree(gone.get_folder_path())
			remove_orphaned_apps_and_pages()
			self.assertFalse(frappe.db.exists("Studio Page", gone.name))
			self.assertTrue(frappe.db.exists("Studio Page", kept.name))

			shutil.rmtree(app.get_folder_path())
			remove_orphaned_apps_and_pages()
			self.assertFalse(frappe.db.exists("Studio App", app.name))
			self.assertFalse(frappe.db.exists("Studio Page", kept.name))

	def test_remove_orphans_skips_custom_apps(self):
		with exports_in_tempdir():
			app = make_studio_app(app_name="custom-" + frappe.generate_hash(length=8))
			page = make_studio_page(app.name)
			remove_orphaned_apps_and_pages()
			self.assertTrue(frappe.db.exists("Studio App", app.name))
			self.assertTrue(frappe.db.exists("Studio Page", page.name))
