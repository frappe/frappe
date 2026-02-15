# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

"""
OpenAPI 3.0 specification generator for Frappe sites.
Scans installed apps for DocTypes and whitelisted methods,
generates OpenAPI JSON, and caches results.
"""

import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import frappe

logger = logging.getLogger(__name__)

# System/internal doctypes to exclude
EXCLUDED_DOCTYPES = {
    "DocType",
    "Custom Field",
    "DocPerm",
}

# HTTP method detection for whitelisted methods
METHOD_DETECTION_RULES = {
    "GET": ["get_", "list_", "fetch_", "has_", "is_", "check_", "validate_", "read_"],
    "POST": [
        "create_",
        "insert_",
        "submit_",
        "update_",
        "save_",
        "set_",
        "add_",
        "post_",
    ],
}


class OpenAPIGenerator:
    """Generate OpenAPI 3.0 specification."""

    def __init__(self, site: str = None):
        self.site = site or frappe.local.site
        self.openapi_spec = {
            "openapi": "3.0.0",
            "info": {
                "title": "Frappe API",
                "description": f"OpenAPI specification for {self.site}",
            },
            "paths": {},
            "components": {
                "schemas": {},
                "securitySchemes": {
                    "tokenAuth": {
                        "type": "apiKey",
                        "in": "header",
                        "name": "Authorization",
                        "description": 'Format: "token api_key:api_secret"',
                    },
                    "oauthBearer": {
                        "type": "http",
                        "scheme": "bearer",
                        "bearerFormat": "JWT",
                    },
                },
            },
            "security": [{"tokenAuth": []}, {"oauthBearer": []}],
        }

    def generate(self) -> Dict[str, Any]:
        """Generate complete OpenAPI specification."""

        allow_openapi = frappe.conf.get("enable_openapi")
        if not allow_openapi:
            logger.warning(
                "OpenAPI generation is disabled (enable_openapi not set in config)"
            )
            return self.openapi_spec

        logger.info(f"Generating OpenAPI specification for {self.site}")

        # Scan DocTypes
        self.add_doctype_endpoints()

        # Scan whitelisted methods
        self.add_whitelisted_method_endpoints()

        # Sort paths (API endpoints) alphabetically
        if "paths" in self.openapi_spec:
            self.openapi_spec["paths"] = dict(
                sorted(self.openapi_spec["paths"].items())
            )

        # Sort schemas alphabetically
        if "schemas" in self.openapi_spec.get("components", {}):
            self.openapi_spec["components"]["schemas"] = dict(
                sorted(self.openapi_spec["components"]["schemas"].items())
            )

        logger.info(
            f"Generated OpenAPI spec with {len(self.openapi_spec['paths'])} endpoints"
        )
        return self.openapi_spec

    def add_doctype_endpoints(self) -> None:
        """
        Add REST endpoints for all non-system DocTypes.

        Endpoints with /{name} in their path (GET single, PUT, DELETE) automatically include a required path parameter definition in the OpenAPI spec.
        This ensures that /api/resource/DocType/{name} endpoints are documented with the correct path parameter for all DocTypes.
        """
        try:
            doctypes = frappe.get_all(
                "DocType",
                fields=["name", "istable", "issingle"],
                filters={"custom": 0},
            )
        except Exception as e:
            logger.error(f"Failed to fetch DocTypes: {e}")
            return

        for dt in doctypes:
            doctype_name = dt.get("name")

            # Skip excluded doctypes and child/table doctypes
            if doctype_name in EXCLUDED_DOCTYPES or dt.get("istable"):
                continue

            try:
                meta = frappe.get_meta(doctype_name)
                if not meta:
                    continue

                # URL-encode doctype name for endpoint paths
                from urllib.parse import quote

                encoded_doctype = quote(doctype_name, safe="")

                # Add GET (read single)
                self.add_endpoint(
                    f"/api/resource/{encoded_doctype}/{{name}}",
                    "get",
                    doctype_name,
                    method="GET",
                )

                # Add GET (list)
                self.add_endpoint(
                    f"/api/resource/{encoded_doctype}",
                    "get",
                    doctype_name,
                    method="GET",
                    is_list=True,
                )

                # Add POST (create)
                self.add_endpoint(
                    f"/api/resource/{encoded_doctype}",
                    "post",
                    doctype_name,
                    method="POST",
                    is_create=True,
                )

                # Add PUT (update)
                self.add_endpoint(
                    f"/api/resource/{encoded_doctype}/{{name}}",
                    "put",
                    doctype_name,
                    method="PUT",
                )

                # Add DELETE
                self.add_endpoint(
                    f"/api/resource/{encoded_doctype}/{{name}}",
                    "delete",
                    doctype_name,
                    method="DELETE",
                )

                # Add schema to components
                self.add_doctype_schema(doctype_name)

            except Exception as e:
                logger.warning(f"Failed to process DocType {doctype_name}: {e}")

    def add_whitelisted_method_endpoints(self) -> None:
        """Discover and add whitelisted method endpoints."""
        methods = self.discover_whitelisted_methods()

        for method in methods:
            method_path = method.get("method", method.get("name", ""))
            if not method_path:
                continue

            try:
                http_method = self.detect_http_method(method_path)
                self.add_endpoint(
                    f"/api/method/{method_path}",
                    http_method.lower(),
                    method_path,
                    method=http_method,
                )
            except Exception as e:
                logger.warning(
                    f"Failed to process whitelisted method {method_path}: {e}"
                )

    def discover_whitelisted_methods(self) -> List[Dict[str, str]]:
        """Discover whitelisted methods by scanning installed apps."""
        methods = []
        installed_apps = frappe.get_installed_apps()
        whitelist_pattern = re.compile(
            r"@frappe\.whitelist\b(?:\s*\([^)]*\))?\s*\n\s*def\s+(\w+)", re.MULTILINE
        )

        for app in installed_apps:
            try:
                app_path = frappe.get_app_path(app)
                if not app_path or not os.path.isdir(app_path):
                    continue

                self.scan_app_directory(app_path, app, whitelist_pattern, methods)
            except Exception as e:
                logger.debug(f"Failed to scan app {app}: {e}")

        return methods

    def scan_app_directory(
        self,
        directory: str,
        app_name: str,
        pattern: re.Pattern,
        methods: List[Dict[str, str]],
    ) -> None:
        """Recursively scan directory for whitelisted methods."""
        try:
            for root, dirs, files in os.walk(directory):
                # Skip certain directories
                dirs[:] = [
                    d
                    for d in dirs
                    if d not in [".git", "__pycache__", "node_modules", ".venv", "env"]
                ]

                for file in files:
                    if not file.endswith(".py"):
                        continue

                    filepath = os.path.join(root, file)
                    try:
                        self.scan_python_file(filepath, app_name, pattern, methods)
                    except Exception as e:
                        logger.debug(f"Error scanning {filepath}: {e}")

        except Exception as e:
            logger.debug(f"Error scanning directory {directory}: {e}")

    def scan_python_file(
        self,
        filepath: str,
        app_name: str,
        pattern: re.Pattern,
        methods: List[Dict[str, str]],
    ) -> None:
        """Scan Python file for whitelisted methods."""
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            # Find all whitelisted methods
            matches = pattern.finditer(content)
            for match in matches:
                method_name = match.group(1)
                # Construct full method path: app.module.method_name
                # e.g., frappe.client.get_value or erpnext.accounts.get_company_default
                rel_path = os.path.relpath(filepath, frappe.get_app_path(app_name))
                module_path = rel_path[:-3].replace(
                    os.sep, "."
                )  # Remove .py and convert to dots

                full_method_path = f"{app_name}.{module_path}.{method_name}"

                method_obj = {
                    "name": full_method_path,
                    "method": full_method_path,
                }

                # Avoid duplicates
                if not any(m.get("method") == full_method_path for m in methods):
                    methods.append(method_obj)
                    logger.debug(f"Found whitelisted method: {full_method_path}")

        except Exception as e:
            logger.debug(f"Error reading {filepath}: {e}")

    def detect_http_method(self, method_path: str) -> str:
        """Detect HTTP method from method name pattern."""
        method_name = method_path.split(".")[-1].lower()

        for http_method, prefixes in METHOD_DETECTION_RULES.items():
            if any(method_name.startswith(p) for p in prefixes):
                return http_method

        return "POST"

    def add_endpoint(
        self,
        path: str,
        operation: str,
        doctype_or_method: str,
        method: str = "GET",
        is_list: bool = False,
        is_create: bool = False,
    ) -> None:
        """Add endpoint to OpenAPI spec."""
        if path not in self.openapi_spec["paths"]:
            self.openapi_spec["paths"][path] = {}

        op_key = operation.lower()
        # If doctype_or_method is a DocType, show decoded name in summary/description
        from urllib.parse import unquote

        decoded_name = (
            unquote(doctype_or_method)
            if "%" in doctype_or_method
            else doctype_or_method
        )

        operation_obj = {
            "tags": [decoded_name],
            "operationId": f"{decoded_name}_{method.lower()}",
            "summary": self.generate_summary(decoded_name, method, is_list),
            "description": self.generate_description(
                decoded_name, method, is_list, is_create
            ),
            "responses": self.generate_responses(method),
        }

        # Add parameters for GET/DELETE/PUT (includes path params)
        if method in ["GET", "DELETE", "PUT"]:
            operation_obj["parameters"] = self.generate_parameters(path, is_list)
        elif method == "GET":
            operation_obj["parameters"] = self.generate_parameters(path, is_list)

        # Add requestBody for POST/PUT
        if method in ["POST", "PUT"]:
            operation_obj["requestBody"] = self.generate_request_body(
                doctype_or_method, is_create
            )

        # Add security
        operation_obj["security"] = [{"tokenAuth": []}, {"oauthBearer": []}]

        self.openapi_spec["paths"][path][op_key] = operation_obj

    def generate_summary(self, name: str, method: str, is_list: bool = False) -> str:
        """Generate summary for endpoint."""
        if is_list:
            return f"List {name} documents"
        if method == "GET":
            return f"Get single {name} document"
        if method == "POST":
            return f"Create new {name} document"
        if method == "PUT":
            return f"Update {name} document"
        if method == "DELETE":
            return f"Delete {name} document"
        return f"{method} {name}"

    def generate_description(
        self, name: str, method: str, is_list: bool = False, is_create: bool = False
    ) -> str:
        """Generate description for endpoint."""
        try:
            meta = frappe.get_meta(name)
            return meta.description or ""
        except Exception:
            return f"{method} endpoint for {name}"

    def generate_parameters(
        self, path: str = "", is_list: bool = False
    ) -> List[Dict[str, Any]]:
        """Generate parameters (path + query) for endpoints."""
        params = []

        # Extract path parameters from the path string (e.g., {name})
        path_params = re.findall(r"\{(\w+)\}", path)
        for param_name in path_params:
            path_param = {
                "name": param_name,
                "in": "path",
                "required": True,
                "schema": {"type": "string"},
            }
            if param_name == "name":
                path_param["description"] = "Document name/ID"
            else:
                path_param["description"] = f"Value for {param_name}"

            params.append(path_param)

        # Add query parameters
        query_params = [
            {
                "name": "filters",
                "in": "query",
                "description": "Filter conditions (JSON format)",
                "schema": {"type": "string"},
            },
            {
                "name": "fields",
                "in": "query",
                "description": "Comma-separated field names to return",
                "schema": {"type": "string"},
            },
        ]

        if is_list:
            query_params.extend(
                [
                    {
                        "name": "limit_start",
                        "in": "query",
                        "description": "Pagination start",
                        "schema": {"type": "integer", "default": 0},
                    },
                    {
                        "name": "limit_page_length",
                        "in": "query",
                        "description": "Pagination limit",
                        "schema": {"type": "integer", "default": 20},
                    },
                ]
            )

        params.extend(query_params)
        return params

    def generate_request_body(
        self, doctype_name: str, is_create: bool = False
    ) -> Dict[str, Any]:
        """Generate requestBody schema."""
        schema_ref = f"#/components/schemas/{doctype_name}"
        if is_create:
            schema_ref = f"#/components/schemas/{doctype_name}Create"

        return {
            "required": True,
            "content": {
                "application/json": {
                    "schema": {"$ref": schema_ref},
                }
            },
        }

    def generate_responses(self, method: str) -> Dict[str, Any]:
        """Generate standard responses for endpoint."""
        if method == "GET":
            return {
                "200": {
                    "description": "Success",
                    "content": {"application/json": {"schema": {"type": "object"}}},
                },
                "401": {"description": "Unauthorized"},
                "404": {"description": "Not found"},
            }

        if method in ["POST", "PUT"]:
            return {
                "200": {
                    "description": "Success",
                    "content": {"application/json": {"schema": {"type": "object"}}},
                },
                "400": {"description": "Validation error"},
                "401": {"description": "Unauthorized"},
            }

        if method == "DELETE":
            return {
                "204": {"description": "Deleted successfully"},
                "401": {"description": "Unauthorized"},
                "404": {"description": "Not found"},
            }

        return {
            "200": {
                "description": "Success",
                "content": {"application/json": {"schema": {"type": "object"}}},
            }
        }

    def add_doctype_schema(self, doctype_name: str) -> None:
        """Add DocType schema to components."""
        try:
            meta = frappe.get_meta(doctype_name)
            fields = meta.fields

            update_schema = {
                "type": "object",
                "properties": {},
                "required": [],
            }

            create_schema = {
                "type": "object",
                "properties": {},
                "required": [],
            }

            for field in fields:
                if field.fieldname in ["name", "owner", "modified", "creation"]:
                    continue

                prop = self.field_to_property(field)
                update_schema["properties"][field.fieldname] = prop

                if field.reqd:
                    create_schema["required"].append(field.fieldname)

                create_schema["properties"][field.fieldname] = prop

            self.openapi_spec["components"]["schemas"][doctype_name] = update_schema
            self.openapi_spec["components"]["schemas"][
                f"{doctype_name}Create"
            ] = create_schema

        except Exception as e:
            logger.warning(f"Failed to generate schema for {doctype_name}: {e}")

    def field_to_property(self, field: Any) -> Dict[str, Any]:
        """Convert DocType field to OpenAPI property."""
        field_type = field.fieldtype or "Data"

        type_mapping = {
            "Data": "string",
            "Link": "string",
            "Int": "integer",
            "Float": "number",
            "Percent": "number",
            "Currency": "number",
            "Date": "string",
            "Datetime": "string",
            "Time": "string",
            "Select": "string",
            "Check": "boolean",
            "Long Text": "string",
            "Text": "string",
            "Code": "string",
            "JSON": "object",
            "Table": "array",
            "Attach": "string",
            "Attach Image": "string",
            "Signature": "string",
            "Color": "string",
            "Dynamic Link": "string",
            "Read Only": "string",
        }

        prop_type = type_mapping.get(field_type, "string")

        prop = {
            "type": prop_type,
            "description": field.label or field.fieldname,
        }

        if field_type == "Select" and field.options:
            prop["enum"] = [opt.strip() for opt in field.options.split("\n")]

        if field_type == "Date":
            prop["format"] = "date"
        elif field_type in ["Datetime", "Timestamp"]:
            prop["format"] = "date-time"

        return prop

    def save_to_cache(self) -> None:
        """Save OpenAPI spec to Redis cache."""
        try:
            cache_key = f"openapi_spec:{self.site}"
            frappe.cache().set_value(
                cache_key, json.dumps(self.openapi_spec), expires_in_sec=3600
            )
            logger.info(f"Saved OpenAPI spec to cache: {cache_key}")
        except Exception as e:
            logger.warning(f"Failed to cache OpenAPI spec (continuing): {e}")

    def save_to_file(self, filepath: Optional[str] = None) -> str:
        """Save OpenAPI spec to file."""
        if not filepath:
            from pathlib import Path

            site_path = Path(frappe.get_site_path())
            filepath = site_path / "public" / "files" / "openapi.json"
            filepath.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(filepath, "w") as f:
                json.dump(self.openapi_spec, f, indent=2)
            logger.info(f"Saved OpenAPI spec to file: {filepath}")
            return str(filepath)
        except Exception as e:
            logger.error(f"Failed to save OpenAPI spec: {e}")
            raise


def generate_specification(site: str = None) -> Dict[str, Any]:
    """Generate and return OpenAPI specification for site."""
    generator = OpenAPIGenerator(site)
    spec = generator.generate()
    generator.save_to_cache()
    generator.save_to_file()
    return spec
