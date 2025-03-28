import unittest
from datetime import datetime, date
from frappe.utils.data import get_datetime_str


class TestGetDatetimeStr(unittest.TestCase):

    def test_datetime_input(self):
        dt = datetime(2025, 3, 28, 15, 30, 45)
        result = get_datetime_str(dt)
        self.assertIsInstance(result, str)
        self.assertEqual(result, '2025-03-28 15:30:45')

    def test_date_input(self):
        d = date(2025, 3, 28)
        result = get_datetime_str(d)
        self.assertIsInstance(result, str)
        self.assertEqual(result, '2025-03-28 00:00:00')

    def test_string_input(self):
        dt_str = '2025-03-28 10:20:30'
        result = get_datetime_str(dt_str)
        self.assertIsInstance(result, str)
        self.assertEqual(result, '2025-03-28 10:20:30')

    def test_invalid_string_input(self):
        invalid_str = 'not-a-valid-date'
        with self.assertRaises(ValueError):
            get_datetime_str(invalid_str)


if __name__ == '__main__':
    unittest.main()
