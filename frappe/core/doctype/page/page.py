# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json
import os
import shutil

import frappe
from frappe import _, conf, get_module_path, safe_decode
from frappe.core.doctype.custom_role.custom_role import get_custom_allowed_roles
from frappe.desk.form.meta import get_code_files_via_hooks, get_js
from frappe.desk.utils import validate_route_conflict
from frappe.model.document import Document
from frappe.model.utils import render_include


class Page(Document):
	_DOCTYPE_NAME = "Page"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.core.doctype.has_role.has_role import HasRole
		from frappe.types import DF

		icon: DF.Data | None
		module: DF.Link
		page_name: DF.Data
		restrict_to_domain: DF.Link | None
		roles: DF.Table[HasRole]
		standard: DF.Literal["Yes", "No"]
		system_page: DF.Check
		title: DF.Data | None
		type: DF.Literal["", "Frappe UI"]
	# end: auto-generated types

	def autoname(self):
		"""
		Creates a url friendly name for this page.
		Will restrict the name to 30 characters, if there exists a similar name,
		it will add name-1, name-2 etc.
		"""
		from frappe.utils import cint

		if (self.name and self.name.startswith("New Page")) or not self.name:
			self.name = self.page_name.lower().replace('"', "").replace("'", "").replace(" ", "-")[:20]
			if frappe.db.exists("Page", self.name):
				cnt = frappe.db.sql(
					"""select name from tabPage
					where name like "{}-%" order by name desc limit 1""".format(self.name)
				)
				if cnt:
					cnt = cint(cnt[0][0].split("-")[-1]) + 1
				else:
					cnt = 1
				self.name += "-" + str(cnt)

	def validate(self):
		validate_route_conflict(self.doctype, self.name)

		if self.is_new() and not getattr(conf, "developer_mode", 0):
			frappe.throw(_("Not in Developer Mode"))

		# setting ignore_permissions via update_setup_wizard_access (setup_wizard.py)
		if frappe.session.user != "Administrator" and not self.flags.ignore_permissions:
			frappe.throw(_("Only Administrator can edit"))

		self.validate_island()

	def validate_island(self):
		"""The two things a Frappe UI page needs before it can be built at all."""
		if self.type != "Frappe UI":
			return

		if self.standard != "Yes":
			frappe.throw(
				_("A Frappe UI page has to be Standard. Its Vue source lives in the app's page folder.")
			)

		# The page script stops running the moment the type changes, so a page
		# switched over would quietly lose whatever that file did.
		page_name = frappe.scrub(self.name)
		if not self.is_new() and os.path.exists(os.path.join(self.get_folder_path(), f"{page_name}.js")):
			frappe.msgprint(
				_("{0}.js will no longer run. A Frappe UI page is drawn by its island.").format(
					f"{page_name}.js"
				),
				indicator="orange",
			)

	def get_folder_path(self) -> str:
		"""The folder holding this page's files: `<module>/page/<page_name>/`."""
		return os.path.join(get_module_path(self.module), "page", frappe.scrub(self.name))

	def get_permission_log_options(self, event=None):
		return {"fields": ["roles"]}

	# export
	def on_update(self):
		"""
		Writes the .json for this page and if write_content is checked,
		it will write out a .html file
		"""
		if self.flags.do_not_update_json:
			return

		from frappe.core.doctype.doctype.doctype import make_module_and_roles

		make_module_and_roles(self, "roles")

		from frappe.modules.utils import export_module_json

		path = export_module_json(self, self.standard == "Yes", self.module)

		if not path:
			return

		if self.type == "Frappe UI":
			self.write_island_boilerplate(path)
		elif not os.path.exists(path + ".js"):
			# js
			with open(path + ".js", "w") as f:
				f.write(
					f"""frappe.pages['{self.name}'].on_page_load = function(wrapper) {{
	var page = frappe.ui.make_app_page({{
		parent: wrapper,
		title: '{self.title}',
		single_column: true
	}});
}}"""
				)

	def write_island_boilerplate(self, path: str):
		"""The starter a Frappe UI page begins life with.

		Two files beside the page's json: the entry desk loads, and the component
		it renders. Neither is overwritten, so a page that already has them keeps
		what its developer wrote.
		"""
		title = self.title or self.name

		# Both files go where `export_module_json` just wrote the page's own json,
		# which is where the page script below is written too.
		if not os.path.exists(path + ".island.js"):
			with open(path + ".island.js", "w") as f:  # nosemgrep
				f.write(ISLAND_ENTRY.replace("__VUE_FILE__", os.path.basename(path) + ".vue"))

		if not os.path.exists(path + ".vue"):
			with open(path + ".vue", "w") as f:  # nosemgrep
				f.write(ISLAND_COMPONENT.replace("__TITLE__", as_js_string(title)))

	def as_dict(self, **kwargs):
		d = super().as_dict(**kwargs)
		for key in ("script", "style", "content"):
			d[key] = self.get(key)

		# Like the three above, this is loaded rather than stored, so it is here
		# and not a field. `load_assets` derives it, and only for a Frappe UI
		# page, so an export carries no key at all.
		if self.get("island"):
			d["island"] = self.island

		return d

	def get_island_name(self) -> str | None:
		"""The island that draws this page. `None` if its app is not installed."""
		from frappe.utils.island import page_island_name

		app = frappe.local.module_app.get(frappe.scrub(self.module))
		return page_island_name(app, self.name) if app else None

	def clear_cache(self):
		from frappe.desk.doctype.sidebar.sidebar import clear_computed_base_for

		# a module with no `Sidebar` has its sidebar computed from pages like this one
		clear_computed_base_for(self)
		return super().clear_cache()

	def on_trash(self):
		if not frappe.conf.developer_mode and not frappe.flags.in_migrate:
			frappe.throw(_("Deletion of this document is only permitted in developer mode."))

		delete_custom_role("page", self.name)
		if frappe.conf.developer_mode:
			frappe.db.after_commit(self.delete_folder_with_contents)

	def delete_folder_with_contents(self):
		try:
			module_path = get_module_path(self.module)
			dir_path = os.path.join(module_path, "page", frappe.scrub(self.name))

			if os.path.exists(dir_path):
				shutil.rmtree(dir_path, ignore_errors=True)
		except frappe.DoesNotExistError as e:
			frappe.log(e)

	def is_permitted(self):
		"""Return True if `Has Role` is not set or the user is allowed."""
		from frappe.utils import has_common

		allowed = [d.role for d in frappe.get_all("Has Role", fields=["role"], filters={"parent": self.name})]

		custom_roles = get_custom_allowed_roles("page", self.name)
		allowed.extend(custom_roles)

		if not allowed:
			return True

		roles = frappe.get_roles()

		if has_common(roles, allowed):
			return True

	def load_assets(self):
		import os

		from frappe.bundler import html_to_js_template
		from frappe.modules import get_module_path, scrub

		self.script = ""

		# An island draws the whole page, so none of the desk assets below are
		# read. The page script in particular is never shipped to the client,
		# where it would be eval'd as a classic script.
		#
		# Desk mounts by name, and only this side knows which app the page's
		# module belongs to.
		if self.type == "Frappe UI":
			self.island = self.get_island_name()
			return

		page_name = scrub(self.name)

		path = os.path.join(get_module_path(self.module), "page", page_name)

		# script
		fpath = os.path.join(path, page_name + ".js")
		if os.path.exists(fpath):
			with open(fpath) as f:
				self.script = render_include(f.read())
				self.script += f"\n\n//# sourceURL={page_name}.js"

		# css
		fpath = os.path.join(path, page_name + ".css")
		if os.path.exists(fpath):
			with open(fpath) as f:
				self.style = safe_decode(f.read())

		# html as js template
		for fname in os.listdir(path):
			if fname.endswith(".html"):
				with open(os.path.join(path, fname)) as f:
					template = f.read()
					if "<!-- jinja -->" in template:
						context = frappe._dict({})
						try:
							out = frappe.get_attr(
								"{app}.{module}.page.{page}.{page}.get_context".format(
									app=frappe.local.module_app[scrub(self.module)],
									module=scrub(self.module),
									page=page_name,
								)
							)(context)

							if out:
								context = out
						except (AttributeError, ImportError):
							pass

						template = frappe.render_template(template, context)
					self.script = html_to_js_template(fname, template) + self.script

					# flag for not caching this page
					self._dynamic_page = True

		for path in get_code_files_via_hooks("page_js", self.name):
			js = get_js(path)
			if js:
				self.script += "\n\n" + js


def delete_custom_role(field, docname):
	name = frappe.db.get_value("Custom Role", {field: docname}, "name")
	if name:
		frappe.delete_doc("Custom Role", name)


def as_js_string(value: str) -> str:
	"""`value` as a JS string literal, to be written into source.

	A title is data, and the scaffold writes it into a `.vue` file. `json.dumps`
	writes the whole literal, quotes included, so a quote in the title cannot end
	the string early. `<` is escaped on top of that: the literal sits inside a
	`<script setup>` block, and the SFC parser ends that block at the first
	`</script>` it sees, wherever that is.
	"""
	return json.dumps(value).replace("<", "\\u003c")


# The starter files a Frappe UI page is created with. Written once, never
# overwritten. `__VUE_FILE__` and `__TITLE__` are filled in by
# `Page.write_island_boilerplate`, by replacement rather than `format`,
# because a Vue template is full of braces.
ISLAND_ENTRY = """// The island entry for this page. Desk imports this module and calls `mount`.
//
// `mountVueIsland` opens the shadow root, adopts this app's stylesheet, mirrors
// desk's theme and gives frappe-ui's overlays a portal target inside the root.
import { mountVueIsland } from "@framework/ui/island";

import Page from "./__VUE_FILE__";

export const mount = (el, context) => mountVueIsland(el, { ...context, component: Page });
"""

ISLAND_COMPONENT = """<script setup>
import { onMounted } from "vue";
import { useHost } from "@framework/ui/island";

// Desk hands these down and updates them in place. `route` is the URL segments
// after the page name, and `query` its parameters. A route change re-renders
// this component instead of re-mounting the island.
defineProps({
	route: { type: Array, default: () => [] },
	query: { type: Object, default: () => ({}) },
});

// The page header belongs to the host, and the island reports what it should
// say. Desk writes `title` into the breadcrumb and the browser tab, and turns
// each action into a page menu row. An action is { label, icon? } plus either
// an onClick or an href.
// See ui/island/decisions/0010-a-page-island-reports-title-and-actions.md
const emit = defineEmits(["title", "actions"]);

// Desk's ambient context: locale, timezone, user, theme, and `navigate` for a
// desk route. Every field is optional, so this component still renders where
// nothing provides it, such as in a unit test.
const host = useHost();

// The page's title when it was created. It is a plain string, and `{{ }}` below
// renders it as text, so it stays data wherever it is used.
const title = __TITLE__;

onMounted(() => {
	emit("title", title);
	emit("actions", []);
});

// Data needs no bootstrapping. frappe-ui resources work here as long as each is
// given the fetcher, the way every @framework/ui component does it:
//
//   import { createResource, frappeRequest } from "frappe-ui";
//
//   const users = createResource({
//       url: "frappe.client.get_list",
//       params: { doctype: "User", fields: ["name"] },
//       resourceFetcher: frappeRequest,
//       auto: true,
//   });
</script>

<template>
	<div class="h-full overflow-y-auto p-5">
		<h1 class="text-lg font-semibold text-ink-gray-9">{{ title }}</h1>
		<p class="mt-2 text-sm text-ink-gray-7">
			This page is drawn by an island. Edit this file, save, and it reloads.
		</p>
		<p v-if="route.length" class="mt-2 text-sm text-ink-gray-6">
			Route below the page: {{ route.join("/") }}
		</p>
		<p v-if="host.user" class="mt-2 text-sm text-ink-gray-6">Signed in as {{ host.user }}</p>
	</div>
</template>
"""
