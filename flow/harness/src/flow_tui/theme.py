"""Base16 palette shared by the Textual theme and the Pygments syntax style."""

from pygments.style import Style
from pygments.token import (
	Comment,
	Error,
	Generic,
	Keyword,
	Literal,
	Name,
	Number,
	Operator,
	String,
	Token,
)
from rich.syntax import PygmentsSyntaxTheme
from textual.theme import Theme

BASE16 = {
	"base00": "#171717",
	"base01": "#1f1f1f",
	"base02": "#292929",
	"base03": "#575757",
	"base04": "#7a7a7a",
	"base05": "#d9d9d9",
	"base06": "#f8f8f8",
	"base07": "#ffffff",
	"base08": "#76bef9",
	"base09": "#c993ef",
	"base0A": "#7dc5a2",
	"base0B": "#f4c25f",
	"base0C": "#ff7575",
	"base0D": "#51decf",
	"base0E": "#fa8a40",
	"base0F": "#575757",
}

# The espresso overrides move hues around inside base08..base0F, so the UI reads
# its accents from these names instead of assuming the base16 slot conventions.
_RED = "#ff7575"
_GREEN = "#7dc5a2"
_YELLOW = "#f4c25f"
_BLUE = "#76bef9"
_TEAL = "#51decf"
_ORANGE = "#fa8a40"
_GREY_FG = "#575757"
_GREY_FG2 = "#7a7a7a"
_ONE_BG3 = "#383838"
_LINE = "#2e2e2e"
_STATUSLINE_BG = "#1e1e1e"

flow_theme = Theme(
	name="flow-base16",
	dark=True,
	background=BASE16["base00"],
	surface=BASE16["base01"],
	panel=_STATUSLINE_BG,
	foreground=BASE16["base05"],
	primary=_TEAL,
	secondary=_BLUE,
	accent=_ORANGE,
	success=_GREEN,
	warning=_YELLOW,
	error=_RED,
	variables={
		"border": _ONE_BG3,
		"border-blurred": _LINE,
		"text-muted": _GREY_FG2,
		"text-disabled": _GREY_FG,
		"block-cursor-foreground": BASE16["base00"],
		"block-cursor-background": _TEAL,
		"input-cursor-background": _TEAL,
		"input-cursor-foreground": BASE16["base00"],
		"input-selection-background": f"{_BLUE} 30%",
		"scrollbar": _ONE_BG3,
		"scrollbar-hover": BASE16["base03"],
		"scrollbar-active": _TEAL,
		"footer-key-foreground": _TEAL,
	},
)


# Rich renderables (`Text`, `Syntax`) bypass the Textual stylesheet, so they cannot read
# `$variables`; these named styles keep them on the same palette as styles.tcss.
STYLE_MUTED = _GREY_FG2
STYLE_THINKING = f"italic {_GREY_FG2}"
STYLE_ERROR = _RED
STYLE_ERROR_STRONG = f"bold {_RED}"
STYLE_RUNNING = _YELLOW
STYLE_TOOL_NAME = f"bold {_BLUE}"


class Base16Style(Style):
	"""Pygments style used by `rich.syntax.Syntax`; Rich has no base16 support itself."""

	name = "flow-base16"
	background_color = BASE16["base00"]
	highlight_color = BASE16["base02"]
	line_number_color = BASE16["base03"]
	line_number_background_color = BASE16["base00"]

	styles = {  # noqa: RUF012 — pygments reads this as a plain class attribute
		Token: BASE16["base05"],
		Comment: f"italic {BASE16['base03']}",
		Comment.Preproc: BASE16["base0E"],
		Keyword: BASE16["base0E"],
		Keyword.Type: BASE16["base0A"],
		Operator: BASE16["base05"],
		Operator.Word: BASE16["base0E"],
		Name.Builtin: BASE16["base0D"],
		Name.Function: BASE16["base0D"],
		Name.Class: BASE16["base0A"],
		Name.Namespace: BASE16["base0A"],
		Name.Exception: BASE16["base0C"],
		Name.Variable: BASE16["base08"],
		Name.Constant: BASE16["base09"],
		Name.Attribute: BASE16["base08"],
		Name.Tag: BASE16["base0A"],
		Name.Decorator: BASE16["base0C"],
		Number: BASE16["base09"],
		Literal: BASE16["base09"],
		String: BASE16["base0B"],
		String.Escape: BASE16["base0C"],
		String.Regex: BASE16["base0C"],
		String.Symbol: BASE16["base09"],
		Error: f"bg:{BASE16['base08']} {BASE16['base00']}",
		Generic.Deleted: BASE16["base0C"],
		Generic.Inserted: BASE16["base0A"],
		Generic.Heading: f"bold {BASE16['base0D']}",
		Generic.Subheading: f"bold {BASE16['base0D']}",
		Generic.Emph: f"italic {BASE16['base05']}",
		Generic.Strong: f"bold {BASE16['base05']}",
		Generic.Prompt: BASE16["base04"],
		Generic.Error: BASE16["base0C"],
		Generic.Traceback: BASE16["base0C"],
	}


SYNTAX_THEME = PygmentsSyntaxTheme(Base16Style)
