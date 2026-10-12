from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from frappe.tests.utils.test_capabilities import TestService


@dataclass
class TestConfig:
	"""Configuration class for test runner"""

	profile: bool = False
	failfast: bool = False
	tests: tuple = ()
	case: str | None = None
	pdb_on_exceptions: tuple | None = None
	selected_categories: list[str] = field(default_factory=list)
	skip_before_tests: bool = False
	test_service: "TestService | None" = None


@dataclass
class TestParameters:
	site: str | None = None
	app: str | None = None
	module: str | None = None
	doctype: str | None = None
	module_def: str | None = None
	verbose: bool = False
	tests: tuple = ()
	force: bool = False
	profile: bool = False
	junit_xml_output: str | None = None
	doctype_list_path: str | None = None
	failfast: bool = False
	case: str | None = None
	test_service: "TestService | None" = None
