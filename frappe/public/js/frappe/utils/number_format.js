// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

import './datatype';

if (!window.frappe) window.frappe = {};

function flt(v, decimals, number_format) {
	if (v == null || v == '') return 0;

	if (!(typeof v === "number" || String(parseFloat(v)) == v)) {
		// cases in which this block should not run
		// 1. 'v' is already a number
		// 2. v is already parsed but in string form
		// if (typeof v !== "number") {

		v = v + "";

		// strip currency symbol if exists
		if (v.indexOf(" ") != -1) {
			// using slice(1).join(" ") because space could also be a group separator
			var parts = v.split(" ");
			v = isNaN(parseFloat(parts[0])) ? parts.slice(parts.length - 1).join(" ") : v;
		}

		v = strip_number_groups(v, number_format);

		v = parseFloat(v);
		if (isNaN(v))
			v = 0;
	}

	v = parseFloat(v);
	if (decimals != null)
		return _round(v, decimals);
	return v;
}

function strip_number_groups(v, number_format) {
	if (!number_format) number_format = get_number_format();
	var info = get_number_format_info(number_format);

	// strip groups (,)
	var group_regex = new RegExp(info.group_sep === "." ? "\\." : info.group_sep, "g");
	v = v.replace(group_regex, "");

	// replace decimal separator with (.)
	if (info.decimal_str !== "." && info.decimal_str !== "") {
		var decimal_regex = new RegExp(info.decimal_str, "g");
		v = v.replace(decimal_regex, ".");
	}

	return v;
}


frappe.number_format_info = {
	"#,###.##": { decimal_str: ".", group_sep: "," },
	"#.###,##": { decimal_str: ",", group_sep: "." },
	"# ###.##": { decimal_str: ".", group_sep: " " },
	"# ###,##": { decimal_str: ",", group_sep: " " },
	"#'###.##": { decimal_str: ".", group_sep: "'" },
	"#, ###.##": { decimal_str: ".", group_sep: ", " },
	"#,##,###.##": { decimal_str: ".", group_sep: "," },
	"#,###.###": { decimal_str: ".", group_sep: "," },
	"#.###": { decimal_str: "", group_sep: "." },
	"#,###": { decimal_str: "", group_sep: "," },
}

window.format_number = function (v, format, decimals) {
	if (!format) {
		format = get_number_format();
		if (decimals == null) decimals = cint(frappe.defaults.get_default("float_precision")) || 3;
	}

	var info = get_number_format_info(format);

	// Fix the decimal first, toFixed will auto fill trailing zero.
	if (decimals == null) decimals = info.precision;

	v = flt(v, decimals, format);

	let is_negative = false;
	if (v < 0) is_negative = true;
	v = Math.abs(v);

	v = v.toFixed(decimals);

	var part = v.split('.');

	// get group position and parts
	var group_position = info.group_sep ? 3 : 0;

	if (group_position) {
		var integer = part[0];
		var str = '';
		var offset = integer.length % group_position;
		for (var i = integer.length; i >= 0; i--) {
			var l = replace_all(str, info.group_sep, "").length;
			if (format == "#,##,###.##" && str.indexOf(",") != -1) { // INR
				group_position = 2;
				l += 1;
			}

			str += integer.charAt(i);

			if (l && !((l + 1) % group_position) && i != 0) {
				str += info.group_sep;
			}
		}
		part[0] = str.split("").reverse().join("");
	}
	if (part[0] + "" == "") {
		part[0] = "0";
	}

	// join decimal
	part[1] = (part[1] && info.decimal_str) ? (info.decimal_str + part[1]) : "";

	// join
	return (is_negative ? "-" : "") + part[0] + part[1];
};

function format_currency(v, currency, decimals) {
	var format = get_number_format(currency);
	var symbol = get_currency_symbol(currency);
	if(decimals === undefined) {
		decimals = frappe.boot.sysdefaults.currency_precision || null;
	}

	if (symbol)
		return symbol + " " + format_number(v, format, decimals);
	else
		return format_number(v, format, decimals);
}

function get_currency_symbol(currency) {
	if (frappe.boot) {
		if (frappe.boot.sysdefaults && frappe.boot.sysdefaults.hide_currency_symbol == "Yes")
			return null;

		if (!currency)
			currency = frappe.boot.sysdefaults.currency;

		return frappe.model.get_value(":Currency", currency, "symbol") || currency;
	} else {
		// load in template
		return frappe.currency_symbols[currency];
	}
}

function get_number_format(currency) {
	return (frappe.boot && frappe.boot.sysdefaults && frappe.boot.sysdefaults.number_format) || "#,###.##";
}

function get_number_format_info(format) {
	var info = frappe.number_format_info[format];

	if (!info) {
		info = { decimal_str: ".", group_sep: "," };
	}

	// get the precision from the number format
	info.precision = format.split(info.decimal_str).slice(1)[0].length;

	return info;
}

function _round(num, precision) {
	var is_negative = num < 0 ? true : false;
	var d = cint(precision);
	var m = Math.pow(10, d);
	var n = +(d ? Math.abs(num) * m : Math.abs(num)).toFixed(8); // Avoid rounding errors
	var i = Math.floor(n), f = n - i;
	var r = ((!precision && f == 0.5) ? ((i % 2 == 0) ? i : i + 1) : Math.round(n));
	r = d ? r / m : r;
	return is_negative ? -r : r;

}

function roundNumber(num, precision) {
	// backward compatibility
	return _round(num, precision);
}

function precision(fieldname, doc) {
	if (cur_frm) {
		if (!doc) doc = cur_frm.doc;
		var df = frappe.meta.get_docfield(doc.doctype, fieldname, doc.parent || doc.name);
		if (!df) console.log(fieldname + ": could not find docfield in method precision()");
		return frappe.meta.get_field_precision(df, doc);
	} else {
		return frappe.boot.sysdefaults.float_precision
	}
}

function in_list(list, item) {
	return list.includes(item);
}

function remainder(numerator, denominator, precision) {
	precision = cint(precision);
	var multiplier = Math.pow(10, precision);
	if (precision) {
		var _remainder = ((numerator * multiplier) % (denominator * multiplier)) / multiplier;
	} else {
		var _remainder = numerator % denominator;
	}

	return flt(_remainder, precision);
}

function round_based_on_smallest_currency_fraction(value, currency, precision) {
	var smallest_currency_fraction_value = flt(frappe.model.get_value(":Currency",
		currency, "smallest_currency_fraction_value"))

	if (smallest_currency_fraction_value) {
		var remainder_val = remainder(value, smallest_currency_fraction_value, precision);
		if (remainder_val > (smallest_currency_fraction_value / 2)) {
			value += (smallest_currency_fraction_value - remainder_val);
		} else {
			value -= remainder_val;
		}
	} else {
		value = _round(value);
	}
	return value;
}

function fmt_money(v, format){
	// deprecated!
	// for backward compatibility
	return format_currency(v, format);
}


Object.assign(window, {
	flt,
	cint,
	strip_number_groups,
	format_currency,
	fmt_money,
	get_currency_symbol,
	get_number_format,
	get_number_format_info,
	_round,
	roundNumber,
	precision,
	remainder,
	round_based_on_smallest_currency_fraction,
	in_list
});