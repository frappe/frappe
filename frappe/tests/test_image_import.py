import frappe
from frappe.tests.utils import FrappeTestCase
from unittest.mock import patch, MagicMock
from frappe.core.api import image_import


class TestImageImport(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.valid_url = "https://example.com/image.png"
        cls.fake_image = b"fake_image_data"
        cls.default_headers = {
            "Content-Type": "image/png",
            "Content-Length": str(len(cls.fake_image))
        }

    def mock_response(self, content=None, content_type="image/png", status_code=200, headers=None):
        content = content if content is not None else self.fake_image
        headers = headers or {
            "Content-Type": content_type,
            "Content-Length": str(len(content))
        }
        mock = MagicMock()
        mock.status_code = status_code
        mock.content = content
        mock.headers = headers
        mock.raise_for_status = MagicMock()
        return mock

    @patch("requests.get")
    def test_import_valid_png_image(self, mock_get):
        mock_get.return_value = self.mock_response()
        result = image_import.import_image_from_url(url=self.valid_url, optimize=False)
        self.assertIn("file_url", result)
        self.assertIn(".png", result["file_url"])

    @patch("requests.get")
    @patch("frappe.utils.image.optimize_image")
    def test_import_and_optimize_image(self, mock_optimize, mock_get):
        mock_get.return_value = self.mock_response()
        mock_optimize.return_value = b"optimized_image_data"
        result = image_import.import_image_from_url(url=self.valid_url, optimize=True)
        self.assertIn("file_url", result)

    def test_invalid_url_format_throws(self):
        with self.assertRaises(Exception) as ctx:
            image_import.import_image_from_url(url="not a valid url")
        self.assertIn("valid", str(ctx.exception))

    @patch("requests.get")
    def test_non_image_content_type_rejected(self, mock_get):
        mock_get.return_value = self.mock_response(content_type="text/html")
        with self.assertRaises(Exception) as ctx:
            image_import.import_image_from_url(url="https://example.com/page.html")
        self.assertIn("valid image", str(ctx.exception))

    @patch("requests.get")
    def test_empty_image_content_throws(self, mock_get):
        mock_get.return_value = self.mock_response(content=b"")
        with self.assertRaises(Exception):
            image_import.import_image_from_url(url=self.valid_url)

    @patch("requests.get")
    @patch("frappe.get_system_settings")
    def test_image_exceeding_max_size_throws(self, mock_settings, mock_get):
        mock_settings.return_value = 5 * 1024 * 1024  # 5 MB
        mock_get.return_value = self.mock_response(content=b"x" * (6 * 1024 * 1024))
        with self.assertRaises(Exception):
            image_import.import_image_from_url(url=self.valid_url)

    @patch("requests.get")
    def test_unsupported_file_format_throws(self, mock_get):
        mock_get.return_value = self.mock_response(content_type="image/bmp")
        with self.assertRaises(Exception) as ctx:
            image_import.import_image_from_url(url=self.valid_url)
        self.assertIn("Unsupported file format", str(ctx.exception))

    @patch("frappe.db.exists")
    @patch("frappe.get_doc")
    def test_folder_creation(self, mock_get_doc, mock_db_exists):
        mock_db_exists.side_effect = lambda doctype, filters: False
        mock_get_doc.return_value = MagicMock()

        image_import.ensure_folder("Home/Library/TestFolder")
        mock_get_doc.assert_called()