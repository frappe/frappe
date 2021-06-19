from typing import List, TypeVar, TYPE_CHECKING
from typing_extensions import Literal  # Literal is not in stdlib for 3.7


if TYPE_CHECKING:
	from frappe.model.document import Document


# List type docfields, actual defined by the docfield but always subclass of `Document`
# i.e. `Table[int]` isn't allowed but `Table[Item]` is.
D = TypeVar("D", bound="Document")
Table = List[D]
TableMultiSelect = List[D]

Select = Literal  # options to be defined by actual docfield.
Check = Literal[0, 1]
Rating = Literal[0, 1, 2, 3, 4, 5]

# Type aliases for standard docfields.
Link = str
DynamicLink = str
Attach = str
AttachImage = str
Image = str
Date = str
DateTime = str
Barcode = str
Code = str
Html = str
Color = str
SmallText = str
LongText = str
Text = str
TextEditor = str
Markdown = str
Password = str
ReadOnly = str
Time = str

Integer = int
Duration = int

Currency = float
Float = float
Percent = float



# prevent `import *` from polluting namespace
__all__ = [
	"Table",
	"TableMultiSelect",
	"Select",
	"Check",
	"Rating",
	"Link",
	"DynamicLink",
	"Attach",
	"AttachImage",
	"Image",
	"Date",
	"DateTime",
	"Barcode",
	"Code",
	"Html",
	"Color",
	"SmallText",
	"LongText",
	"Text",
	"TextEditor",
	"Markdown",
	"Password",
	"ReadOnly",
	"Time",
	"Integer",
	"Duration",
	"Currency",
	"Float",
	"Percent",
]
