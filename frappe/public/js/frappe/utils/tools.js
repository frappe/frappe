// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

import showdown from "showdown";

frappe.provide("frappe.tools");

frappe.tools.downloadify = function (data, roles, title) {
	if (roles && roles.length && !has_common(roles, roles)) {
		frappe.msgprint(
			__("Export not allowed. You need {0} role to export.", [frappe.utils.comma_or(roles)])
		);
		return;
	}

	var filename = title + ".csv";
	var csv_data = frappe.tools.to_csv(data);
	var a = document.createElement("a");

	if ("download" in a) {
		// Used Blob object, because it can handle large files
		var blob_object = new Blob([csv_data], { type: "text/csv;charset=UTF-8" });
		a.href = URL.createObjectURL(blob_object);
		a.download = filename;
	} else {
		// use old method
		a.href = "data:attachment/csv," + encodeURIComponent(csv_data);
		a.download = filename;
		a.target = "_blank";
	}

	document.body.appendChild(a);
	a.click();

	document.body.removeChild(a);
};

const MD_ALLOWED_TAGS = new Set([
	"p",
	"br",
	"hr",
	"h1",
	"h2",
	"h3",
	"h4",
	"h5",
	"h6",
	"ul",
	"ol",
	"li",
	"blockquote",
	"pre",
	"code",
	"em",
	"strong",
	"del",
	"b",
	"i",
	"a",
	"img",
	"table",
	"thead",
	"tbody",
	"tr",
	"th",
	"td",
]);
const MD_SAFE_URL = /^(https?:|mailto:|tel:|#|\/(?!\/))/i;
const MD_SAFE_IMG_SRC = /^(https?:|\/(?!\/)|data:image\/)/i;
const MD_SAFE_ALIGN = /^text-align:\s*(left|right|center|justify);?$/i;

// Whitelist-sanitize markdown-generated HTML to prevent XSS (showdown does not sanitize).
function sanitize_markdown_html(html) {
	const doc = new DOMParser().parseFromString(html, "text/html");
	(function walk(node) {
		for (const el of [...node.children]) {
			const tag = el.tagName.toLowerCase();
			walk(el);
			if (!MD_ALLOWED_TAGS.has(tag)) {
				el.replaceWith(...el.childNodes);
				continue;
			}
			for (const attr of [...el.attributes]) {
				const name = attr.name.toLowerCase();
				const keep =
					name === "title" ||
					name === "alt" ||
					(tag === "a" && name === "href" && MD_SAFE_URL.test(attr.value)) ||
					(tag === "img" && name === "src" && MD_SAFE_IMG_SRC.test(attr.value)) ||
					((tag === "code" || tag === "pre") && name === "class") ||
					((tag === "th" || tag === "td") &&
						name === "style" &&
						MD_SAFE_ALIGN.test(attr.value));
				if (!keep) el.removeAttribute(attr.name);
			}
			if (tag === "a") {
				const href = el.getAttribute("href") || "";
				if (href && !href.startsWith("#")) {
					el.setAttribute("target", "_blank");
					el.setAttribute("rel", "noopener noreferrer");
				}
			}
		}
	})(doc.body);
	return doc.body.innerHTML;
}

frappe.markdown = function (txt) {
	if (!frappe.md2html) {
		frappe.md2html = new showdown.Converter({ tables: true });
	}

	while (txt.substr(0, 1) === "\n") {
		txt = txt.substr(1);
	}

	// remove leading tab (if they exist in the first line)
	var whitespace_len = 0,
		first_line = txt.split("\n")[0];

	while (["\n", "\t"].indexOf(first_line.substr(0, 1)) !== -1) {
		whitespace_len++;
		first_line = first_line.substr(1);
	}

	if (whitespace_len && whitespace_len != first_line.length) {
		var txt1 = [];
		$.each(txt.split("\n"), function (i, t) {
			txt1.push(t.substr(whitespace_len));
		});
		txt = txt1.join("\n");
	}

	return sanitize_markdown_html(frappe.md2html.makeHtml(txt));
};

frappe.tools.to_csv = function (data) {
	var res = [];
	$.each(data, function (i, row) {
		row = $.map(row, function (col) {
			if (col === null || col === undefined) col = "";
			return typeof col === "string"
				? '"' + $("<i>").html(col.replace(/"/g, '""')).text() + '"'
				: col;
		});
		res.push(row.join(","));
	});
	return res.join("\n");
};
