"""This file defines all frappe types."""

from datetime import date, datetime, time
from typing import Literal

# DocField types
Data = str
Text = str
Autocomplete = Data
Attach = Data
AttachImage = Data
Barcode = Data
Check = bool | int
Code = Text
Color = str
Currency = float
Date = str | date
Datetime = str | datetime
Duration = int
DynamicLink = Data
Float = float
HTMLEditor = Text
Int = int
JSON = Text
Link = Data
LongText = Text
MarkdownEditor = Text
Password = Data
Percent = float
Phone = Data
ReadOnly = Data
Rating = float
Select = Literal
SmallText = Text
TextEditor = Text
Time = str | time
Table = list
TableMultiSelect = list
