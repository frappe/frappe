from dataclasses import dataclass

NUMBER_FORMAT_MAP = {
	"#,###.##": (".", ",", 2),
	"#.###,##": (",", ".", 2),
	"# ###.##": (".", " ", 2),
	"# ###,##": (",", " ", 2),
	"#'###.##": (".", "'", 2),
	"#, ###.##": (".", ", ", 2),
	"#,##,###.##": (".", ",", 2),
	"#,###.###": (".", ",", 3),
	"#.###": ("", ".", 0),
	"#,###": ("", ",", 0),
	"#.########": (".", "", 8),
}


@dataclass
class NumberFormat:
	precision: int
	decimal_separator: str
	thousands_separator: str
	string: str

	@classmethod
	def from_string(cls, number_format: str) -> "NumberFormat":
		decimal_separator, thousands_separator, precision = NUMBER_FORMAT_MAP[number_format]
		return NumberFormat(
			precision=precision,
			decimal_separator=decimal_separator,
			thousands_separator=thousands_separator,
			string=number_format,
		)

	def __str__(self) -> str:
		return self.string
