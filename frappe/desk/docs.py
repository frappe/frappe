# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import os
import re
from urllib.parse import urlencode

import frappe
from frappe import _
from frappe.utils import cint, get_url, has_common, sanitize_html
from frappe.website.utils import extract_title, get_frontmatter

DOCS_FOLDER = "docs"
DEFAULT_ROLE = "Desk User"
ALLOWED_FRONTMATTER_KEYS = ("title", "order", "roles")
IMAGE_SRC_PATTERN = re.compile(r'(<img[^>]+src=["\'])([^"\']+)(["\'])', re.IGNORECASE)


@frappe.whitelist()
def get_tree():
	"""Return the documentation navigation tree for pages the current user may access."""
	return build_navigation_tree()


@frappe.whitelist()
def get_page(path: str = ""):
	"""Return rendered HTML and metadata for a documentation page at the given logical path."""
	page = get_page_record(normalize_path(path), check_permission=True)
	content = render_page_content(page.body, page.path)
	return {
		"path": page.path,
		"title": page.title,
		"content": content,
		"toc_html": render_toc(page.body),
	}


@frappe.whitelist()
def get_first_page():
	"""Return the logical path of the first accessible documentation page."""
	pages = discover_pages()
	permitted = sorted(
		(page for page in pages.values() if is_permitted(page)),
		key=lambda page: (page.order, page.title.lower(), page.path),
	)
	if not permitted:
		return None

	return permitted[0].path


@frappe.whitelist()
def get_asset(page_path: str, asset_path: str):
	"""Serve a documentation asset after verifying access to the referring page."""
	page = get_page_record(normalize_path(page_path), check_permission=True)
	asset_file = resolve_asset_path(page, asset_path)

	with open(asset_file, "rb") as f:
		content = f.read()

	frappe.response["type"] = "binary"
	frappe.response["filename"] = os.path.basename(asset_file)
	frappe.response["filecontent"] = content


def discover_pages():
	"""Discover and merge documentation pages from all installed apps."""
	pages = {}

	for app in frappe.get_installed_apps():
		app_path = frappe.get_app_path(app)
		docs_root = os.path.join(app_path, DOCS_FOLDER)
		if not os.path.isdir(docs_root):
			continue

		for basepath, _folders, files in os.walk(docs_root):
			for fname in files:
				if not fname.endswith(".md"):
					continue

				filepath = os.path.join(basepath, fname)
				page = build_page_record(filepath, app, docs_root, app_path)
				pages[page.path] = page

	return pages


def build_page_record(filepath, app, docs_root, app_path):
	page_name, _ext = os.path.splitext(os.path.basename(filepath))
	basepath = os.path.dirname(filepath)
	relative_dir = os.path.relpath(basepath, docs_root)

	if page_name == "index":
		logical_path = "" if relative_dir == "." else relative_dir.replace(os.sep, "/")
	else:
		parent = "" if relative_dir == "." else relative_dir.replace(os.sep, "/")
		logical_path = f"{parent}/{page_name}" if parent else page_name

	with open(filepath, encoding="utf-8") as f:
		source = f.read()

	res = get_frontmatter(source)
	attributes = parse_frontmatter_attributes(res["attributes"])
	body = res["body"]
	title = attributes.get("title") or extract_title(body, logical_path or page_name)

	return frappe._dict(
		{
			"path": logical_path,
			"title": title,
			"order": cint(attributes.get("order", 0)),
			"roles": parse_roles(attributes.get("roles")),
			"body": body,
			"app": app,
			"filepath": filepath,
			"basepath": basepath,
			"docs_root": docs_root,
			"app_path": app_path,
		}
	)


def parse_frontmatter_attributes(attributes):
	if not attributes or not isinstance(attributes, dict):
		return {}

	return {key: attributes[key] for key in ALLOWED_FRONTMATTER_KEYS if key in attributes}


def parse_roles(roles):
	if roles is None:
		return [DEFAULT_ROLE]

	if isinstance(roles, str):
		return [role.strip() for role in roles.split(",") if role.strip()]

	if isinstance(roles, list):
		return [role for role in roles if role]

	return [DEFAULT_ROLE]


def normalize_path(path):
	if not path:
		return ""

	normalized = os.path.normpath(path.strip("/"))
	if normalized in (".", ""):
		return ""

	if normalized.startswith("..") or "/.." in normalized:
		frappe.throw(_("Invalid documentation path"), frappe.ValidationError)

	return normalized.replace(os.sep, "/")


def get_page_record(path, check_permission=False):
	pages = discover_pages()
	page = pages.get(path)

	if not page:
		frappe.throw(_("Documentation page not found"), frappe.DoesNotExistError)

	if check_permission and not is_permitted(page):
		raise frappe.PermissionError(_("No read permission for documentation page {0}").format(page.title))

	return page


def is_permitted(page):
	if frappe.session.user == "Administrator":
		return True

	return has_common(frappe.get_roles(), page.roles)


def build_navigation_tree():
	permitted_pages = {path: page for path, page in discover_pages().items() if is_permitted(page)}
	if not permitted_pages:
		return []

	paths = set(permitted_pages.keys())
	for path in permitted_pages:
		for prefix in get_path_prefixes(path):
			paths.add(prefix)

	nodes = {}
	for path in paths:
		page = permitted_pages.get(path)
		if page:
			nodes[path] = {
				"path": path,
				"title": page.title,
				"order": page.order,
				"has_page": True,
				"children": [],
			}
		else:
			nodes[path] = {
				"path": path,
				"title": title_from_path_segment(path.rsplit("/", 1)[-1]),
				"order": 0,
				"has_page": False,
				"children": [],
			}

	roots = []
	for path, node in nodes.items():
		parent_path = path.rsplit("/", 1)[0] if "/" in path else ""
		if parent_path and parent_path in nodes:
			nodes[parent_path]["children"].append(node)
		elif not parent_path:
			roots.append(node)

	sort_tree_nodes(roots)
	return roots


def get_path_prefixes(path):
	if not path:
		return []

	parts = path.split("/")
	return ["/".join(parts[:index]) for index in range(1, len(parts))]


def title_from_path_segment(segment):
	return segment.replace("_", " ").replace("-", " ").title()


def sort_tree_nodes(nodes):
	nodes.sort(key=lambda node: (node["order"], node["title"].lower(), node["path"]))
	for node in nodes:
		sort_tree_nodes(node["children"])


def render_page_content(body, page_path=""):
	html = frappe.utils.md_to_html(body or "")
	content = sanitize_html(str(html), linkify=True)
	return rewrite_asset_urls(content, page_path)


def rewrite_asset_urls(html, page_path):
	def replace(match):
		prefix, src, suffix = match.groups()
		if src.startswith(("http://", "https://", "data:", "/")):
			return match.group(0)

		return f"{prefix}{get_asset_url(page_path, src)}{suffix}"

	return IMAGE_SRC_PATTERN.sub(replace, html or "")


def get_asset_url(page_path, asset_path):
	query = urlencode({"page_path": page_path, "asset_path": asset_path})
	return get_url(f"/api/method/frappe.desk.docs.get_asset?{query}")


def render_toc(body):
	html = frappe.utils.md_to_html(body or "")
	if not html or not getattr(html, "toc_html", None):
		return ""

	return frappe.utils.sanitize_html(html.toc_html, linkify=True)


def resolve_asset_path(page, asset_path):
	normalized_asset_path = normalize_asset_path(asset_path)
	asset_file = os.path.realpath(os.path.join(page.basepath, normalized_asset_path))
	docs_root = os.path.realpath(page.docs_root)

	if not asset_file.startswith(docs_root + os.sep):
		frappe.throw(_("Invalid asset path"), frappe.ValidationError)

	if not os.path.isfile(asset_file):
		frappe.throw(_("Documentation asset not found"), frappe.DoesNotExistError)

	return asset_file


def normalize_asset_path(asset_path):
	if not asset_path:
		frappe.throw(_("Invalid asset path"), frappe.ValidationError)

	normalized = os.path.normpath(asset_path.strip("/\\"))
	if normalized in (".", "") or normalized.startswith("..") or "/.." in normalized.replace("\\", "/"):
		frappe.throw(_("Invalid asset path"), frappe.ValidationError)

	return normalized
