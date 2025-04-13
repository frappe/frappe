import unittest
from unittest.mock import patch, MagicMock
import datetime
from datetime import timedelta

# Mock the required functions and dependencies
def flt(value):
    """Mock implementation of flt function to convert values to float"""
    if isinstance(value, str):
        return float(value or 0)
    return float(value or 0)

def _(text):
    """Mock translation function"""
    return text

# Import the function being tested
def add_total_row(result, columns, meta=None, is_tree=False, parent_field=None):
    total_row = [""] * len(columns)
    has_percent = []

    for i, col in enumerate(columns):
        fieldtype, options, fieldname = None, None, None
        if isinstance(col, str):
            if meta:
                # get fieldtype from the meta
                field = meta.get_field(col)
                if field:
                    fieldtype = meta.get_field(col).fieldtype
                    fieldname = meta.get_field(col).fieldname
            else:
                col = col.split(":")
                if len(col) > 1:
                    if col[1]:
                        fieldtype = col[1]
                        if "/" in fieldtype:
                            fieldtype, options = fieldtype.split("/")
                    else:
                        fieldtype = "Data"
        else:
            fieldtype = col.get("fieldtype")
            fieldname = col.get("fieldname")
            options = col.get("options")

        for row in result:
            if i >= len(row):
                continue
            cell = row.get(fieldname) if isinstance(row, dict) else row[i]
            if fieldtype in ["Currency", "Int", "Float", "Percent", "Duration"] and flt(cell):
                if not (is_tree and row.get(parent_field)):
                    total_row[i] = flt(total_row[i]) + flt(cell)

            if fieldtype == "Percent" and i not in has_percent:
                has_percent.append(i)

            if fieldtype == "Time" and cell:
                if not total_row[i]:
                    total_row[i] = timedelta(hours=0, minutes=0, seconds=0)
                total_row[i] = total_row[i] + cell

        if fieldtype == "Link" and options == "Currency":
            total_row[i] = result[0].get(fieldname) if isinstance(result[0], dict) else result[0][i]

    for i in has_percent:
        total_row[i] = flt(total_row[i]) / len(has_percent)

    first_col_fieldtype = None
    if isinstance(columns[0], str):
        first_col = columns[0].split(":")
        if len(first_col) > 1:
            first_col_fieldtype = first_col[1].split("/", 1)[0]
    else:
        first_col_fieldtype = columns[0].get("fieldtype")

    if first_col_fieldtype not in ["Currency", "Int", "Float", "Percent", "Date"]:
        total_row[0] = _("Total")

    result.append(total_row)
    return result

# Create the test class following Frappe's style
class TestAddTotalRow(unittest.TestCase):
    def setUp(self):
        # Mock the meta object if needed
        self.meta = MagicMock()
        self.meta.get_field = MagicMock(return_value=None)
        
    def test_percent_columns_calculation_with_tree_structure(self):
        """
        Test the specific change in percent column calculation with tree structure:
        - Original: total_row[i] = flt(total_row[i]) / len(result)
        - New: total_row[i] = flt(total_row[i]) / len(has_percent)
        
        This test creates a complex scenario with multiple percent columns
        and tree structure (parent-child relationships).
        """
        # Create a complex test case with multiple data types
        columns = [
            {"fieldtype": "Data", "fieldname": "account"},
            {"fieldtype": "Currency", "fieldname": "balance"},
            {"fieldtype": "Percent", "fieldname": "growth_rate"},
            {"fieldtype": "Int", "fieldname": "transactions"},
            {"fieldtype": "Percent", "fieldname": "contribution"},
            {"fieldtype": "Float", "fieldname": "avg_txn_value"},
            {"fieldtype": "Percent", "fieldname": "roi"}
        ]
        
        # Create test data with different values including parent-child relationships
        # Structure:
        # - Assets (Parent)
        #   - Current Assets (Child)
        #   - Fixed Assets (Child)
        # - Liabilities (Parent)
        #   - Current Liabilities (Child)
        # - Equity (Parent)
        parent_field = "parent_account"
        
        result = [
            # Parent nodes
            {
                "account": "Assets",
                "balance": 5000,
                "growth_rate": 7.5,
                "transactions": 50,
                "contribution": 50.0,
                "avg_txn_value": 100.0,
                "roi": 15.0,
                parent_field: None,  # Root node
                "is_group": 1
            },
            # Child nodes under Assets
            {
                "account": "Current Assets",
                "balance": 3000,
                "growth_rate": 5.0,
                "transactions": 30,
                "contribution": 30.0,
                "avg_txn_value": 100.0,
                "roi": 10.0,
                parent_field: "Assets",  # Child of Assets
                "is_group": 0
            },
            {
                "account": "Fixed Assets",
                "balance": 2000,
                "growth_rate": 2.5,
                "transactions": 20,
                "contribution": 20.0,
                "avg_txn_value": 100.0,
                "roi": 5.0,
                parent_field: "Assets",  # Child of Assets
                "is_group": 0
            },
            # Another parent node
            {
                "account": "Liabilities",
                "balance": 3000,
                "growth_rate": 4.0,
                "transactions": 40,
                "contribution": 30.0,
                "avg_txn_value": 75.0,
                "roi": 12.0,
                parent_field: None,  # Root node
                "is_group": 1
            },
            # Child node under Liabilities
            {
                "account": "Current Liabilities",
                "balance": 3000,
                "growth_rate": 4.0,
                "transactions": 40,
                "contribution": 30.0,
                "avg_txn_value": 75.0,
                "roi": 12.0,
                parent_field: "Liabilities",  # Child of Liabilities
                "is_group": 0
            },
            # Another parent node
            {
                "account": "Equity",
                "balance": 2000,
                "growth_rate": 3.0,
                "transactions": 10,
                "contribution": 20.0,
                "avg_txn_value": 200.0,
                "roi": 8.0,
                parent_field: None,  # Root node
                "is_group": 1
            }
        ]
        
        # Execute the function with our test data - using tree structure
        updated_result = add_total_row(result.copy(), columns, is_tree=True, parent_field=parent_field)
        
        # The last row should be the total row
        total_row = updated_result[-1]
        
        # Verify non-percent calculations
        self.assertEqual(total_row[0], "Total")
        
        # When is_tree=True, only root nodes should be included in totals
        # So we should only sum values from "Assets", "Liabilities" and "Equity" (not their children)
        expected_balance = 5000 + 3000 + 2000  # Assets + Liabilities + Equity
        expected_transactions = 50 + 40 + 10    # Assets + Liabilities + Equity
        expected_avg_txn_value = 100.0 + 75.0 + 200.0  # Assets + Liabilities + Equity
        
        self.assertEqual(total_row[1], expected_balance)
        self.assertEqual(total_row[3], expected_transactions)
        self.assertEqual(total_row[5], expected_avg_txn_value)
        
        # Now test the percent columns (indices 2, 4, 6)
        percent_indices = [2, 4, 6]
        
        # Calculate expected values for percent columns - only including root nodes
        # and dividing by the number of percent columns (3) not rows
        expected_growth_rate = (7.5 + 4.0 + 3.0) / len(percent_indices)
        expected_contribution = (50.0 + 30.0 + 20.0) / len(percent_indices)
        expected_roi = (15.0 + 12.0 + 8.0) / len(percent_indices)
        
        # Assert the correct values in the percent columns
        self.assertAlmostEqual(total_row[2], expected_growth_rate)
        self.assertAlmostEqual(total_row[4], expected_contribution)
        self.assertAlmostEqual(total_row[6], expected_roi)
        
        # Demonstrate how the result would differ with the old implementation
        # (dividing by number of rows instead of number of percent columns)
        old_calculation_growth = (7.5 + 4.0 + 3.0) / len(result)
        old_calculation_contribution = (50.0 + 30.0 + 20.0) / len(result)
        old_calculation_roi = (15.0 + 12.0 + 8.0) / len(result)
        
        # These assertions should fail if we were using the old implementation
        self.assertNotEqual(total_row[2], old_calculation_growth)
        self.assertNotEqual(total_row[4], old_calculation_contribution)
        self.assertNotEqual(total_row[6], old_calculation_roi)
        
    
    def test_empty_tree_structure(self):
        """Test with empty result set but with tree structure parameters"""
        
        columns = [
            {"fieldtype": "Data", "fieldname": "account"},
            {"fieldtype": "Currency", "fieldname": "balance"},
            {"fieldtype": "Percent", "fieldname": "growth_rate"}
        ]
        
        result = []
        
        # This should handle the case without errors
        updated_result = add_total_row(result.copy(), columns, is_tree=True, parent_field="parent")
        self.assertEqual(len(updated_result), 1)  # Should add a total row
        total_row = updated_result[0]
        self.assertEqual(total_row[0], "Total")
        
    

if __name__ == "__main__":
    unittest.main()

