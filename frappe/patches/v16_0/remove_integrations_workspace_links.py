import frappe


def execute():
	labels_to_remove = {"Backup", "Dropbox Settings", "S3 Backup Settings", "Google Drive"}

	workspace = frappe.get_doc("Workspace", "Integrations")
	workspace.links = [link for link in workspace.links if link.label not in labels_to_remove]

	for idx, link in enumerate(workspace.links, start=1):
		link.idx = idx

	workspace.save()
