// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

if(!window.wn) wn = {};

function flt(v, decimals, number_format) { 
	if(v==null || v=='')return 0;
	
	if(typeof v!=="number") {
		v = v + "";

		// strip currency symbol if exists
		if(v.indexOf(" ")!=-1) {
			v = v.split(" ")[1];
		}

		v = strip_number_groups(v, number_format);

		v=parseFloat(v);
		if(isNaN(v))
			v=0;
	}
	
	if(decimals!=null)
		return _round(v, decimals);
	return v;
}

function cint(v, def) { 
	if(v===true) 
		return 1;
	if(v===false)
		return 0;
	v=v+'';
	if(v!=="0")v=lstrip(v, ['0']); 
	v=parseInt(v); 
	if(isNaN(v))v=def===undefined?0:def;
	return v; 
}

function strip_number_groups(v, number_format) {
	if(!number_format) number_format = get_number_format();
	
	// strip groups (,)
	if(get_number_format_info(number_format).group_sep==".") {
		v = v.replace(/\./g,'');

		// sanitize decimal separator to .
		v = v.replace(/,/g, ".");
	} else {
		v=v.replace(/,/g,'');
	}
	
	return v;
}


wn.number_format_info = {
	"#,###.##": {decimal_str:".", group_sep:",", precision:2},
	"#.###,##": {decimal_str:",", group_sep:".", precision:2},
	"# ###.##": {decimal_str:".", group_sep:" ", precision:2},
	"#,###.###": {decimal_str:".", group_sep:",", precision:3},
	"#,##,###.##": {decimal_str:".", group_sep:",", precision:2},
	"#.###": {decimal_str:"", group_sep:".", precision:0},
	"#,###": {decimal_str:"", group_sep:",", precision:0},
}

window.format_number = function(v, format, decimals){ 
	if (!format) {
		format = get_number_format();
		if(decimals == null) decimals = cint(wn.defaults.get_default("float_precision")) || 3;
	}

	info = get_number_format_info(format);
	
	//Fix the decimal first, toFixed will auto fill trailing zero.
	decimals = decimals || info.precision;
	
	v = flt(v, decimals, format);

	if(v<0) var is_negative = true; 
	v = Math.abs(v);
	
	v = v.toFixed(decimals);

	var part = v.split('.');
	
	// get group position and parts
	var group_position = info.group_sep ? 3 : 0;

	if (group_position) {
		var integer = part[0];
		var str = '';
		var offset = integer.length % group_position;
		for (var i=integer.length; i>=0; i--) { 
			var l = replace_all(str, info.group_sep, "").length;
			if(format=="#,##,###.##" && str.indexOf(",")!=-1) { // INR
				group_position = 2;
				l += 1;
			}
			
			str += integer.charAt(i); 

			if (l && !((l+1) % group_position) && i!=0 ) {
				str += info.group_sep;
			}
		}
		part[0] = str.split("").reverse().join("");
	}
	if(part[0]+""=="") {
		part[0]="0";
	}
	
	// join decimal
	part[1] = part[1] ? (info.decimal_str + part[1]) : "";
	
	// join
	return (is_negative ? "-" : "") + part[0] + part[1];
};

function format_currency(v, currency, decimals) {
	var format = get_number_format(currency);
	var symbol = get_currency_symbol(currency);

	if(symbol)
		return symbol + " " + format_number(v, format, decimals);
	else
		return format_number(v, format, decimals);
}

function get_currency_symbol(currency) {
	if(wn.boot) {
		if(wn.boot.sysdefaults.hide_currency_symbol=="Yes")
			return null;

		if(!currency)
			currency = wn.boot.sysdefaults.currency;

		return wn.model.get_value(":Currency", currency, "symbol") || currency;
	} else {
		// load in template
		return wn.currency_symbols[currency];
	}
}

var global_number_format = null;
function get_number_format(currency) {
	if(!global_number_format) {
		global_number_format = wn.boot.sysdefaults.number_format
			|| wn.model.get_value("Currency", wn.boot.sysdefaults.currency, "number_format")
			|| "#,###.##";
	}
	
	var number_format;
	if(currency && wn.boot) {
		number_format = wn.model.get_value("Currency", currency, 
			"number_format");
	}
	
	return number_format || global_number_format;
}

function get_number_format_info(format) {
	var info = wn.number_format_info[format];
	if(!info) {
		info = {decimal_str:".", group_sep:",", precision:2};
	}
	return info;
}

function _round(num, precision) {
    var d = cint(precision);
    var m = Math.pow(10, d);
    var n = +(d ? num * m : num).toFixed(8); // Avoid rounding errors
    var i = Math.floor(n), f = n - i;
    var r = (f == 0.5) ? ((i % 2 == 0) ? i : i + 1) : Math.round(n);
    return d ? r / m : r;
}

function roundNumber(num, precision) {
	// backward compatibility
	return _round(num, precision);
}

function precision(fieldname, doc) {
	if(!doc) doc = cur_frm.doc;
	var df = wn.meta.get_docfield(doc.doctype, fieldname, doc.parent || doc.name);
	if(!df) console.log(fieldname + ": could not find docfield in method precision()");
	return wn.meta.get_field_precision(df, doc);
}

var lstrip = function(s, chars) {
	if(!chars) chars = ['\n', '\t', ' '];
	// strip left
	var first_char = s.substr(0,1);
	while(in_list(chars, first_char)) {
		var s = s.substr(1);
		first_char = s.substr(0,1);
	}
	return s;
}

function in_list(list, item) {
	if(!list) return false;
	for(var i=0, j=list.length; i<j; i++)
		if(list[i]==item) return true;
	return false;
}