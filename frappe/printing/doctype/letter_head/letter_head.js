// Copyright (c) 2017, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Letter Head", {
	setup(frm) {
		frm.get_field("instructions").html(INSTRUCTIONS);
	},

	refresh(frm) {
		frm.enable_save();
		frm.trigger("render_preview");

		if (!frappe.boot.developer_mode) {
			if (frm.is_new()) {
				frm.toggle_enable("standard", false);
			}

			if (!frm.is_new() && frm.doc.standard === "Yes") {
				frm.set_intro(__("Please duplicate this to make changes"));
				frm.set_read_only();
				frm.disable_save();
			}
		}

		frm.flag_public_attachments = true;
	},

	content: (frm) => frm.events.queue_preview(frm),
	footer: (frm) => frm.events.queue_preview(frm),
	custom_css: (frm) => frm.events.queue_preview(frm),
	source: (frm) => frm.events.queue_preview(frm),
	footer_source: (frm) => frm.events.queue_preview(frm),
	queue_preview(frm) {
		clearTimeout(frm._preview_timer);
		frm._preview_timer = setTimeout(() => frm.trigger("render_preview"), 600);
	},
	async render_preview(frm) {
		const field = frm.get_field("preview");
		const { source, footer_source, content, footer, custom_css } = frm.doc;
		const request = (frm._preview_request = (frm._preview_request || 0) + 1);
		if (!frm.has_perm("write") || (source !== "HTML" && footer_source !== "HTML")) {
			field.$wrapper.empty();
			return;
		}
		const out = await frappe.xcall("frappe.www.printview.get_letter_head_preview", {
			content: source === "HTML" ? content : null,
			footer: footer_source === "HTML" ? footer : null,
			css: custom_css,
		});
		if (request !== frm._preview_request) return;
		frappe.ui.show_print_preview(field, out);
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
<p>${__("In the PDF, these classes are filled in on every page:")}</p>
<pre>
<code>
&lt;span class="page"&gt;&lt;/span&gt; / &lt;span class="topage"&gt;&lt;/span&gt;
</code>
</pre>`;
