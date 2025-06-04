import frappe
import requests
import mimetypes
import os
import hashlib
import logging
from urllib.parse import urlparse
from frappe import _

@frappe.whitelist(allow_guest=True)
def import_image_from_url(url=None, optimize=False):
    logger = frappe.logger()

    # Handle JSON POST input
    if not url:
        url = frappe.form_dict.get("url")
    optimize = frappe.form_dict.get("optimize", optimize) in [True, "1", "true", "True"]

    if not url:
        frappe.throw(_("Image URL is required."))

    # Validate URL format
    parsed_url = urlparse(url)
    if not parsed_url.scheme or not parsed_url.netloc:
        frappe.throw(_("The provided URL is not valid."))

    # Fetch the image
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
    except requests.RequestException as e:
        logger.error(f"Image fetch failed for URL {url}: {e}")
        frappe.throw(_("Failed to fetch image from URL."))

    # Validate content type
    content_type = response.headers.get("Content-Type", "")
    if not content_type.startswith("image/"):
        frappe.throw(_("The URL does not point to a valid image."))

    # Validate image content
    content = response.content
    if not content:
        frappe.throw(_("The image content is empty."))

    # Validate file size
    max_size = frappe.get_system_settings("max_file_size") or 25 * 1024 * 1024
    if len(content) > max_size:
        frappe.throw(_("The image size exceeds the maximum allowed size of {0} MB.").format(max_size // (1024 * 1024)))

    # Determine file extension and name
    extension = mimetypes.guess_extension(content_type) or ".png"
    base_name = os.path.basename(parsed_url.path)
    if not base_name:
        base_name = "imported_image"
    if not base_name.endswith(extension):
        base_name += extension

    # Optionally hash to avoid duplicates
    hash_digest = hashlib.md5(content).hexdigest()
    filename = f"{hash_digest}{extension}"

    # Optimize image if requested
    if optimize:
        try:
            from frappe.utils.image import optimize_image
            content = optimize_image(content=content, content_type=content_type)
        except Exception as e:
            logger.warning(f"Image optimization failed: {e}")

    # Create and insert the file document
    file_doc = frappe.get_doc({
        "doctype": "File",
        "file_name": filename,
        "content": content,
        "is_private": 1,
        "folder": folder,
    }).insert(ignore_permissions=True)

    logger.info(f"Image successfully imported as: {file_doc.file_url}")

    return {
        "file_url": file_doc.file_url,
        "name": file_doc.name,
    }

def validate_url_scheme(scheme: str):
    if scheme not in ["http", "https"]:
        frappe.throw(_("Only HTTP and HTTPS URLs are allowed."))

def get_max_allowed_size():
    setting = frappe.get_system_settings("max_file_size")
    return int(setting) if setting else 25 * 1024 * 1024

def ensure_folder(path: str):
    parts = path.strip("/").split("/")
    parent = None
    for part in parts:
        if part == "Home" and parent is None:
            parent = "Home"
            continue
        if not frappe.db.exists("File", {"file_name": part, "folder": parent or "Home"}):
            frappe.get_doc({
                "doctype": "File",
                "file_name": part,
                "is_folder": 1,
                "folder": parent or "Home"
            }).insert(ignore_permissions=True)
        parent = f"{parent}/{part}" if parent else part

def get_unique_filename(folder: str, original_name: str) -> str:
    name, ext = os.path.splitext(original_name)
    filename = original_name
    if not frappe.db.exists("File", {"file_name": filename, "folder": folder}):
        return filename
    index = 1
    while True:
        filename = f"{name}({index}){ext}"
        if not frappe.db.exists("File", {"file_name": filename, "folder": folder}):
            return filename
        index += 1

def find_existing_file_with_same_content(folder: str, content: bytes):
    files = frappe.get_all("File", filters={"folder": folder}, fields=["name", "file_name", "file_url"])
    for f in files:
        doc = frappe.get_doc("File", f.name)
        try:
            if doc.get_content() == content:
                return doc
        except Exception:
            continue
    return None