# Frappe Testing Module

This module provides a comprehensive framework for running tests in Frappe applications. It includes functionality for test discovery, execution, result reporting, and environment setup.

## Key Components

- `TestConfig`: Configuration class for customizing test execution
- `TestRunner`: Main class for running test suites with additional Frappe-specific functionality
- `TestResult`: Custom test result class for improved output formatting and logging
- `discover_all_tests`: Function to discover all tests in specified Frappe apps
- `discover_doctype_tests`: Function to discover tests for specific DocTypes
- `discover_module_tests`: Function to discover tests in specific modules

## Usage

This module is typically used by Frappe's CLI commands for running tests, but can also be used programmatically for custom test execution scenarios.

For detailed information about each component, please refer to the well-commented code in the following files:

- [`__init__.py`](./__init__.py): Module initialization and logging setup
- [`runner.py`](./runner.py): TestRunner class and test execution logic
- [`discovery.py`](./discovery.py): Test discovery functions
- [`result.py`](./result.py): Custom TestResult class for result handling
- [`environment.py`](./environment.py): Test environment setup and teardown

## Example

```python
from frappe.testing import TestConfig, TestRunner, discover_all_tests

config = TestConfig(failfast=True, verbose=2)
runner = TestRunner(cfg=config)
discover_all_tests(['my_app'], runner)
runner.run()
```

For more detailed information about each component and its functionality, please refer to the docstrings and comments in the respective files.
