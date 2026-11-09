from packaging.licenses import InvalidLicenseExpression, canonicalize_license_expression

from frappe.utils.sbom.collector import License

NOASSERTION = "NOASSERTION"

# Only classifiers that name one exact license. "BSD License" or "Apache Software License"
# do not tell the variant or the version, so they stay NOASSERTION.
CLASSIFIERS = {
	"License :: CC0 1.0 Universal (CC0 1.0) Public Domain Dedication": "CC0-1.0",
	"License :: OSI Approved :: Boost Software License 1.0 (BSL-1.0)": "BSL-1.0",
	"License :: OSI Approved :: Eclipse Public License 2.0 (EPL-2.0)": "EPL-2.0",
	"License :: OSI Approved :: European Union Public Licence 1.2 (EUPL 1.2)": "EUPL-1.2",
	"License :: OSI Approved :: GNU Affero General Public License v3": "AGPL-3.0-only",
	"License :: OSI Approved :: GNU Affero General Public License v3 or later (AGPLv3+)": "AGPL-3.0-or-later",
	"License :: OSI Approved :: GNU General Public License v2 (GPLv2)": "GPL-2.0-only",
	"License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)": "GPL-2.0-or-later",
	"License :: OSI Approved :: GNU General Public License v3 (GPLv3)": "GPL-3.0-only",
	"License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)": "GPL-3.0-or-later",
	"License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)": "LGPL-3.0-only",
	"License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)": "LGPL-3.0-or-later",
	"License :: OSI Approved :: Historical Permission Notice and Disclaimer (HPND)": "HPND",
	"License :: OSI Approved :: ISC License (ISCL)": "ISC",
	"License :: OSI Approved :: MIT License": "MIT",
	"License :: OSI Approved :: MIT No Attribution License (MIT-0)": "MIT-0",
	"License :: OSI Approved :: Mozilla Public License 1.1 (MPL 1.1)": "MPL-1.1",
	"License :: OSI Approved :: Mozilla Public License 2.0 (MPL 2.0)": "MPL-2.0",
	"License :: OSI Approved :: Python Software Foundation License": "PSF-2.0",
	"License :: OSI Approved :: The Unlicense (Unlicense)": "Unlicense",
	"License :: OSI Approved :: Universal Permissive License (UPL)": "UPL-1.0",
	"License :: OSI Approved :: zlib/libpng License": "Zlib",
}


def to_spdx_license(license: License) -> tuple[str, str | None]:
	"""Return a valid SPDX license expression, or NOASSERTION and the raw license text.

	A package with more than one license classifier stays NOASSERTION, because the
	classifiers do not tell if the licenses apply together or as a choice.
	"""
	if expression := _canonicalize(license.expression) or _canonicalize(license.text):
		return expression, None

	if len(license.classifiers) == 1 and (expression := CLASSIFIERS.get(license.classifiers[0])):
		return expression, None

	raw = "\n".join(filter(None, (license.expression, *license.classifiers, license.text)))
	return NOASSERTION, raw or None


def _canonicalize(expression: str | None) -> str | None:
	if not expression:
		return None
	try:
		return canonicalize_license_expression(expression)
	except InvalidLicenseExpression:
		return None
