// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// for license information please see license.txt

frappe.provide("frappe.form.formatters");

frappe.form.formatters = {
	_right: function(value, options) {
		if(options && options.inline) {
			return value;
		} else {
			return "<div style='text-align: right'>" + value + "</div>";
		}
	},
	Data: function(value) {
		return value==null ? "" : value;
	},
	Select: function(value) {
		return __(frappe.form.formatters["Data"](value));
	},
	Float: function(value, docfield, options, doc) {
		// don't allow 0 precision for Floats, hence or'ing with null
		var precision = docfield.precision || cint(frappe.boot.sysdefaults.float_precision) || null;
		if (docfield.options && docfield.options.trim()) {
			// options points to a currency field, but expects precision of float!
			docfield.precision = precision;
			return frappe.form.formatters.Currency(value, docfield, options, doc);

		} else {
			// show 1.000000 as 1
			if (!(options || {}).always_show_decimals && !is_null(value)) {
				var temp = cstr(value).split(".");
				if (temp[1]==undefined || cint(temp[1])===0) {
					precision = 0;
				}
			}

			return frappe.form.formatters._right(
				((value==null || value==="")
					? ""
					: format_number(value, null, precision)), options);
		}
	},
	Int: function(value, docfield, options) {
		return frappe.form.formatters._right(value==null ? "" : cint(value), options)
	},
	Percent: function(value, docfield, options) {
		return frappe.form.formatters._right(flt(value, 2) + "%", options)
	},
	Currency: function(value, docfield, options, doc) {
		var currency = frappe.meta.get_field_currency(docfield, doc);
		return frappe.form.formatters._right((value==null || value==="")
			? "" : format_currency(value, currency, docfield.precision || null), options);
	},
	Check: function(value) {
		if(value) {
			return '<i class="octicon octicon-check" style="margin-right: 8px;"></i>';
		} else {
			return '<i class="icon-check-empty text-extra-muted" style="margin-right: 8px;"></i>';
		}
	},
	Link: function(value, docfield, options) {
		var doctype = docfield._options || docfield.options;
		if(value && value.match(/^['"].*['"]$/)) {
			return value.replace(/^.(.*).$/, "$1");
		}
		if(options && options.for_print) {
			return value;
		}
		if(!value) {
			return "";
		}
		if(docfield && docfield.link_onclick) {
			return repl('<a onclick="%(onclick)s">%(value)s</a>',
				{onclick: docfield.link_onclick.replace(/"/g, '&quot;'), value:value});
		} else if(docfield && doctype) {
			return repl('<a class="grey" href="#Form/%(doctype)s/%(name)s" data-doctype="%(doctype)s">%(label)s</a>', {
				doctype: encodeURIComponent(doctype),
				name: encodeURIComponent(value),
				label: __(options && options.label || value)
			});
		} else {
			return value;
		}
	},
	Date: function(value) {
		return value ? dateutil.str_to_user(value) : "";
	},
	Datetime: function(value) {
		return value ? dateutil.str_to_user(dateutil.convert_to_user_tz(value)) : "";
	},
	Text: function(value) {
		if(value) {
			var tags = ["<p", "<div", "<br", "<table"];
			var match = false;

			for(var i=0; i<tags.length; i++) {
				if(value.match(tags[i])) {
					match = true;
					break;
				}
			}

			if(!match) {
				value = replace_newlines(value);
			}
		}

		return frappe.form.formatters.Data(value);
	},
	StarredBy: function(value) {
		var html = "";
		$.each(JSON.parse(value || "[]"), function(i, v) {
			if(v) html+= '<span class="avatar avatar-small" \
				style="margin-right: 3px;"><img src="'+frappe.user_info(v).image+'" alt="'+ frappe.user_info(v).abbr +'"></span>';
		});
		return html;
	},
	Tag: function(value) {
		var html = "";
		$.each((value || "").split(","), function(i, v) {
			if(v) html+= '<span class="label label-info" \
				style="margin-right: 7px; cursor: pointer;"\
				data-field="_user_tags" data-label="'+v+'">'+v +'</span>';
		});
		return html;
	},
	Comment: function(value) {
		var html = "";
		$.each(JSON.parse(value || "[]"), function(i, v) {
			if(v) html+= '<span class="label label-warning" \
				style="margin-right: 7px;"\
				data-field="_comments" data-label="'+v.name+'">'+v.comment+'</span>';
		});
		return html;
	},
	Assign: function(value) {
		var html = "";
		$.each(JSON.parse(value || "[]"), function(i, v) {
			if(v) html+= '<span class="label label-warning" \
				style="margin-right: 7px;"\
				data-field="_assign">'+v+'</span>';
		});
		return html;
	},
	SmallText: function(value) {
		return frappe.form.formatters.Text(value);
	},
	TextEditor: function(value) {
		return frappe.form.formatters.Text(value);
	},
	Code: function(value) {
		return "<pre>" + (value==null ? "" : $("<div>").text(value).html()) + "</pre>"
	},
	WorkflowState: function(value) {
		workflow_state = frappe.get_doc("Workflow State", value);
		if(workflow_state) {
			return repl("<span class='label label-%(style)s' \
				data-workflow-state='%(value)s'\
				style='padding-bottom: 4px; cursor: pointer;'>\
				<i class='icon-small icon-white icon-%(icon)s'></i> %(value)s</span>", {
					value: value,
					style: workflow_state.style.toLowerCase(),
					icon: workflow_state.icon
				});
		} else {
			return "<span class='label'>" + value + "</span>";
		}
	},
	Email: function(value) {
		return $("<div></div>").text(value).html();
	}
}

frappe.form.get_formatter = function(fieldtype) {
	if(!fieldtype)
		fieldtype = "Data";
	return frappe.form.formatters[fieldtype.replace(/ /g, "")] || frappe.form.formatters.Data;
}

frappe.format = function(value, df, options, doc) {
	if(!df) df = {"fieldtype":"Data"};
	var fieldtype = df.fieldtype || "Data";

	// format Dynamic Link as a Link
	if(fieldtype==="Dynamic Link") {
		fieldtype = "Link";
		df._options = doc ? doc[df.options] : null;
	}

	formatter = df.formatter || frappe.form.get_formatter(fieldtype);

	var formatted = formatter(value, df, options, doc);

	if (typeof formatted == "string")
		formatted = frappe.utils.remove_script_and_style(formatted);

	return formatted;
}

frappe.get_format_helper = function(doc) {
	var helper = {
		get_formatted: function(fieldname) {
			var df = frappe.meta.get_docfield(doc.doctype, fieldname);
			if(!df) { console.log("fieldname not found: " + fieldname); };
			return frappe.format(doc[fieldname], df, {inline:1}, doc);
		}
	};
	$.extend(helper, doc);
	return helper;
}
