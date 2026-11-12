import { __ } from "frappe/i18n";

const DOWNLOAD_VCARDS = "/api/v2/method/frappe.contacts.doctype.contact.contact.download_vcards";

export default {
	onRefresh(page) {
		page.bulkActions.add({
			name: "download_vcards",
			label: __("Download vCards"),
			icon: "lucide-id-card",
			run: (page) =>
				postDownload(DOWNLOAD_VCARDS, { contacts: JSON.stringify(page.selection) }),
		});
	},
};

// A form POST, so the browser saves the file the server sends back and a long selection fits.
function postDownload(url, values) {
	const form = document.createElement("form");
	form.action = url;
	form.method = "POST";
	form.style.display = "none";
	values = { ...values, csrf_token: globalThis.csrf_token };
	for (const [name, value] of Object.entries(values)) {
		const field = document.createElement("textarea");
		field.name = name;
		field.value = value;
		form.appendChild(field);
	}
	document.body.appendChild(form);
	form.submit();
	form.remove();
}
