import base64
import binascii
import contextlib
import re
import uuid
from datetime import UTC, datetime
from urllib.parse import quote

from packaging.utils import canonicalize_name

import frappe
from frappe.utils.change_log import parse_github_url
from frappe.utils.sbom.collector import App, Inventory, Package
from frappe.utils.sbom.licenses import NOASSERTION, to_spdx_license

CHECKSUM_ALGORITHMS = {"sha1": "SHA1", "sha256": "SHA256", "sha384": "SHA384", "sha512": "SHA512"}
ID_PREFIXES = {"pypi": "PyPI", "npm": "npm"}


def to_spdx(inventory: Inventory, site: str) -> dict:
	"""Return the inventory as an SPDX 2.3 document, ready for JSON serialization."""
	ids = _SPDXIds()
	packages = [_app_package(app, ids) for app in inventory.apps]
	packages += [_dependency_package(package, ids) for package in inventory.packages]

	relationships = [_relationship("SPDXRef-DOCUMENT", "DESCRIBES", ids.get(app)) for app in inventory.apps]
	relationships += [
		_relationship(ids.get(d.dependent), "DEPENDS_ON", ids.get(d.dependency))
		for d in inventory.dependencies
	]

	return {
		"spdxVersion": "SPDX-2.3",
		"dataLicense": "CC0-1.0",
		"SPDXID": "SPDXRef-DOCUMENT",
		"name": f"SBOM for {site}",
		"documentNamespace": f"https://{site}/sbom/{uuid.uuid4()}",
		"creationInfo": {
			"created": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
			"creators": [f"Tool: frappe-{frappe.__version__}", f"Organization: {site}"],
		},
		"packages": packages,
		"relationships": relationships,
	}


class _SPDXIds:
	"""Give each app and package an SPDXID that is unique in the document."""

	def __init__(self):
		self.ids: dict[App | Package, str] = {}
		self.used: set[str] = set()

	def get(self, item: App | Package) -> str:
		if item not in self.ids:
			prefix = "App" if isinstance(item, App) else ID_PREFIXES[item.ecosystem]
			base = re.sub(r"[^A-Za-z0-9.-]", "-", f"SPDXRef-{prefix}-{item.name}-{item.version or ''}")
			spdx_id, suffix = base.rstrip("-"), 1
			while spdx_id in self.used:
				suffix += 1
				spdx_id = f"{base.rstrip('-')}-{suffix}"
			self.ids[item] = spdx_id
			self.used.add(spdx_id)
		return self.ids[item]


def _app_package(app: App, ids: _SPDXIds) -> dict:
	package = {
		"name": app.name,
		"SPDXID": ids.get(app),
		"downloadLocation": _vcs_location(app.repository_url, app.commit)
		or app.repository_url
		or NOASSERTION,
		"supplier": _actor("Organization", ", ".join(app.authors)),
		"primaryPackagePurpose": "APPLICATION",
		**_common_fields(app.version, app.license),
	}
	if app.description:
		package["description"] = app.description
	if purl := _github_purl(app.repository_url, app.commit):
		package["externalRefs"] = [_purl_ref(purl)]
	return package


def _dependency_package(package: Package, ids: _SPDXIds) -> dict:
	result = {
		"name": package.name,
		"SPDXID": ids.get(package),
		"downloadLocation": (
			package.download_url or _vcs_location(package.repository_url, package.commit) or NOASSERTION
		),
		"supplier": _actor("Person", package.author),
		"primaryPackagePurpose": "LIBRARY",
		"externalRefs": [_purl_ref(_github_purl(package.repository_url, package.commit) or _purl(package))],
		**_common_fields(package.version, package.license),
	}
	if checksums := _checksums(package.integrity):
		result["checksums"] = checksums
	if package.vendored_path:
		result["comment"] = f"Vendored at {package.vendored_path}"
	return result


def _common_fields(version, license) -> dict:
	license_declared, license_comments = to_spdx_license(license)
	fields = {
		"filesAnalyzed": False,
		"licenseConcluded": NOASSERTION,
		"licenseDeclared": license_declared,
		"copyrightText": NOASSERTION,
	}
	if version:
		fields["versionInfo"] = version
	if license_comments:
		fields["licenseComments"] = license_comments
	return fields


def _relationship(element: str, relationship_type: str, related_element: str) -> dict:
	return {
		"spdxElementId": element,
		"relationshipType": relationship_type,
		"relatedSpdxElement": related_element,
	}


def _actor(kind: str, name: str | None) -> str:
	"""Format an SPDX actor. `Name <email>` becomes `Name (email)`, the SPDX form."""
	if not name:
		return NOASSERTION
	name = re.sub(r"\s*<([^>]*)>", r" (\1)", " ".join(name.split())).strip()
	return f"{kind}: {name}"


def _vcs_location(repository_url: str | None, commit: str | None) -> str | None:
	if repository_url and commit:
		return f"git+{repository_url}@{commit}"
	return None


def _purl(package: Package) -> str:
	if package.ecosystem == "pypi":
		purl = f"pkg:pypi/{canonicalize_name(package.name)}"
	else:
		purl = f"pkg:npm/{quote(package.name, safe='/')}"
	return f"{purl}@{quote(package.version, safe='')}" if package.version else purl


def _github_purl(repository_url: str | None, commit: str | None) -> str | None:
	if not repository_url or not commit:
		return None
	owner, repo = parse_github_url(repository_url)
	return f"pkg:github/{owner}/{repo}@{commit}".lower() if owner else None


def _purl_ref(purl: str) -> dict:
	return {"referenceCategory": "PACKAGE-MANAGER", "referenceType": "purl", "referenceLocator": purl}


def _checksums(integrity: str | None) -> list[dict]:
	"""Convert a subresource integrity string, such as `sha512-<base64>`, to SPDX checksums."""
	checksums = []
	for item in (integrity or "").split():
		algorithm, _, digest = item.partition("-")
		if algorithm not in CHECKSUM_ALGORITHMS:
			continue
		with contextlib.suppress(binascii.Error):
			checksums.append(
				{
					"algorithm": CHECKSUM_ALGORITHMS[algorithm],
					"checksumValue": base64.b64decode(digest, validate=True).hex(),
				}
			)
	return checksums
