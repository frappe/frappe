from __future__ import unicode_literals, absolute_import
import click
import os
import frappe
from frappe.commands import pass_context


@click.command('write-docs')
@pass_context
@click.argument('app')
@click.option('--target', default=None)
@click.option('--local', default=False, is_flag=True, help='Run app locally')
def write_docs(context, app, target=None, local=False):
	"Setup docs in target folder of target app"
	from frappe.utils.setup_docs import setup_docs

	if not target:
		target = os.path.abspath(os.path.join("..", "docs", app))

	for site in context.sites:
		try:
			frappe.init(site=site)
			frappe.connect()
			make = setup_docs(app)
			make.make_docs(target, local)
		finally:
			frappe.destroy()

@click.command('build-docs')
@pass_context
@click.argument('app')
@click.option('--docs-version', default='current')
@click.option('--target', default=None)
@click.option('--local', default=False, is_flag=True, help='Run app locally')
@click.option('--watch', default=False, is_flag=True, help='Watch for changes and rewrite')
def build_docs(context, app, docs_version="current", target=None, local=False, watch=False):
	"Setup docs in target folder of target app"
	from frappe.utils import watch as start_watch
	if not target:
		target = os.path.abspath(os.path.join("..", "docs", app))

	for site in context.sites:
		_build_docs_once(site, app, docs_version, target, local)

		if watch:
			def trigger_make(source_path, event_type):
				if "/templates/autodoc/" in source_path:
					_build_docs_once(site, app, docs_version, target, local)

				elif ("/docs.css" in source_path
					or "/docs/" in source_path
					or "docs.py" in source_path):
					_build_docs_once(site, app, docs_version, target, local, only_content_updated=True)

			apps_path = frappe.get_app_path(app, "..", "..")
			start_watch(apps_path, handler=trigger_make)

def _build_docs_once(site, app, docs_version, target, local, only_content_updated=False):
	from frappe.utils.setup_docs import setup_docs

	try:

		frappe.init(site=site)
		frappe.connect()
		make = setup_docs(app)

		if not only_content_updated:
			make.build(docs_version)

		make.make_docs(target, local)

	finally:
		frappe.destroy()

commands = [
	build_docs,
	write_docs,
]
