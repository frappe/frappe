// Copyright (c) 2017, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Letter Head", {
	setup(frm) {
		frm.get_field("instructions").html(INSTRUCTIONS);

		["content", "footer"].forEach((fieldname) => {
			const field = frm.get_field(fieldname);
			field.preview_renderer = (value, $preview) =>
				render_letter_head_preview(frm, field, value, $preview);
		});
	},

	refresh(frm) {
		frm.enable_save();

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

async function render_letter_head_preview(frm, field, value, $preview) {
	if (frm.is_new()) {
		$preview.html(
			`<div class="text-muted p-3">${__("Save the Letter Head to preview it")}</div>`
		);
		return;
	}

	const request_id = (field.preview_request_id || 0) + 1;
	field.preview_request_id = request_id;
	$preview.html(`<div class="text-muted p-3">${__("Rendering preview...")}</div>`);

	try {
		const { message } = await frappe.call({
			method: "frappe.printing.doctype.letter_head.letter_head.render_preview",
			args: {
				letter_head: frm.doc.name,
				fieldname: field.df.fieldname,
				content: value,
			},
		});

		if (request_id !== field.preview_request_id) return;
		render_isolated_preview(message || "", $preview);
	} catch (error) {
		if (request_id !== field.preview_request_id) return;
		$preview.html(
			`<div class="text-danger p-3">${__("Unable to render Letter Head preview")}</div>`
		);
	}
}

function render_isolated_preview(value, $preview) {
	const iframe = document.createElement("iframe");
	iframe.setAttribute("sandbox", "allow-same-origin");
	iframe.setAttribute("referrerpolicy", "no-referrer");
	iframe.setAttribute("title", __("Letter Head Preview"));
	iframe.style.cssText = "width: 100%; min-height: 180px; border: 0; background: #fff;";

	iframe.addEventListener("load", () => {
		const resize = () => {
			const height = iframe.contentDocument?.documentElement?.scrollHeight || 180;
			iframe.style.height = `${Math.max(height, 180)}px`;
		};

		resize();
		iframe.contentDocument?.querySelectorAll("img").forEach((image) => {
			image.addEventListener("load", resize, { once: true });
		});
	});

	iframe.srcdoc = `<!doctype html>
		<html>
			<head>
				<base href="${window.location.origin}/">
				<style>html, body { margin: 0; padding: 0; }</style>
			</head>
			<body><div class="letter-head">${value}</div></body>
		</html>`;

	$preview.empty().append(iframe);
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
