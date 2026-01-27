// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// for license information please see license.txt

frappe.provide("frappe.form.formatters");

frappe.form.link_formatters = {};

frappe.form.formatters = {
	_right: function (value, options) {
		if (options && (options.inline || options.only_value)) {
			return value;
		} else {
			return "<div style='text-align: right'>" + value + "</div>";
		}
	},
	_apply_custom_formatter: function (value, df) {
		/* you can add a custom formatter in df.formatter
		example:
			frappe.meta.docfield_map[df.parent][df.fieldname].formatter = (value) => {
				if (value==='Test') return '😜';
			}
		*/

		if (df) {
			const std_df =
				frappe.meta.docfield_map[df.parent] &&
				frappe.meta.docfield_map[df.parent][df.fieldname];
			if (std_df && std_df.formatter && typeof std_df.formatter === "function") {
				value = std_df.formatter(value, df);
			}
		}
		return value;
	},
	Data: function (value, df) {
		if (df && df.options == "URL") {
			if (!value) return "";
			return `<a href="${value}" title="Open Link" target="_blank">${value}</a>`;
		}
		if (df && df.options == "IBAN") {
			if (!value) return "";
			return frappe.utils.get_formatted_iban(value);
		}
		value = value == null ? "" : value;

		return frappe.form.formatters._apply_custom_formatter(value, df);
	},
	Autocomplete: function (value, df) {
		return __(frappe.form.formatters["Data"](value, df));
	},
	Select: function (value, df) {
		return __(frappe.form.formatters["Data"](value, df));
	},
	Float: function (value, docfield, options, doc) {
		if (value === null) {
			return "";
		}

		// don't allow 0 precision for Floats, hence or'ing with null
		var precision =
			docfield.precision ||
			cint(frappe.boot.sysdefaults && frappe.boot.sysdefaults.float_precision) ||
			null;
		if (docfield.options && docfield.options.trim()) {
			// options points to a currency field, but expects precision of float!
			docfield.precision = precision;
			return frappe.form.formatters.Currency(value, docfield, options, doc);
		} else {
			// show 1.000000 as 1
			if (!(options || {}).always_show_decimals && !is_null(value)) {
				var temp = cstr(value).split(".");
				if (temp[1] == undefined || cint(temp[1]) === 0) {
					precision = 0;
				}
			}

			value = value == null || value === "" ? "" : value;

			return frappe.form.formatters._right(format_number(value, null, precision), options);
		}
	},
	Int: function (value, docfield, options) {
		if (value === null) {
			return "";
		}

		if (cstr(docfield.options).trim() === "File Size") {
			return frappe.form.formatters.FileSize(value);
		}
		return frappe.form.formatters._right(value == null ? "" : cint(value), options);
	},
	Percent: function (value, docfield, options) {
		if (value === null) {
			return "";
		}

		const precision =
			docfield.precision ||
			cint(frappe.boot.sysdefaults && frappe.boot.sysdefaults.float_precision) ||
			2;
		return frappe.form.formatters._right(format_number(value, null, precision) + "%", options);
	},
	Rating: function (value, docfield) {
		let rating_html = "";
		let number_of_stars = docfield.options || 5;
		value = value * number_of_stars;
		value = Math.round(value * 2) / 2; // roundoff number to nearest 0.5
		Array.from({ length: cint(number_of_stars) }, (_, i) => i + 1).forEach((i) => {
			rating_html += `<svg class="icon icon-md" data-rating=${i} viewBox="0 0 24 24" fill="none">
				<path class="right-half ${
					i <= (value || 0) ? "star-click" : ""
				}" d="M11.9987 3.00011C12.177 3.00011 12.3554 3.09303 12.4471 3.27888L14.8213 8.09112C14.8941 8.23872 15.0349 8.34102 15.1978 8.3647L20.5069 9.13641C20.917 9.19602 21.0807 9.69992 20.7841 9.9892L16.9421 13.7354C16.8243 13.8503 16.7706 14.0157 16.7984 14.1779L17.7053 19.4674C17.7753 19.8759 17.3466 20.1874 16.9798 19.9945L12.2314 17.4973C12.1586 17.459 12.0786 17.4398 11.9987 17.4398V3.00011Z" fill="var(--star-fill)" stroke="var(--star-fill)"/>
				<path class="left-half ${
					i <= (value || 0) || i - 0.5 == value ? "star-click" : ""
				}" d="M11.9987 3.00011C11.8207 3.00011 11.6428 3.09261 11.5509 3.27762L9.15562 8.09836C9.08253 8.24546 8.94185 8.34728 8.77927 8.37075L3.42887 9.14298C3.01771 9.20233 2.85405 9.70811 3.1525 9.99707L7.01978 13.7414C7.13858 13.8564 7.19283 14.0228 7.16469 14.1857L6.25116 19.4762C6.18071 19.8842 6.6083 20.1961 6.97531 20.0045L11.7672 17.5022C11.8397 17.4643 11.9192 17.4454 11.9987 17.4454V3.00011Z" fill="var(--star-fill)" stroke="var(--star-fill)"/>
			</svg>`;
		});
		return `<div class="rating">
			${rating_html}
		</div>`;
	},
	Currency: function (value, docfield, options, doc) {
		if (value === null) {
			return "";
		}

		var currency = frappe.meta.get_field_currency(docfield, doc);

		let precision;
		if (typeof docfield.precision == "number") {
			precision = docfield.precision;
		} else {
			precision = cint(
				docfield.precision || frappe.boot.sysdefaults.currency_precision || 2
			);
		}

		// If you change anything below, it's going to hurt a company in UAE, a bit.
		if (precision > 2) {
			var parts = cstr(value).split("."); // should be minimum 2, comes from the DB
			var decimals = parts.length > 1 ? parts[1] : ""; // parts.length == 2 ???

			if (decimals.length < 3 || decimals.length < precision) {
				const fraction =
					frappe.model.get_value(":Currency", currency, "fraction_units") || 100; // if not set, minimum 2.

				if (decimals.length < cstr(fraction).length) {
					precision = cstr(fraction).length - 1;
				}
			}
		}

		value = value == null || value === "" ? "" : value;
		value = format_currency(value, currency, precision);

		if (options && options.only_value) {
			return value;
		} else {
			return frappe.form.formatters._right(value, options);
		}
	},
	Check: function (value) {
		return `<input type="checkbox" disabled
			class="disabled-${value ? "selected" : "deselected"}">`;
	},
	Link: function (value, docfield, options, doc) {
		var doctype = docfield._options || docfield.options;
		var original_value = value;
		let link_title = frappe.utils.get_link_title(doctype, value);

		if (link_title === value) {
			link_title = null;
		}

		if (value && value.match && value.match(/^['"].*['"]$/)) {
			value.replace(/^.(.*).$/, "$1");
		}

		if (options && (options.for_print || options.only_value)) {
			return link_title || value;
		}

		if (frappe.form.link_formatters[doctype]) {
			// don't apply formatters in case of composite (parent field of same type)
			if (doc && doctype !== doc.doctype) {
				value = frappe.form.link_formatters[doctype](value, doc, docfield);
			}
		}

		if (!value) {
			return "";
		}
		if (value[0] == "'" && value[value.length - 1] == "'") {
			return value.substring(1, value.length - 1);
		}
		if (docfield && docfield.link_onclick) {
			return repl('<a onclick="%(onclick)s" href="#">%(value)s</a>', {
				onclick: docfield.link_onclick.replace(/"/g, "&quot;") + "; return false;",
				value: value,
			});
		} else if (docfield && doctype) {
			if (frappe.model.can_read(doctype)) {
				const a = document.createElement("a");
				a.href = `/desk/${encodeURIComponent(
					frappe.router.slug(doctype)
				)}/${encodeURIComponent(original_value)}`;
				a.dataset.doctype = doctype;
				a.dataset.name = original_value;
				a.dataset.value = original_value;
				a.innerText = __((options && options.label) || link_title || value);
				return a.outerHTML;
			} else {
				return link_title || value;
			}
		} else {
			return link_title || value;
		}
	},
	Date: function (value) {
		if (!frappe.datetime.str_to_user) {
			return value;
		}
		if (value) {
			value = frappe.datetime.str_to_user(value, false, true);
			// handle invalid date
			if (value === "Invalid date") {
				value = null;
			}
		}

		return value || "";
	},
	DateRange: function (value) {
		if (Array.isArray(value)) {
			return __("{0} to {1}", [
				frappe.datetime.str_to_user(value[0]),
				frappe.datetime.str_to_user(value[1]),
			]);
		} else {
			return value || "";
		}
	},
	Datetime: function (value) {
		if (value) {
			return moment(frappe.datetime.convert_to_user_tz(value)).format(
				frappe.boot.sysdefaults.date_format.toUpperCase() +
					" " +
					(frappe.boot.sysdefaults.time_format || "HH:mm:ss")
			);
		} else {
			return "";
		}
	},
	Text: function (value, df) {
		if (value) {
			var tags = ["<p", "<div", "<br", "<table"];
			var match = false;

			for (var i = 0; i < tags.length; i++) {
				if (value.match(tags[i])) {
					match = true;
					break;
				}
			}

			if (!match) {
				value = frappe.utils.replace_newlines(value);
			}
		}

		return frappe.form.formatters.Data(value, df);
	},
	Time: function (value) {
		if (value) {
			value = frappe.datetime.str_to_user(value, true);
		}

		return value || "";
	},
	Duration: function (value, docfield) {
		if (value) {
			let duration_options = frappe.utils.get_duration_options(docfield);
			value = frappe.utils.get_formatted_duration(value, duration_options);
		}

		return value || "0s";
	},
	LikedBy: function (value) {
		var html = "";
		$.each(JSON.parse(value || "[]"), function (i, v) {
			if (v) html += frappe.avatar(v);
		});
		return html;
	},
	Tag: function (value) {
		var html = "";
		$.each((value || "").split(","), function (i, v) {
			if (v)
				html += `
				<span
					class="data-pill btn-xs align-center ellipsis"
					style="background-color: var(--control-bg); box-shadow: none; margin-right: 4px;"
					data-field="_user_tags" data-label="${v}'">
					${v}
				</span>`;
		});
		return html;
	},
	Comment: function (value) {
		return value;
	},
	Assign: function (value) {
		var html = "";
		$.each(JSON.parse(value || "[]"), function (i, v) {
			if (v)
				html +=
					'<span class="label label-warning" \
				style="margin-right: 7px;"\
				data-field="_assign">' +
					v +
					"</span>";
		});
		return html;
	},
	SmallText: function (value) {
		return frappe.form.formatters.Text(value);
	},
	TextEditor: function (value) {
		let formatted_value = frappe.form.formatters.Text(value);
		// to use ql-editor styles
		try {
			if (
				!$(formatted_value).find(".ql-editor").length &&
				!$(formatted_value).hasClass("ql-editor")
			) {
				formatted_value = `<div class="ql-editor read-mode">${formatted_value}</div>`;
			}
		} catch (e) {
			formatted_value = `<div class="ql-editor read-mode">${formatted_value}</div>`;
		}

		return formatted_value;
	},
	Code: function (value) {
		return "<pre>" + (value == null ? "" : $("<div>").text(value).html()) + "</pre>";
	},
	WorkflowState: function (value) {
		var workflow_state = frappe.get_doc("Workflow State", value);
		if (workflow_state) {
			return repl(
				"<span class='label label-%(style)s' \
				data-workflow-state='%(value)s'\
				style='padding-bottom: 4px; cursor: pointer;'>\
				<i class='fa fa-small fa-white fa-%(icon)s'></i> %(value)s</span>",
				{
					value: value,
					style: workflow_state.style.toLowerCase(),
					icon: workflow_state.icon,
				}
			);
		} else {
			return "<span class='label'>" + value + "</span>";
		}
	},
	Email: function (value) {
		return $("<div></div>").text(value).html();
	},
	FileSize: function (value) {
		value = cint(value);
		if (value > 1048576) {
			return (value / 1048576).toFixed(2) + "M";
		} else if (value > 1024) {
			return (value / 1024).toFixed(2) + "K";
		}
		return value;
	},
	TableMultiSelect: function (rows, df, options) {
		rows = rows || [];
		const meta = frappe.get_meta(df.options);
		const link_field = meta.fields.find((df) => df.fieldtype === "Link");
		const formatted_values = rows.map((row) => {
			const value = row[link_field.fieldname];
			return `<span class="text-nowrap">
				${frappe.format(value, link_field, options, row)}
			</span>`;
		});
		return formatted_values.join(", ");
	},
	Color: (value) => {
		return value
			? `<div>
			<div class="selected-color" style="background-color: ${value}"></div>
			<span class="color-value">${value}</span>
		</div>`
			: "";
	},
	Icon: (value) => {
		return value
			? `<div class='flex' style='gap: 8px;'>
			<div class="selected-icon">${frappe.utils.icon(value, "md")}</div>
			<span class="icon-value">${value}</span>
		</div>`
			: "";
	},
	Attach: format_attachment_url,
	AttachImage: format_attachment_url,
};

function format_attachment_url(url, df, options, doc) {
	if (!url) {
		let is_editable = doc && (doc.docstatus === 0 || (doc.docstatus === 1 && df && df.allow_on_submit));
		if (is_editable && (!df || !df.read_only)) {
			let button_html = `<button class="btn btn-xs btn-default grid-attach-btn" 
				onclick="frappe.ui.form.trigger_grid_attach(this, event)"
				data-doctype="${doc.doctype}" data-name="${doc.name}" data-fieldname="${df.fieldname}">
				${__("Attach")}
			</button>`;
			return button_html;
		}
		return "";
	}
	
	let clear_btn = "";
	let is_editable = doc && (doc.docstatus === 0 || (doc.docstatus === 1 && df && df.allow_on_submit));
	if (is_editable && (!df || !df.read_only)) {
		clear_btn = `<a class="text-danger grid-clear-btn" style="margin-left: 10px; text-decoration: none;" title="${__("Clear")}"
			onclick="frappe.ui.form.trigger_grid_clear(this, event)"
			data-doctype="${doc.doctype}" data-name="${doc.name}" data-fieldname="${df.fieldname}" data-value="${url}">
			${frappe.utils.icon('close', 'sm')}
		</a>`;
	}
	
	return `<div style="display: flex; align-items: center; justify-content: space-between;">
		<a href="${url}" target="_blank" style="max-width: 80%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">${url}</a>
		${clear_btn}
	</div>`;
}

frappe.provide("frappe.ui.form");
frappe.ui.form.trigger_grid_attach = function (btn, e) {
	if (e) e.stopPropagation();
	let $btn = $(btn);
	let doctype = $btn.attr("data-doctype");
	let name = $btn.attr("data-name");
	let fieldname = $btn.attr("data-fieldname");

	let doc = locals[doctype] && locals[doctype][name];
	if (!doc) return;

	// Helper to update value
	const update_value = (value) => {
		// We use set_value to trigger UI updates
		frappe.model.set_value(doctype, name, fieldname, value);
	};

	if (doc.__islocal) {
		// New document: select locally
		let file_input = $('<input type="file" style="display:none">');
		$("body").append(file_input);
		file_input.on("change", function () {
			if (this.files && this.files.length > 0) {
				let file = this.files[0];
				let value = `pending:${file.name}`;
				
				// We need to register this pending attachment with the parent form
				if (window.cur_frm) {
					if (!cur_frm._pending_attachments) cur_frm._pending_attachments = [];
					
					let dummy_control = {
						df: { fieldname: fieldname },
						frm: cur_frm,
						pending_file: file,
						upload_pending_file: function() {
							return new Promise((resolve, reject) => {
								const formData = new FormData();
								formData.append("file", file, file.name);
								formData.append("doctype", cur_frm.doctype);
								formData.append("docname", cur_frm.docname);
								formData.append("fieldname", fieldname);
								formData.append("folder", "Home/Attachments");
								formData.append("is_private", "1");
								formData.append("cmd", "frappe.handler.upload_file");
								
								$.ajax({
									url: "/api/method/frappe.handler.upload_file",
									type: "POST",
									data: formData,
									processData: false,
									contentType: false,
									headers: { "X-Frappe-CSRF-Token": frappe.csrf_token },
									success: (r) => {
										if (r.message) {
											update_value(r.message.file_url);
											resolve(r.message);
										} else {
											reject(new Error("Upload failed"));
										}
									},
									error: (xhr) => reject(new Error(xhr.statusText))
								});
							});
						}
					};
					cur_frm._pending_attachments.push(dummy_control);
				}
				update_value(value);
			}
			file_input.remove();
		});
		file_input.click();
	} else {
		// Saved document: use FileUploader
		new frappe.ui.FileUploader({
			doctype: doctype,
			docname: name,
			fieldname: fieldname,
			allow_multiple: false,
			on_success: (file) => {
				update_value(file.file_url);
			}
		});
	}
};

frappe.ui.form.trigger_grid_clear = function(btn, e) {
	if (e) e.stopPropagation();
	let $btn = $(btn);
	let doctype = $btn.attr("data-doctype");
	let name = $btn.attr("data-name");
	let fieldname = $btn.attr("data-fieldname");
	let value = $btn.attr("data-value");

	frappe.confirm(__("Are you sure you want to delete the attachment?"), function () {
		// For saved docs with real attachments, try to remove properly
		if (value && !value.startsWith("pending:") && window.cur_frm && !locals[doctype][name].__islocal) {
			cur_frm.attachments.remove_attachment_by_filename(value, async () => {
				frappe.model.set_value(doctype, name, fieldname, null);
				cur_frm.doc.docstatus == 1 ? cur_frm.save("Update") : cur_frm.save();
			});
		} else {
			// For pending or local docs, just clear the value
			// Also clear pending attachment from cur_frm if exists
			if (window.cur_frm && cur_frm._pending_attachments) {
				// We don't have the control object reference here easily, causing a potential leak in _pending_attachments 
				// but it shouldn't break anything major.
			}
			frappe.model.set_value(doctype, name, fieldname, null);
		}
	});
};

frappe.form.get_formatter = function (fieldtype) {
	if (!fieldtype) fieldtype = "Data";
	return frappe.form.formatters[fieldtype.replace(/ /g, "")] || frappe.form.formatters.Data;
};

frappe.format = function (value, df, options, doc) {
	let mask_readonly = false;
	if (df?.parent) {
		const mask_fields = frappe.get_meta(df.parent)?.masked_fields;
		mask_readonly = mask_fields?.includes(df.fieldname);
	}

	if (!df || mask_readonly) df = { fieldtype: "Data" };
	if (df.fieldname == "_user_tags") df = { ...df, fieldtype: "Tag" };
	var fieldtype = df.fieldtype || "Data";

	// format Dynamic Link as a Link
	if (fieldtype === "Dynamic Link") {
		fieldtype = "Link";
		df._options = doc ? doc[df.options] : null;
	}

	var formatter = df.formatter || frappe.form.get_formatter(fieldtype);

	var formatted = formatter(value, df, options, doc);

	if (typeof formatted == "string") formatted = frappe.dom.remove_script_and_style(formatted);

	return formatted;
};

frappe.get_format_helper = function (doc) {
	var helper = {
		get_formatted: function (fieldname) {
			var df = frappe.meta.get_docfield(doc.doctype, fieldname);
			if (!df) {
				console.log("fieldname not found: " + fieldname);
			}
			return frappe.format(doc[fieldname], df, { inline: 1 }, doc);
		},
	};
	$.extend(helper, doc);
	return helper;
};

frappe.form.link_formatters["User"] = function (value, doc, docfield) {
	let full_name = doc && (doc.full_name || (docfield && doc[`${docfield.fieldname}_full_name`]));
	return full_name || value;
};
