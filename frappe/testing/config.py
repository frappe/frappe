from dataclasses import dataclass, field
from typing import Optional, Union


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
