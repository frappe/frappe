// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// for license information please see license.txt

frappe.provide("frappe.form.formatters");

frappe.form.link_formatters = {};

frappe.form.formatters = {
	_right: function(value, options) {
		if(options && (options.inline || options.only_value)) {
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
		var precision = docfield.precision
			|| cint(frappe.boot.sysdefaults && frappe.boot.sysdefaults.float_precision)
			|| null;
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
	Currency: function (value, docfield, options, doc) {
		var currency  = frappe.meta.get_field_currency(docfield, doc);
		var precision = docfield.precision || cint(frappe.boot.sysdefaults.currency_precision) || 2;

		// If you change anything below, it's going to hurt a company in UAE, a bit.
		if (precision > 2) {
			var parts	 = cstr(value).split("."); // should be minimum 2, comes from the DB
			var decimals = parts.length > 1 ? parts[1] : ""; // parts.length == 2 ???

			if ( decimals.length < 3 || decimals.length < precision ) {
				const fraction = frappe.model.get_value(":Currency", currency, "fraction_units") || 100; // if not set, minimum 2.
				precision      = cstr(fraction).length - 1;
			}
		}

		value = (value == null || value === "") ? "" : format_currency(value, currency, precision);

		if ( options && options.only_value ) {
			return value;
		} else {
			return frappe.form.formatters._right(value, options);
		}
	},
	Check: function(value) {
		if(value) {
			return '<i class="octicon octicon-check" style="margin-right: 3px;"></i>';
		} else {
			return '<i class="fa fa-square disabled-check"></i>';
		}
	},
	Link: function(value, docfield, options, doc) {
		var doctype = docfield._options || docfield.options;
		var original_value = value;
		if(value && value.match && value.match(/^['"].*['"]$/)) {
			value.replace(/^.(.*).$/, "$1");
		}

		if(options && (options.for_print || options.only_value)) {
			return value;
		}

		if(frappe.form.link_formatters[doctype]) {
			// don't apply formatters in case of composite (parent field of same type)
			if (doc && doctype !== doc.doctype) {
				value = frappe.form.link_formatters[doctype](value, doc);
			}
		}

		if(!value) {
			return "";
		}
		if(value[0] == "'" && value[value.length -1] == "'") {
			return value.substring(1, value.length - 1);
		}
		if(docfield && docfield.link_onclick) {
			return repl('<a onclick="%(onclick)s">%(value)s</a>',
				{onclick: docfield.link_onclick.replace(/"/g, '&quot;'), value:value});
		} else if(docfield && doctype) {
			return repl('<a class="grey" href="#Form/%(doctype)s/%(name)s" data-doctype="%(doctype)s">%(label)s</a>', {
				doctype: encodeURIComponent(doctype),
				name: encodeURIComponent(original_value),
				label: __(options && options.label || value)
			});
		} else {
			return value;
		}
	},
	Date: function(value) {
		if (value) {
			value = frappe.datetime.str_to_user(value);
			// handle invalid date
			if (value==="Invalid date") {
				value = null;
			}
		}

		return value || "";
	},
	DateRange: function(value) {
		if($.isArray(value)) {
			return __("{0} to {1}", [
				frappe.datetime.str_to_user(value[0]),
				frappe.datetime.str_to_user(value[1])
			]);
		} else {
			return value || "";
		}
	},
	Datetime: function(value) {
		if(value) {
			var m = moment(frappe.datetime.convert_to_user_tz(value));
			if(frappe.boot.sysdefaults.time_zone) {
				m = m.tz(frappe.boot.sysdefaults.time_zone);
			}
			return m.format(frappe.boot.sysdefaults.date_format.toUpperCase() + ', h:mm a z');
		} else {
			return "";
		}
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
				value = frappe.utils.replace_newlines(value);
			}
		}

		return frappe.form.formatters.Data(value);
	},
	LikedBy: function(value) {
		var html = "";
		$.each(JSON.parse(value || "[]"), function(i, v) {
			if(v) html+= frappe.avatar(v);
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
		var workflow_state = frappe.get_doc("Workflow State", value);
		if(workflow_state) {
			return repl("<span class='label label-%(style)s' \
				data-workflow-state='%(value)s'\
				style='padding-bottom: 4px; cursor: pointer;'>\
				<i class='fa fa-small fa-white fa-%(icon)s'></i> %(value)s</span>", {
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
	},
	FileSize: function(value) {
		if(value > 1048576) {
			value = flt(flt(value) / 1048576, 1) + "M";
		} else if (value > 1024) {
			value = flt(flt(value) / 1024, 1) + "K";
		}
		return value;
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

	var formatter = df.formatter || frappe.form.get_formatter(fieldtype);

	var formatted = formatter(value, df, options, doc);

	if (typeof formatted == "string")
		formatted = frappe.dom.remove_script_and_style(formatted);

	return formatted;
}

frappe.get_format_helper = function(doc) {
	var helper = {
		get_formatted: function(fieldname) {
			var df = frappe.meta.get_docfield(doc.doctype, fieldname);
			if(!df) { console.log("fieldname not found: " + fieldname); }
			return frappe.format(doc[fieldname], df, {inline:1}, doc);
		}
	};
	$.extend(helper, doc);
	return helper;
}
