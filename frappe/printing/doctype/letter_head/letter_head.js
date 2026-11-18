// Copyright (c) 2017, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Letter Head", {
	setup(frm) {
		frm.get_field("instructions").html(INSTRUCTIONS);
	},

	refresh: function (frm) {
		frm.flag_public_attachments = true;

		if (!frm.is_new()) {
			frm.add_custom_button(__("Preview"), () => preview_letter_head(frm));
		}
	},

	validate: (frm) => {
		["header_script", "footer_script"].forEach((field) => {
			if (!frm.doc[field]) return;

			try {
				eval(frm.doc[field]);
			} catch (e) {
				frappe.throw({
					title: __("Error in Header/Footer Script"),
					indicator: "orange",
					message: '<pre class="small"><code>' + e.stack + "</code></pre>",
				});
			}
		});
	},
});

function preview_letter_head(frm) {
	if (frm.is_dirty()) {
		frappe.msgprint(__("Save the Letter Head to preview your changes."));
		return;
	}
	frappe.call({
		method: "frappe.utils.print_format.render_letterhead_for_print",
		args: { letterhead: frm.doc.name },
		callback: ({ message }) => {
			const { header = "", footer = "" } = message || {};
			const print_css = frappe.assets.bundled_asset("print.bundle.css");
			const print_style = (frappe.boot.print_css || "").replace(/<\//g, "<\\/");
			const dialog = new frappe.ui.Dialog({
				title: __("Preview"),
				size: "extra-large",
				fields: [{ fieldtype: "HTML", fieldname: "preview" }],
			});
			const $iframe = $(`<iframe class="letter-head-preview" sandbox=""></iframe>`);
			$iframe[0].srcdoc = `<!DOCTYPE html>
<html>
	<head>
		<link href="${frappe.urllib.get_base_url()}${print_css}" rel="stylesheet">
		<style>${print_style}</style>
		<style>
			.print-format { display: flex; flex-direction: column; }
			.letter-head-footer { margin-top: auto; }
		</style>
	</head>
	<body>
		<div class="print-format">
			<div class="letter-head">${header}</div>
			<div class="letter-head-footer">${footer}</div>
		</div>
	</body>
</html>`;
			dialog.fields_dict.preview.$wrapper.append($iframe);
			dialog.show();
		},
	});
}

const INSTRUCTIONS = `<h4>${__("Letter Head Scripts")}</h4>
<p>${__("Header/Footer scripts can be used to add dynamic behaviours.")}</p>
<pre>
<code>
// ${__(
	"The following Header Script will add the current date to an element in 'Header HTML' with class 'header-content'"
)}
var el = document.getElementsByClassName("header-content");
if (el.length > 0) {
	el[0].textContent += " " + new Date().toGMTString();
}
</code>
</pre>
<p>${__("You can also access wkhtmltopdf variables (valid only in PDF print):")}</p>
<pre>
<code>
// ${__("Get Header and Footer wkhtmltopdf variables")}
// ${__("Snippet and more variables:  {0}", ["https://wkhtmltopdf.org/usage/wkhtmltopdf.txt"])}
var vars = {};
var query_strings_from_url = document.location.search.substring(1).split('&');
for (var query_string in query_strings_from_url) {
	if (query_strings_from_url.hasOwnProperty(query_string)) {
		var temp_var = query_strings_from_url[query_string].split('=', 2);
		vars[temp_var[0]] = decodeURI(temp_var[1]);
	}
}
var el = document.getElementsByClassName("header-content");
if (el.length > 0 && vars["page"] == 1) {
	el[0].textContent += " : " + vars["date"];
}
</code>
</pre>`;
