export function can_upload_public_files() {
	// If system setting is OFF → everyone can upload public files (old behaviour)
	if (Number(frappe.boot.sysdefaults?.only_system_managers_upload_public_files) !== 1) {
		return true;
	}
	// If system setting is ON → only System Manager / Administrator can upload public files
	return frappe.user.has_role(["System Manager", "Administrator"]);
}

// Expose globally for non-ES module scripts (e.g., file.js)
frappe.provide("frappe.file_utils");
frappe.file_utils.can_upload_public_files = can_upload_public_files;
