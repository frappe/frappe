# Frappe Test Utilities

This README provides an overview of the test utilities available in the Frappe framework, particularly focusing on the `frappe/tests/utils.py` file. These utilities are designed to facilitate efficient and effective testing of Frappe applications.

## Main Functions

The `utils.py` file contains several key components:

1. Test record generation utilities
2. Test case classes (UnitTestCase and IntegrationTestCase)
3. Context managers for various testing scenarios
4. Utility functions and decorators

## Test Case Classes

### UnitTestCase

This class extends `unittest.TestCase` and provides additional utilities specific to Frappe framework. It's designed for testing individual components or functions in isolation.

Some key methods and features include:

- Custom assertions (e.g., `assertQueryEqual`, `assertDocumentEqual`)
- HTML and SQL normalization
- Context managers for user switching and time freezing

### IntegrationTestCase

This class extends `UnitTestCase` and is designed for integration testing. It provides features for:

- Automatic database setup and teardown
- Database connection management
- Query counting and Redis call monitoring
- Lazy loading of test record dependencies

For a complete list of methods and their usage, please refer to the actual code in `frappe/tests/utils.py`.

## Usage

To use these test utilities in your Frappe application tests, you can inherit from the appropriate test case class:

```python
from frappe.tests.utils import UnitTestCase

class MyTestCase(UnitTestCase):
    def test_something(self):
        # Your test code here
        pass
```

Remember that this README provides an overview as of the time of writing. Always refer to the actual code for the most up-to-date and detailed information on available methods and their usage.

## Contributing

If you're adding new test utilities or modifying existing ones, please ensure to update this README accordingly.
