# Copyright (c) 2025, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import os
import re
from urllib.parse import urlencode

import frappe
from frappe import _
from frappe.translate import get_parent_language
from frappe.utils import cint, get_url, has_common, sanitize_html
from frappe.website.utils import extract_title, get_frontmatter

DOCS_FOLDER = "docs"
DEFAULT_LANG = "en"
DEFAULT_ROLE = "Desk User"
ALLOWED_FRONTMATTER_KEYS = ("title", "order", "roles")
IMAGE_SRC_PATTERN = re.compile(r'(<img[^>]+src=["\'])([^"\']+)(["\'])', re.IGNORECASE)


@frappe.whitelist()
def get_tree(locale: str | None = None):
	"""Return the documentation navigation tree for pages the current user may access."""
	return build_navigation_tree(locale)


@frappe.whitelist()
def get_page(path: str = "", locale: str | None = None):
	"""Return rendered HTML and metadata for a documentation page at the given logical path."""
	locale = normalize_locale(locale)
	page = get_page_record(normalize_path(path), locale=locale, check_permission=True)
	content = render_page_content(page.body, page.path, locale)
	return {
		"path": page.path,
		"title": page.title,
		"locale": locale,
		"content": content,
		"toc_html": render_toc(page.body),
	}


@frappe.whitelist()
def get_first_page(locale: str | None = None):
	"""Return the logical path of the first accessible documentation page."""
	locale = normalize_locale(locale)
	pages = discover_pages(locale)
	permitted = sorted(
		(page for page in pages.values() if is_permitted(page)),
		key=lambda page: (page.order, page.title.lower(), page.path),
	)
	if not permitted:
		return None

	return permitted[0].path


@frappe.whitelist()
def resolve_locale(path: str = ""):
	"""Resolve a stable locale and path for a language-neutral docs route."""
	path = normalize_path(path)
	user_lang = normalize_locale(frappe.local.lang or DEFAULT_LANG)
	raw_pages = discover_raw_pages()

	if path:
		return {"locale": get_preferred_locale_for_path(raw_pages, path, user_lang), "path": path}

	locale = user_lang if locale_has_distinct_content(raw_pages, user_lang) else DEFAULT_LANG
	pages = discover_pages(locale)
	first_path = get_first_page_path(pages)
	return {"locale": locale, "path": first_path if first_path is not None else ""}


@frappe.whitelist()
def get_locales():
	"""Return locales that have documentation, with display labels."""
	return get_documented_locale_infos()


@frappe.whitelist()
def get_page_variants(path: str = ""):
	"""Return locales that have an accessible variant of the given page."""
	path = normalize_path(path)
	variants = []

	for locale_info in get_documented_locale_infos():
		locale = locale_info["locale"]
		if not page_has_variant_for_locale(path, locale):
			continue

		page = get_page_record(path, locale=locale, check_permission=True)
		variants.append(
			{
				"locale": locale,
				"label": locale_info["label"],
				"title": page.title,
			}
		)

	return variants


@frappe.whitelist()
def get_asset(page_path: str, asset_path: str, locale: str | None = None):
	"""Serve a documentation asset after verifying access to the referring page."""
	locale = normalize_locale(locale)
	page = get_page_record(normalize_path(page_path), locale=locale, check_permission=True)
	asset_file = resolve_asset_path(page, asset_path)

	with open(asset_file, "rb") as f:
		content = f.read()

	frappe.response["type"] = "binary"
	frappe.response["filename"] = os.path.basename(asset_file)
	frappe.response["filecontent"] = content


def get_documented_locale_infos(raw_pages=None):
	raw_pages = raw_pages or discover_raw_pages()
	locales = sorted({language for language, path in raw_pages})
	return [{"locale": locale, "label": get_locale_label(locale)} for locale in locales]


@frappe.request_cache
def get_language_labels():
	return {
		name: language_name or name
		for name, language_name in frappe.db.sql(
			"select name, language_name from `tabLanguage`",
			as_list=True,
		)
	}


def get_locale_label(locale):
	return get_language_labels().get(locale, locale)


def page_exists_for_locale(path, locale, check_permission=True):
	try:
		get_page_record(path, locale=locale, check_permission=check_permission)
		return True
	except (frappe.DoesNotExistError, frappe.PermissionError):
		return False


def page_has_variant_for_locale(path, locale, raw_pages=None):
	raw_pages = raw_pages or discover_raw_pages()
	by_lang = group_pages_by_language(raw_pages)
	locale = normalize_locale(locale)

	if path in by_lang.get(DEFAULT_LANG, {}):
		if locale == DEFAULT_LANG:
			return True

		english_page = by_lang[DEFAULT_LANG][path]
		localized = select_localized_page(raw_pages, path, english_page.app_index, locale)
		return bool(localized and localized.language != DEFAULT_LANG)

	return path in by_lang.get(locale, {})


def discover_pages(locale=None):
	"""Discover and compose documentation pages for the requested locale."""
	locale = normalize_locale(locale or frappe.local.lang or DEFAULT_LANG)
	return compose_pages(discover_raw_pages(), locale)


def discover_raw_pages():
	"""Discover documentation pages from all installed apps, grouped by language."""
	pages = {}

	for app_index, app in enumerate(frappe.get_installed_apps()):
		app_path = frappe.get_app_path(app)
		docs_root = os.path.join(app_path, DOCS_FOLDER)
		if not os.path.isdir(docs_root):
			continue

		for basepath, _folders, files in os.walk(docs_root):
			for fname in files:
				if not fname.endswith(".md"):
					continue

				filepath = os.path.join(basepath, fname)
				language, logical_path = parse_docs_path(docs_root, basepath, fname)
				if not language:
					continue

				page = build_page_record(filepath, app, docs_root, app_path, language, logical_path)
				page.app_index = app_index
				pages[(language, logical_path)] = page

	return pages


def compose_pages(raw_pages, locale):
	"""Compose the final page map for the requested locale."""
	by_lang = group_pages_by_language(raw_pages)
	english_pages = by_lang.get(DEFAULT_LANG, {})
	composed = {}

	for path, page in english_pages.items():
		composed[path] = page

	for path, english_page in english_pages.items():
		localized = select_localized_page(raw_pages, path, english_page.app_index, locale)
		if localized and localized.language != DEFAULT_LANG:
			composed[path] = merge_translated_page(english_page, localized)

	localized_only = {}
	for lang in get_language_chain(locale)[:-1]:
		for path, page in by_lang.get(lang, {}).items():
			if path not in english_pages and path not in localized_only:
				localized_only[path] = page

	composed.update(localized_only)
	return composed


def group_pages_by_language(raw_pages):
	by_lang = {}
	for (language, path), page in raw_pages.items():
		by_lang.setdefault(language, {})[path] = page
	return by_lang


def get_language_chain(locale):
	lang = normalize_locale(locale)
	chain = [lang]
	parent = get_parent_language(lang)
	if parent and parent not in chain:
		chain.append(parent)
	if DEFAULT_LANG not in chain:
		chain.append(DEFAULT_LANG)
	return chain


def select_localized_page(raw_pages, path, min_app_index, locale):
	for lang in get_language_chain(locale):
		if lang == DEFAULT_LANG:
			continue

		page = raw_pages.get((lang, path))
		if page and page.app_index >= min_app_index:
			return page

	return None


def get_preferred_locale_for_path(raw_pages, path, user_lang):
	if has_localized_variant(raw_pages, user_lang, path):
		return user_lang

	by_lang = group_pages_by_language(raw_pages)
	if path in by_lang.get(DEFAULT_LANG, {}):
		return DEFAULT_LANG

	localized_only_locale = get_localized_only_locale(raw_pages, path, user_lang)
	if localized_only_locale:
		return localized_only_locale

	return DEFAULT_LANG


def get_localized_only_locale(raw_pages, path, user_lang):
	by_lang = group_pages_by_language(raw_pages)
	if path in by_lang.get(DEFAULT_LANG, {}):
		return None

	for lang in get_language_chain(user_lang):
		if lang != DEFAULT_LANG and path in by_lang.get(lang, {}):
			return lang

	for lang in sorted(by_lang):
		if lang != DEFAULT_LANG and path in by_lang.get(lang, {}):
			return lang

	return None


def has_localized_variant(raw_pages, locale, path):
	by_lang = group_pages_by_language(raw_pages)
	english_pages = by_lang.get(DEFAULT_LANG, {})

	if path in english_pages:
		if locale == DEFAULT_LANG:
			return True

		localized = select_localized_page(raw_pages, path, english_pages[path].app_index, locale)
		return bool(localized and localized.language != DEFAULT_LANG)

	for lang in get_language_chain(locale):
		if lang == DEFAULT_LANG:
			continue
		if path in by_lang.get(lang, {}):
			return True

	return False


def locale_has_distinct_content(raw_pages, locale):
	if locale == DEFAULT_LANG:
		return bool(group_pages_by_language(raw_pages).get(DEFAULT_LANG))

	by_lang = group_pages_by_language(raw_pages)
	english_pages = by_lang.get(DEFAULT_LANG, {})

	for lang in get_language_chain(locale):
		if lang == DEFAULT_LANG:
			continue

		for path, _page in by_lang.get(lang, {}).items():
			if path not in english_pages:
				return True

			english_page = english_pages[path]
			localized = select_localized_page(raw_pages, path, english_page.app_index, locale)
			if localized and localized.language != DEFAULT_LANG:
				return True

	return False


def get_first_page_path(pages):
	permitted = sorted(
		(page for page in pages.values() if is_permitted(page)),
		key=lambda page: (page.order, page.title.lower(), page.path),
	)
	if not permitted:
		return None
	return permitted[0].path


def merge_translated_page(canonical, localized):
	return frappe._dict(
		{
			"path": canonical.path,
			"title": localized.title,
			"order": canonical.order,
			"roles": canonical.roles,
			"body": localized.body,
			"app": localized.app,
			"app_index": localized.app_index,
			"language": localized.language,
			"filepath": localized.filepath,
			"basepath": localized.basepath,
			"docs_root": localized.docs_root,
			"app_path": localized.app_path,
		}
	)


def parse_docs_path(docs_root, basepath, filename):
	page_name, _ext = os.path.splitext(filename)
	relative_dir = os.path.relpath(basepath, docs_root)
	dir_parts = [] if relative_dir == "." else relative_dir.split(os.sep)

	if not dir_parts or not is_language_code(dir_parts[0]):
		return None, None

	language = dir_parts[0]
	content_parts = dir_parts[1:]

	if page_name == "index":
		logical_path = "" if not content_parts else "/".join(content_parts)
	else:
		logical_path = "/".join([*content_parts, page_name]) if content_parts else page_name

	return language, logical_path


@frappe.request_cache
def get_language_codes():
	return set(frappe.get_all("Language", pluck="name"))


def is_language_code(segment):
	return segment in get_language_codes()


def normalize_locale(locale):
	locale = (locale or DEFAULT_LANG).strip()
	if is_language_code(locale):
		return locale

	parent = get_parent_language(locale)
	if parent and is_language_code(parent):
		return locale

	frappe.throw(_("Invalid documentation locale"), frappe.ValidationError)


def build_page_record(filepath, app, docs_root, app_path, language, logical_path):
	with open(filepath, encoding="utf-8") as f:
		source = f.read()

	res = get_frontmatter(source)
	attributes = parse_frontmatter_attributes(res["attributes"])
	body = res["body"]
	page_name = os.path.splitext(os.path.basename(filepath))[0]
	title = attributes.get("title") or extract_title(body, logical_path or page_name)

	return frappe._dict(
		{
			"path": logical_path,
			"title": title,
			"order": cint(attributes.get("order", 0)),
			"roles": parse_roles(attributes.get("roles")),
			"body": body,
			"language": language,
			"app": app,
			"filepath": filepath,
			"basepath": os.path.dirname(filepath),
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


def get_page_record(path, locale=None, check_permission=False):
	locale = normalize_locale(locale or DEFAULT_LANG)
	raw_pages = discover_raw_pages()
	pages = compose_pages(raw_pages, locale)
	page = pages.get(path) or get_localized_only_page(raw_pages, path, locale)

	if not page:
		frappe.throw(_("Documentation page not found"), frappe.DoesNotExistError)

	if check_permission and not is_permitted(page):
		raise frappe.PermissionError(_("No read permission for documentation page {0}").format(page.title))

	return page


def get_localized_only_page(raw_pages, path, locale):
	by_lang = group_pages_by_language(raw_pages)
	if path in by_lang.get(DEFAULT_LANG, {}):
		return None

	for lang in get_language_chain(locale):
		if lang == DEFAULT_LANG:
			continue
		page = by_lang.get(lang, {}).get(path)
		if page:
			return page

	for lang in sorted(by_lang):
		if lang == DEFAULT_LANG:
			continue
		page = by_lang.get(lang, {}).get(path)
		if page:
			return page

	return None


def is_permitted(page):
	if frappe.session.user == "Administrator":
		return True

	return has_common(frappe.get_roles(), page.roles)


def build_navigation_tree(locale=None):
	locale = normalize_locale(locale or frappe.local.lang or DEFAULT_LANG)
	permitted_pages = {path: page for path, page in discover_pages(locale).items() if is_permitted(page)}
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


def render_page_content(body, page_path="", locale=None):
	html = frappe.utils.md_to_html(body or "")
	content = sanitize_html(str(html), linkify=True)
	return rewrite_asset_urls(content, page_path, locale)


def rewrite_asset_urls(html, page_path, locale=None):
	def replace(match):
		prefix, src, suffix = match.groups()
		if src.startswith(("http://", "https://", "data:", "/")):
			return match.group(0)

		return f"{prefix}{get_asset_url(page_path, src, locale)}{suffix}"

	return IMAGE_SRC_PATTERN.sub(replace, html or "")


def get_asset_url(page_path, asset_path, locale=None):
	query = urlencode(
		{
			"page_path": page_path,
			"asset_path": asset_path,
			"locale": normalize_locale(locale),
		}
	)
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
