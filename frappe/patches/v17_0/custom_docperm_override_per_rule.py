import frappe
from frappe.permissions import add_rule_that_grants_nothing


def execute():
	"""Keep the permissions of DocTypes that have Custom DocPerm rows unchanged.

	A Custom DocPerm row now replaces only the standard rule with the same role and permlevel, instead of
	every standard rule of its DocType. For each standard rule without a Custom DocPerm row, add one that
	grants nothing, so that rule stays out of effect as before."""
	for doctype in get_doctypes_with_visible_custom_perms():
		preserve_effective_permissions(doctype)


def get_doctypes_with_visible_custom_perms() -> list[str]:
	return frappe.get_all(
		"Custom DocPerm",
		filters={"is_app_disabled": 0, "parent": ["is", "set"]},
		pluck="parent",
		distinct=True,
	)


def preserve_effective_permissions(doctype: str):
	standard_rules = get_rules("DocPerm", {"parent": doctype})
	customized_rules = get_rules("Custom DocPerm", {"parent": doctype, "is_app_disabled": 0})

	standard_rules_not_in_effect = standard_rules - customized_rules
	for role, permlevel in standard_rules_not_in_effect:
		add_rule_that_grants_nothing(doctype, role, permlevel)


def get_rules(perm_doctype: str, filters: dict) -> set[tuple[str, int]]:
	rules = set()
	for perm in frappe.get_all(perm_doctype, fields=["role", "permlevel"], filters=filters):
		rules.add((perm.role, perm.permlevel))

	return rules
