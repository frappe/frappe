# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import base64
import datetime
import re
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Optional
from uuid import UUID

import uuid_utils

import frappe
from frappe import _
from frappe.model import log_types
from frappe.query_builder import DocType
from frappe.utils import cint, cstr, now_datetime

if TYPE_CHECKING:
	from frappe.model.document import Document
	from frappe.model.meta import Meta


NAMING_SERIES_PATTERN = re.compile(r"^[\w\- \/.#{}]+$", re.UNICODE)
BRACED_PARAMS_PATTERN = re.compile(r"(\{[\w | #]+\})")


# Types that can be using in naming series fields
NAMING_SERIES_PART_TYPES = (
	int,
	str,
	datetime.datetime,
	datetime.date,
	datetime.time,
	datetime.timedelta,
)


class InvalidNamingSeriesError(frappe.ValidationError):
	pass


class InvalidUUIDValue(frappe.ValidationError):
	pass


class NamingSeries:
	__slots__ = ("series",)

	def __init__(self, series: str) -> None:
		self.series = series

		# Add default number part if missing
		if "#" not in self.series:
			self.series += ".#####"

	def validate(self) -> None:
		if "." not in self.series:
			frappe.throw(
				_("Invalid naming series {}: dot (.) missing").format(frappe.bold(self.series)),
				exc=InvalidNamingSeriesError,
			)

		if not NAMING_SERIES_PATTERN.match(self.series):
			frappe.throw(
				_(
					"Special Characters except '-', '#', '.', '/', '{{' and '}}' not allowed in naming series {0}"
				).format(frappe.bold(self.series)),
				exc=InvalidNamingSeriesError,
			)

	def generate_next_name(self, doc: "Document", *, ignore_validate: bool = False) -> str:
		if not ignore_validate:
			self.validate()

		parts = self.series.split(".")
		return parse_naming_series(parts, doc=doc)

	def get_prefix(self) -> str:
		"""Naming series stores prefix to maintain a counter in DB. This prefix can be used to update counter or validations.

		e.g. `SINV-.YY.-.####` has prefix of `SINV-22-` in database for year 2022.
		"""

		prefix = None

		def fake_counter_backend(partial_series, digits):
			nonlocal prefix
			prefix = partial_series
			return "#" * digits

		# This function evaluates all parts till we hit numerical parts and then
		# sends prefix + digits to DB to find next number.
		# Instead of reimplementing the whole parsing logic in multiple places we
		# can just ask this function to give us the prefix.
		parse_naming_series(self.series, number_generator=fake_counter_backend)

		if prefix is None:
			frappe.throw(_("Invalid Naming Series: {}").format(self.series))

		return prefix

	def get_preview(self, doc=None) -> list[str]:
		"""Generate preview of naming series without using DB counters"""
		generated_names = []
		for count in range(1, 4):

			def fake_counter(_prefix, digits):
				# ignore B023: binding `count` is not necessary because
				# function is evaluated immediately and it can not be done
				# because of function signature requirement
				return str(count).zfill(digits)

			generated_names.append(parse_naming_series(self.series, doc=doc, number_generator=fake_counter))
		return generated_names

	def update_counter(self, new_count: int) -> None:
		"""Warning: Incorrectly updating series can result in unusable transactions"""
		Series = frappe.qb.DocType("Series")
		prefix = self.get_prefix()

		# Initialize if not present in DB
		if frappe.db.get_value("Series", prefix, "name", order_by="name") is None:
			frappe.qb.into(Series).insert(prefix, 0).columns("name", "current").run()

		(frappe.qb.update(Series).set(Series.current, cint(new_count)).where(Series.name == prefix)).run()

	def get_current_value(self) -> int:
		prefix = self.get_prefix()
		return cint(frappe.db.get_value("Series", prefix, "current", order_by="name"))


def set_new_name(doc) -> None:
	"""
	Sets the `name` property for the document based on various rules.

	1. If amended doc, set suffix.
	2. If `autoname` method is declared, then call it.
	3. If `autoname` property is set in the DocType (`meta`), then build it using the `autoname` property.
	4. If no rule defined, use hash.

	:param doc: Document to be named.
	"""

	doc.run_method("before_naming")

	meta = frappe.get_meta(doc.doctype)
	autoname = meta.autoname or ""

	if autoname.lower() not in ("prompt", "uuid") and not frappe.flags.in_import:
		doc.name = None

	if is_autoincremented(doc.doctype, meta):
		doc.name = frappe.db.get_next_sequence_val(doc.doctype)
		return

	if meta.autoname == "UUID":
		if not doc.name:
			doc.name = str(uuid_utils.uuid7())
		elif isinstance(doc.name, UUID | uuid_utils.UUID):
			doc.name = str(doc.name)
		elif isinstance(doc.name, str):  # validate
			try:
				UUID(doc.name)
			except ValueError:
				frappe.throw(_("Invalid value specified for UUID: {}").format(doc.name), InvalidUUIDValue)
		return

	if getattr(doc, "amended_from", None):
		_set_amended_name(doc)
		if doc.name:
			return

	elif getattr(doc.meta, "issingle", False):
		doc.name = doc.doctype

	if not doc.name:
		set_naming_from_document_naming_rule(doc)

	if not doc.name:
		doc.run_method("autoname")

	if not doc.name and autoname:
		set_name_from_naming_options(autoname, doc)

	# at this point, we fall back to name generation with the hash option
	if not doc.name:
		doc.name = make_autoname("hash", doc.doctype)

	doc.name = validate_name(doc.doctype, doc.name)


def is_autoincremented(doctype: str, meta: Optional["Meta"] = None) -> bool:
	"""Checks if the doctype has autoincrement autoname set"""

	if not meta:
		meta = frappe.get_meta(doctype)

	return not getattr(meta, "issingle", False) and meta.autoname == "autoincrement"


def set_name_from_naming_options(autoname, doc) -> None:
	"""
	Get a name based on the autoname field option
	"""

	_autoname = autoname.lower()

	if _autoname.startswith("field:"):
		doc.name = _field_autoname(autoname, doc)

		# if the autoname option is 'field:' and no name was derived, we need to
		# notify
		if not doc.name:
			fieldname = autoname[6:]
			frappe.throw(_("{0} is required").format(doc.meta.get_label(fieldname)))

	elif _autoname.startswith("naming_series:"):
		set_name_by_naming_series(doc)
	elif _autoname.startswith("prompt"):
		_prompt_autoname(autoname, doc)
	elif _autoname.startswith("format:"):
		doc.name = _format_autoname(autoname, doc)
	elif "#" in autoname:
		doc.name = make_autoname(autoname, doc=doc)


def set_naming_from_document_naming_rule(doc) -> None:
	"""
	Evaluate rules based on "Document Naming Series" doctype
	"""
	from frappe.model.base_document import DOCTYPES_FOR_DOCTYPE

	IGNORED_DOCTYPES = {*log_types, *DOCTYPES_FOR_DOCTYPE, "DefaultValue", "Patch Log"}

	if doc.doctype in IGNORED_DOCTYPES:
		return

	document_naming_rules = frappe.cache_manager.get_doctype_map(
		"Document Naming Rule",
		doc.doctype,
		filters={"document_type": doc.doctype, "disabled": 0},
		order_by="priority desc",
	)

	for d in document_naming_rules:
		frappe.get_cached_doc("Document Naming Rule", d.name).apply(doc)
		if doc.name:
			break


def set_name_by_naming_series(doc) -> None:
	"""Sets name by the `naming_series` property"""
	if not doc.naming_series:
		doc.naming_series = get_default_naming_series(doc.doctype)

	if not doc.naming_series:
		frappe.throw(frappe._("Naming Series mandatory"))

	doc.name = make_autoname(doc.naming_series + ".#####", "", doc)


def make_autoname(key: str = "", doctype: str = "", doc: str = "", *, ignore_validate: bool = False):
	"""
	     Creates an autoname from the given key:

	     **Autoname rules:**

	              * The key is separated by '.'
	              * '####' represents a series. The string before this part becomes the prefix:
	                     Example: ABC.#### creates a series ABC0001, ABC0002 etc
	              * 'MM' represents the current month
	              * 'YY' and 'YYYY' represent the current year


	*Example:*

	              * DE./.YY./.MM./.##### will create a series like
	                DE/09/01/00001 where 09 is the year, 01 is the month and 00001 is the series
	"""
	if key == "hash":
		# Makeshift "ULID": first 4 chars are based on timestamp, other 6 are random
		return _get_timestamp_prefix() + _generate_random_string(6)

	series = NamingSeries(key)
	return series.generate_next_name(doc, ignore_validate=ignore_validate)


def _get_timestamp_prefix():
	ts = int(time.time() * 10)  # time in deciseconds
	# we ~~don't need~~ can't get ordering over entire lifetime, so we wrap the time.
	ts = ts % (32**4)
	return base64.b32hexencode(ts.to_bytes(length=5, byteorder="big")).decode()[-4:].lower()


def _generate_random_string(length: int = 10):
	"""Better version of frappe.generate_hash for naming.

	This uses entire base32 instead of base16 used by generate_hash. So it has twice as many
	characters and hence more likely to have shorter common prefixes. i.e. slighly faster comparisons and less conflicts.

	Why not base36?
	It's not in standard library else using all characters is probably better approach.
	Why not base64?
	MySQL is case-insensitive, we can't use both upper and lower case characters.
	"""
	from secrets import token_bytes as get_random_bytes

	return base64.b32hexencode(get_random_bytes(length)).decode()[:length].lower()


def parse_naming_series(
	parts: list[str] | str,
	doctype=None,
	doc: Optional["Document"] = None,
	number_generator: Callable[[str, int], str] | None = None,
) -> str:
	"""Parse the naming series and get next name.

	args:
	        parts: naming series parts (split by `.`)
	        doc: document to use for series that have parts using fieldnames
	        number_generator: Use different counter backend other than `tabSeries`. Primarily used for testing.
	"""

	name = ""
	_sentinel = object()
	if isinstance(parts, str):
		parts = parts.split(".")

	if not number_generator:
		number_generator = getseries

	series_set = False
	today = now_datetime()
	for e in parts:
		if not e:
			continue

		part = ""
		if e.startswith("#"):
			if not series_set:
				digits = len(e)
				part = number_generator(name, digits)
				series_set = True
		elif e == "YY":
			part = today.strftime("%y")
		elif e == "MM":
			part = today.strftime("%m")
		elif e == "DD":
			part = today.strftime("%d")
		elif e == "YYYY":
			part = today.strftime("%Y")
		elif e == "WW":
			part = determine_consecutive_week_number(today)
		elif e == "timestamp":
			part = str(today)
		elif doc and (e.startswith("{") or doc.get(e, _sentinel) is not _sentinel):
			e = e.replace("{", "").replace("}", "")
			part = doc.get(e)
		elif method := has_custom_parser(e):
			part = frappe.get_attr(method[0])(doc, e)
		else:
			part = e

		if isinstance(part, str):
			name += part
		elif isinstance(part, NAMING_SERIES_PART_TYPES):
			name += cstr(part).strip()

	return name


def has_custom_parser(e):
	"""Return True if the naming series part has a custom parser."""
	return frappe.get_hooks("naming_series_variables", {}).get(e)


def determine_consecutive_week_number(datetime):
	"""Determines the consecutive calendar week"""
	m = datetime.month
	# ISO 8601 calandar week
	w = datetime.strftime("%V")
	# Ensure consecutiveness for the first and last days of a year
	if m == 1 and int(w) >= 52:
		w = "00"
	elif m == 12 and int(w) <= 1:
		w = "53"
	return w


def getseries(key, digits):
	# series created ?
	# Using frappe.qb as frappe.get_values does not allow order_by=None
	series = DocType("Series")
	current = (frappe.qb.from_(series).where(series.name == key).for_update().select("current")).run()

	if current and current[0][0] is not None:
		current = current[0][0]
		# yes, update it
		frappe.db.sql("UPDATE `tabSeries` SET `current` = `current` + 1 WHERE `name`=%s", (key,))
		current = cint(current) + 1
	else:
		# no, create it
		frappe.db.sql("INSERT INTO `tabSeries` (`name`, `current`) VALUES (%s, 1)", (key,))
		current = 1
	return ("%0" + str(digits) + "d") % current


def revert_series_if_last(key, name, doc=None) -> None:
	"""
	Reverts the series for particular naming series:
	* key is naming series		- SINV-.YYYY-.####
	* name is actual name		- SINV-2021-0001

	1. This function split the key into two parts prefix (SINV-YYYY) & hashes (####).
	2. Use prefix to get the current index of that naming series from Series table
	3. Then revert the current index.

	*For custom naming series:*
	1. hash can exist anywhere, if it exist in hashes then it take normal flow.
	2. If hash doesn't exit in hashes, we get the hash from prefix, then update name and prefix accordingly.

	*Example:*
	        1. key = SINV-.YYYY.-
	                * If key doesn't have hash it will add hash at the end
	                * prefix will be SINV-YYYY based on this will get current index from Series table.
	        2. key = SINV-.####.-2021
	                * now prefix = SINV-#### and hashes = 2021 (hash doesn't exist)
	                * will search hash in key then accordingly get prefix = SINV-
	        3. key = ####.-2021
	                * prefix = #### and hashes = 2021 (hash doesn't exist)
	                * will search hash in key then accordingly get prefix = ""
	"""
	if ".#" in key:
		prefix, hashes = key.rsplit(".", 1)
		if "#" not in hashes:
			# get the hash part from the key
			hash = re.search("#+", key)
			if not hash:
				return
			name = name.replace(hashes, "")
			prefix = prefix.replace(hash.group(), "")
	else:
		prefix = key

	if "." in prefix:
		prefix = parse_naming_series(prefix.split("."), doc=doc)

	count = cint(name.replace(prefix, ""))
	series = DocType("Series")
	current = (frappe.qb.from_(series).where(series.name == prefix).for_update().select("current")).run()

	if current and current[0][0] == count:
		frappe.db.sql("UPDATE `tabSeries` SET `current` = `current` - 1 WHERE `name`=%s", prefix)


def get_default_naming_series(doctype: str) -> str | None:
	"""get default value for `naming_series` property"""
	naming_series_options = frappe.get_meta(doctype).get_naming_series_options()

	# Return first truthy options
	# Empty strings are used to avoid populating forms by default
	for option in naming_series_options:
		if option:
			return option


def validate_name(doctype: str, name: int | str):
	if not name:
		frappe.throw(_("No Name Specified for {0}").format(doctype))

	if isinstance(name, int):
		if is_autoincremented(doctype):
			# this will set the sequence value to be the provided name/value and set it to be used
			# so that the sequence will start from the next value
			frappe.db.set_next_sequence_val(doctype, name, is_val_used=True)
			return name

		frappe.throw(_("Invalid name type (integer) for varchar name column"), frappe.NameError)

	if name.startswith("New " + doctype):
		frappe.throw(
			_("There were some errors setting the name, please contact the administrator"), frappe.NameError
		)
	name = name.strip()

	if not frappe.get_meta(doctype).get("issingle") and (doctype == name) and (name != "DocType"):
		frappe.throw(_("Name of {0} cannot be {1}").format(doctype, name), frappe.NameError)

	special_characters = "<>"
	if re.findall(f"[{special_characters}]+", name):
		message = ", ".join(f"'{c}'" for c in special_characters)
		frappe.throw(_("Name cannot contain special characters like {0}").format(message), frappe.NameError)

	return name


def append_number_if_name_exists(doctype, value, fieldname: str = "name", separator: str = "-", filters=None):
	if not filters:
		filters = dict()
	filters.update({fieldname: value})
	exists = frappe.db.exists(doctype, filters)

	regex = f"^{re.escape(value)}{separator}\\d+$"

	if exists:
		last = frappe.db.sql(
			f"""SELECT `{fieldname}` FROM `tab{doctype}`
			WHERE `{fieldname}` {frappe.db.REGEX_CHARACTER} %s
			ORDER BY length({fieldname}) DESC,
			`{fieldname}` DESC LIMIT 1""",
			regex,
		)

		if last:
			count = str(cint(last[0][0].rsplit(separator, 1)[1]) + 1)
		else:
			count = "1"

		value = f"{value}{separator}{count}"

	return value


def _set_amended_name(doc):
	amend_naming_rule = frappe.db.get_value(
		"Amended Document Naming Settings", {"document_type": doc.doctype}, "action", cache=True
	)
	if not amend_naming_rule:
		amend_naming_rule = frappe.db.get_single_value(
			"Document Naming Settings", "default_amend_naming", cache=True
		)

	if amend_naming_rule == "Default Naming":
		return

	am_id = 1
	am_prefix = doc.amended_from
	if frappe.db.get_value(doc.doctype, doc.amended_from, "amended_from"):
		am_id = cint(doc.amended_from.split("-")[-1]) + 1
		am_prefix = "-".join(doc.amended_from.split("-")[:-1])  # except the last hyphen

	doc.name = am_prefix + "-" + str(am_id)
	return doc.name


def _field_autoname(autoname, doc, skip_slicing=None):
	"""
	Generate a name using `DocType` field. This is called when the doctype's
	`autoname` field starts with 'field:'
	"""
	fieldname = autoname if skip_slicing else autoname[6:]
	return (cstr(doc.get(fieldname)) or "").strip()


def _prompt_autoname(autoname, doc) -> None:
	"""
	Generate a name using Prompt option. This simply means the user will have to set the name manually.
	This is called when the doctype's `autoname` field starts with 'prompt'.
	"""
	# set from __newname in save.py
	if not doc.name:
		frappe.throw(_("Please set the document name"))


def _format_autoname(autoname: str, doc):
	"""
	Generate autoname by replacing all instances of braced params (fields, date params ('DD', 'MM', 'YY'), series)
	Independent of remaining string or separators.

	Example pattern: 'format:LOG-{MM}-{fieldname1}-{fieldname2}-{#####}'
	"""

	first_colon_index = autoname.find(":")
	autoname_value = autoname[first_colon_index + 1 :]

	def get_param_value_for_match(match):
		param = match.group()
		return parse_naming_series([param[1:-1]], doc=doc)

	# Replace braced params with their parsed value
	name = BRACED_PARAMS_PATTERN.sub(get_param_value_for_match, autoname_value)

	return name
