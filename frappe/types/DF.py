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
Geolocation = Text
HTMLEditor = Text
Icon = Data
Int = int
JSON = Text
Link = Data
LongInt = int
LongText = Text
MarkdownEditor = Text
Password = Data
Percent = float
Phone = Data
ReadOnly = Data
Rating = float
Select = Literal
Signature = Text
SmallText = Text
TextEditor = Text
Time = str | time
Table = list
TableMultiSelect = list
