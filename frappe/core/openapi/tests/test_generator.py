# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import unittest

import frappe
from frappe.core.openapi.generator import OpenAPIGenerator


class TestOpenAPIGenerator(unittest.TestCase):
    def setUp(self):
        self.site = frappe.local.site or frappe.get_site_name()
        self.generator = OpenAPIGenerator(site=self.site)

    def test_url_encoding_and_display(self):
        """Test URL encoding and display for DocType endpoints with spaces."""
        doctype = "Email Account"
        encoded = "Email%20Account"
        path = f"/api/resource/{encoded}/{{name}}"

        spec = self.generator.generate()

        self.assertIn(
            path, spec["paths"], f"Encoded path {path} not found in OpenAPI spec."
        )

        endpoint = spec["paths"][path]["get"]
        self.assertIn(doctype, endpoint["tags"], "Decoded DocType name not in tags.")
        self.assertIn(
            doctype, endpoint["summary"], "Decoded DocType name not in summary."
        )

        params = endpoint["parameters"]
        name_param = next(
            (p for p in params if p["name"] == "name" and p["in"] == "path"), None
        )
        self.assertIsNotNone(name_param, "Path parameter 'name' not defined.")
        self.assertTrue(
            name_param["required"], "Path parameter 'name' should be required."
        )
        self.assertEqual(
            name_param["schema"]["type"],
            "string",
            "Path parameter 'name' should be string.",
        )

    def test_whitelisted_methods_discovery(self):
        """Ensure whitelisted methods are discovered and /api/method paths exist."""
        spec = self.generator.generate()
        method_paths = [
            p for p in spec.get("paths", {}).keys() if p.startswith("/api/method/")
        ]
        self.assertTrue(
            len(method_paths) > 0,
            "No whitelisted method endpoints found under /api/method/",
        )

    def test_alphabetical_ordering(self):
        """Ensure components.schemas and paths are sorted alphabetically."""
        spec = self.generator.generate()
        schemas = list(spec.get("components", {}).get("schemas", {}).keys())
        self.assertEqual(
            schemas, sorted(schemas), "Schemas are not alphabetically ordered"
        )
        paths = list(spec.get("paths", {}).keys())
        self.assertEqual(paths, sorted(paths), "Paths are not alphabetically ordered")

    def test_list_endpoint_pagination_params(self):
        """Ensure list endpoints include pagination query parameters."""
        path = "/api/resource/User"
        spec = self.generator.generate()
        if path in spec.get("paths", {}):
            get_op = spec["paths"][path].get("get")
            self.assertIsNotNone(get_op, "GET operation for list endpoint missing")
            params = get_op.get("parameters", [])
            names = [p.get("name") for p in params]
            self.assertIn(
                "limit_start",
                names,
                "limit_start not present in list endpoint parameters",
            )
            self.assertIn(
                "limit_page_length",
                names,
                "limit_page_length not present in list endpoint parameters",
            )
        else:
            self.skipTest(f"List endpoint {path} not present in spec on this site")


if __name__ == "__main__":
    unittest.main()
