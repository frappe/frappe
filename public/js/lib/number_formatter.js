/**
 * Adapted from:
 * -------------
 * @preserve IntegraXor Web SCADA - JavaScript Number Formatter
 * http://www.integraxor.com/
 * author: KPL, KHL
 * (c)2011 ecava
 * Dual licensed under the MIT or GPL Version 2 licenses.
 */

////////////////////////////////////////////////////////////////////////////////
// param: Mask & Value
////////////////////////////////////////////////////////////////////////////////

window['format_number'] = function( m, v){ 
	if (!m) {
		return v; //return as it is.
	}
	//search for separator for grp & decimal, anything not digit, not +/- sign, not #.
	var result = m.match(/[^\d\-\+#]/g);
	var Decimal = (result && result[result.length-1]) || '.'; //treat the right most symbol as decimal 
	var Group = (result && result[1] && result[0]) || ',';  //treat the left most symbol as group separator

	if(isNaN(+v)) {
		v=0;
	};

	//convert any string to number according to formation sign.
	var format = m;
	var v = m.charAt(0) == '-'? -v: +v;
	var isNegative = v<0? v= -v: 0; //process only abs(), and turn on flag.
	
	//split the decimal for the format string if any.
	var m = m.split( Decimal);
	//Fix the decimal first, toFixed will auto fill trailing zero.
	v = v.toFixed( m[1] && m[1].length);
	// v = +(v) + ''; //convert number to string to trim off *all* trailing decimal zero(es)
	// 
	// //fill back any trailing zero according to format
	// var pos_trail_zero = m[1] && m[1].lastIndexOf('0'); //look for last zero in format
	var part = v.split('.');
	// if (!part[1] || part[1] && part[1].length <= pos_trail_zero) {
	// 	v = (+v).toFixed( pos_trail_zero+1);
	// }
	var szSep = m[0].split( Group); //look for separator
	m[0] = szSep.join(''); //join back without separator for counting the pos of any leading 0.

	var pos_lead_zero = m[0] && m[0].indexOf('0');
	if (pos_lead_zero > -1 ) {
		while (part[0].length < (m[0].length - pos_lead_zero)) {
			part[0] = '0' + part[0];
		}
	}
	else if (+part[0] == 0){
		part[0] = '';
	}
	
	v = v.split('.');
	v[0] = part[0];
	
	//process the first group separator from decimal (.) only, the rest ignore.
	//get the length of the last slice of split result.
	var pos_separator = ( szSep[1] && szSep[ szSep.length-1].length);
	if (pos_separator) {
		var integer = v[0];
		var str = '';
		var offset = integer.length % pos_separator;
		for (var i=integer.length; i>=0; i--) { 
			var l = replace_all(str, Group, "").length;
			if(format=="#,##,###.##" && str.indexOf(",")!=-1) { // INR
				pos_separator = 2;
				l += 1;
			}
			
			str += integer.charAt(i); //ie6 only support charAt for sz.
			//-pos_separator so that won't trail separator on full length
			if (l && !((l+1) % pos_separator) && i!=0 ) {
				str += Group;
			}
		}
		v[0] = str.split("").reverse().join("");
	}

	v[1] = (m[1] && v[1])? Decimal+v[1] : "";
	return (isNegative?'-':'') + v[0] + v[1]; //put back any negation and combine integer and fraction.
};