// Copyright (c) 2017, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on("Letter Head", {
	setup(frm) {
		frm.get_field("instructions").html(INSTRUCTIONS);
	},

	refresh: function (frm) {
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
