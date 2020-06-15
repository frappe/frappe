// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

import deep_equal from "fast-deep-equal";
frappe.provide('frappe.utils');

Object.assign(frappe.utils, {
	get_random: function(len) {
		var text = "";
		var possible = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz";

		for( var i=0; i < len; i++ )
			text += possible.charAt(Math.floor(Math.random() * possible.length));

		return text;
	},
	get_file_link: function(filename) {
		filename = cstr(filename);
		if(frappe.utils.is_url(filename)) {
			return filename;
		} else if(filename.indexOf("/")===-1) {
			return "files/" + filename;
		} else {
			return filename;
		}
	},
	replace_newlines(t) {
		return t?t.replace(/\n/g, '<br>'):'';
	},
	is_html: function(txt) {
		if (!txt) return false;

		if(txt.indexOf("<br>")==-1 && txt.indexOf("<p")==-1
			&& txt.indexOf("<img")==-1 && txt.indexOf("<div")==-1 && !txt.includes('<span')) {
			return false;
		}
		return true;
	},
	is_mac: function() {
		return window.navigator.platform === 'MacIntel';
	},
	is_xs: function() {
		return $(document).width() < 768;
	},
	is_sm: function() {
		return $(document).width() < 991 && $(document).width() >= 768;
	},
	is_md: function() {
		return $(document).width() < 1199 && $(document).width() >= 991;
	},
	is_json: function(str) {
		try {
			JSON.parse(str);
		} catch (e) {
			return false;
		}
		return true;
	},
	strip_whitespace: function(html) {
		return (html || "").replace(/<p>\s*<\/p>/g, "").replace(/<br>(\s*<br>\s*)+/g, "<br><br>");
	},
	encode_tags: function(html) {
		var tagsToReplace = {
			'&': '&amp;',
			'<': '&lt;',
			'>': '&gt;'
		};

		function replaceTag(tag) {
			return tagsToReplace[tag] || tag;
		}

		return html.replace(/[&<>]/g, replaceTag);
	},
	strip_original_content: function(txt) {
		var out = [],
			part = [],
			newline = txt.indexOf("<br>")===-1 ? "\n" : "<br>";

		$.each(txt.split(newline), function(i, t) {
			var tt = strip(t);
			if(tt && (tt.substr(0,1)===">" || tt.substr(0,4)==="&gt;")) {
				part.push(t);
			} else {
				out.concat(part);
				out.push(t);
				part = [];
			}
		});
		return out.join(newline);
	},
	escape_html: function(txt) {
		return $("<div></div>").text(txt || "").html();
	},

	html2text: function(html) {
		let d = document.createElement('div');
		d.innerHTML = html;
		return d.textContent;
	},

	is_url: function(txt) {
		return txt.toLowerCase().substr(0,7)=='http://'
			|| txt.toLowerCase().substr(0,8)=='https://'
	},
	to_title_case: function(string, with_space=false) {
		let titlecased_string = string.toLowerCase().replace(/(?:^|[\s-/])\w/g, function(match) {
			return match.toUpperCase();
		});

		let replace_with = with_space ? ' ' : '';

		return titlecased_string.replace(/-|_/g, replace_with);
	},
	toggle_blockquote: function(txt) {
		if (!txt) return txt;

		var content = $("<div></div>").html(txt)
		content.find("blockquote").parent("blockquote").addClass("hidden")
			.before('<p><a class="text-muted btn btn-default toggle-blockquote" style="padding: 2px 7px 0px; line-height: 1;"> \
					• • • \
				</a></p>');
		return content.html();
	},
	scroll_to: function(element, animate, additional_offset, element_to_be_scrolled) {
		element_to_be_scrolled = element_to_be_scrolled || $("html, body");

		var y = 0;
		if (element && typeof element==="number") {
			y = element;
		} else if(element) {
			var header_offset = $(".navbar").height() + $(".page-head").height();
			var y = $(element).offset().top - header_offset - cint(additional_offset);
		}

		if(y < 0) {
			y = 0;
		}

		// already there
		if (y == element_to_be_scrolled.scrollTop()) {
			return;
		}

		if (animate !== false) {
			element_to_be_scrolled.animate({ scrollTop: y });
		} else {
			element_to_be_scrolled.scrollTop(y);
		}

	},
	filter_dict: function(dict, filters) {
		var ret = [];
		if(typeof filters=='string') {
			return [dict[filters]]
		}
		$.each(dict, function(i, d) {
			for(var key in filters) {
				if($.isArray(filters[key])) {
					if(filters[key][0]=="in") {
						if(filters[key][1].indexOf(d[key])==-1)
							return;
					} else if(filters[key][0]=="not in") {
						if(filters[key][1].indexOf(d[key])!=-1)
							return;
					} else if(filters[key][0]=="<") {
						if (!(d[key] < filters[key])) return;
					} else if(filters[key][0]=="<=") {
						if (!(d[key] <= filters[key])) return;
					} else if(filters[key][0]==">") {
						if (!(d[key] > filters[key])) return;
					} else if(filters[key][0]==">=") {
						if (!(d[key] >= filters[key])) return;
					}
				} else {
					if(d[key]!=filters[key]) return;
				}
			}
			ret.push(d);
		});
		return ret;
	},
	comma_or: function(list) {
		return frappe.utils.comma_sep(list, " " + __("or") + " ");
	},
	comma_and: function(list) {
		return frappe.utils.comma_sep(list, " " + __("and") + " ");
	},
	comma_sep: function(list, sep) {
		if(list instanceof Array) {
			if(list.length==0) {
				return "";
			} else if (list.length==1) {
				return list[0];
			} else {
				return list.slice(0, list.length-1).join(", ") + sep + list.slice(-1)[0];
			}
		} else {
			return list;
		}
	},
	set_footnote: function(footnote_area, wrapper, txt) {
		if(!footnote_area) {
			footnote_area = $('<div class="text-muted footnote-area level">')
				.appendTo(wrapper);
		}

		if(txt) {
			footnote_area.html(txt);
		} else {
			footnote_area.remove();
			footnote_area = null;
		}
		return footnote_area;
	},
	get_args_dict_from_url: function(txt) {
		var args = {};
		$.each(decodeURIComponent(txt).split("&"), function(i, arg) {
			arg = arg.split("=");
			args[arg[0]] = arg[1]
		});
		return args;
	},
	get_url_from_dict: function(args) {
		return $.map(args, function(val, key) {
			if(val!==null)
				return encodeURIComponent(key)+"="+encodeURIComponent(val);
			else
				return null;
		}).join("&") || "";
	},
	validate_type: function ( val, type ) {
		// from https://github.com/guillaumepotier/Parsley.js/blob/master/parsley.js#L81
		var regExp;

		switch ( type ) {
			case "phone":
				regExp = /^([0-9\ \+\_\-\,\.\*\#\(\)]){1,20}$/;
				break;
			case "name":
				regExp = /^[\w][\w'-]*([ \w][\w'-]+)*$/;
				break;
			case "number":
				regExp = /^-?(?:\d+|\d{1,3}(?:,\d{3})+)?(?:\.\d+)?$/;
				break;
			case "digits":
				regExp = /^\d+$/;
				break;
			case "alphanum":
				regExp = /^\w+$/;
				break;
			case "email":
				// from https://emailregex.com/
				regExp = /^(([^<>()\[\]\\.,;:\s@"]+(\.[^<>()\[\]\\.,;:\s@"]+)*)|(".+"))@((\[[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}])|(([a-zA-Z\-0-9]+\.)+[a-zA-Z]{2,}))$/;
				break;
			case "url":
				regExp = /^(https?|s?ftp):\/\/(((([a-z]|\d|-|\.|_|~|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])|(%[\da-f]{2})|[!\$&'\(\)\*\+,;=]|:)*@)?(((\d|[1-9]\d|1\d\d|2[0-4]\d|25[0-5])\.(\d|[1-9]\d|1\d\d|2[0-4]\d|25[0-5])\.(\d|[1-9]\d|1\d\d|2[0-4]\d|25[0-5])\.(\d|[1-9]\d|1\d\d|2[0-4]\d|25[0-5]))|((([a-z]|\d|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])|(([a-z]|\d|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])([a-z]|\d|-|\.|_|~|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])*([a-z]|\d|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])))\.)+(([a-z]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])|(([a-z]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])([a-z]|\d|-|\.|_|~|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])*([a-z]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])))\.?)(:\d*)?)(\/((([a-z]|\d|-|\.|_|~|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])|(%[\da-f]{2})|[!\$&'\(\)\*\+,;=]|:|@)+(\/(([a-z]|\d|-|\.|_|~|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])|(%[\da-f]{2})|[!\$&'\(\)\*\+,;=]|:|@)*)*)?)?(\?((([a-z]|\d|-|\.|_|~|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])|(%[\da-f]{2})|[!\$&'\(\)\*\+,;=]|:|@)|[\uE000-\uF8FF]|\/|\?)*)?(#((([a-z]|\d|-|\.|_|~|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])|(%[\da-f]{2})|[!\$&'\(\)\*\+,;=]|:|@)|\/|\?)*)?$/i;
				break;
			case "dateIso":
				regExp = /^(\d{4})\D?(0[1-9]|1[0-2])\D?([12]\d|0[1-9]|3[01])$/;
				break;
			default:
				return false;
		}

		// test regExp if not null
		return '' !== val ? regExp.test( val ) : false;
	},
	guess_style: function(text, default_style, _colour) {
		var style = default_style || "default";
		var colour = "darkgrey";
		if(text) {
			if(has_words(["Pending", "Review", "Medium", "Not Approved"], text)) {
				style = "warning";
				colour = "orange";
			} else if(has_words(["Open", "Urgent", "High", "Failed", "Rejected", "Error"], text)) {
				style = "danger";
				colour = "red";
			} else if(has_words(["Closed", "Finished", "Converted", "Completed", "Complete", "Confirmed",
				"Approved", "Yes", "Active", "Available", "Paid", "Success"], text)) {
				style = "success";
				colour = "green";
			} else if(has_words(["Submitted"], text)) {
				style = "info";
				colour = "blue";
			}
		}
		return _colour ? colour : style;
	},

	guess_colour: function(text) {
		return frappe.utils.guess_style(text, null, true);
	},

	get_indicator_color: function(state) {
		return frappe.db.get_list('Workflow State', {filters: {name: state}, fields: ['name', 'style']}).then(res => {
			const state = res[0];
			if (!state.style) {
				return frappe.utils.guess_colour(state.name);
			}
			const style = state.style;
			const colour_map = {
				"Success": "green",
				"Warning": "orange",
				"Danger": "red",
				"Primary": "blue",
			};

			return colour_map[style];
		});

	},

	sort: function(list, key, compare_type, reverse) {
		if(!list || list.length < 2)
			return list || [];

		var sort_fn = {
			"string": function(a, b) {
				return cstr(a[key]).localeCompare(cstr(b[key]));
			},
			"number": function(a, b) {
				return flt(a[key]) - flt(b[key]);
			}
		};

		if(!compare_type)
			compare_type = typeof list[0][key]==="string" ? "string" : "number";

		list.sort(sort_fn[compare_type]);

		if(reverse) { list.reverse(); }

		return list;
	},

	unique: function(list) {
		var dict = {},
			arr = [];
		for(var i=0, l=list.length; i < l; i++) {
			if(!dict.hasOwnProperty(list[i])) {
				dict[list[i]] = null;
				arr.push(list[i]);
			}
		}
		return arr;
	},

	remove_nulls: function(list) {
		var new_list = [];
		for (var i=0, l=list.length; i < l; i++) {
			if (!is_null(list[i])) {
				new_list.push(list[i]);
			}
		}
		return new_list;
	},

	all: function(lst) {
		for(var i=0, l=lst.length; i<l; i++) {
			if(!lst[i]) {
				return false;
			}
		}
		return true;
	},

	dict: function(keys,values) {
		// make dictionaries from keys and values
		var out = [];
		$.each(values, function(row_idx, row) {
			var new_row = {};
			$.each(keys, function(key_idx, key) {
				new_row[key] = row[key_idx];
			})
			out.push(new_row);
		});
		return out;
	},

	sum: function(list) {
		return list.reduce(function(previous_value, current_value) { return flt(previous_value) + flt(current_value); }, 0.0);
	},

	arrays_equal: function(arr1, arr2) {
		if (!arr1 || !arr2) {
			return false;
		}
		if (arr1.length != arr2.length) {
			return false;
		}
		for (var i = 0; i < arr1.length; i++) {
			if ($.isArray(arr1[i])) {
				if (!frappe.utils.arrays_equal(arr1[i], arr2[i])) {
					return false;
				}
			}
			else if (arr1[i] !== arr2[i]) {
				return false;
			}
		}
		return true;
	},

	intersection: function(a, b) {
		// from stackoverflow: http://stackoverflow.com/questions/1885557/simplest-code-for-array-intersection-in-javascript
		/* finds the intersection of
		 * two arrays in a simple fashion.
		 *
		 * PARAMS
		 *  a - first array, must already be sorted
		 *  b - second array, must already be sorted
		 *
		 * NOTES
		 *
		 *  Should have O(n) operations, where n is
		 *    n = MIN(a.length(), b.length())
		 */
		var ai=0, bi=0;
		var result = new Array();

		// sorted copies
		a = ([].concat(a)).sort();
		b = ([].concat(b)).sort();

		while( ai < a.length && bi < b.length ) {
			if (a[ai] < b[bi] ) { ai++; }
			else if (a[ai] > b[bi] ) { bi++; }
			else {
				/* they're equal */
				result.push(a[ai]);
				ai++;
				bi++;
			}
		}

		return result;
	},

	resize_image: function(reader, callback, max_width, max_height) {
		var tempImg = new Image();
		if(!max_width) max_width = 600;
		if(!max_height) max_height = 400;
		tempImg.src = reader.result;

		tempImg.onload = function() {
			var tempW = tempImg.width;
			var tempH = tempImg.height;
			if (tempW > tempH) {
				if (tempW > max_width) {
					tempH *= max_width / tempW;
					tempW = max_width;
				}
			} else {
				if (tempH > max_height) {
					tempW *= max_height / tempH;
					tempH = max_height;
				}
			}

			var canvas = document.createElement('canvas');
			canvas.width = tempW;
			canvas.height = tempH;
			var ctx = canvas.getContext("2d");
			ctx.drawImage(this, 0, 0, tempW, tempH);
			var dataURL = canvas.toDataURL("image/jpeg");
			setTimeout(function() { callback(dataURL); }, 10 );
		}
	},

	csv_to_array: function (strData, strDelimiter) {
		// Check to see if the delimiter is defined. If not,
		// then default to comma.
		strDelimiter = (strDelimiter || ",");

		// Create a regular expression to parse the CSV values.
		var objPattern = new RegExp(
			(
				// Delimiters.
				"(\\" + strDelimiter + "|\\r?\\n|\\r|^)" +

				// Quoted fields.
				"(?:\"([^\"]*(?:\"\"[^\"]*)*)\"|" +

				// Standard fields.
				"([^\"\\" + strDelimiter + "\\r\\n]*))"
			),
			"gi"
			);


		// Create an array to hold our data. Give the array
		// a default empty first row.
		var arrData = [[]];

		// Create an array to hold our individual pattern
		// matching groups.
		var arrMatches = null;


		// Keep looping over the regular expression matches
		// until we can no longer find a match.
		while ((arrMatches = objPattern.exec( strData ))){

			// Get the delimiter that was found.
			var strMatchedDelimiter = arrMatches[ 1 ];

			// Check to see if the given delimiter has a length
			// (is not the start of string) and if it matches
			// field delimiter. If id does not, then we know
			// that this delimiter is a row delimiter.
			if (
				strMatchedDelimiter.length &&
				strMatchedDelimiter !== strDelimiter
				){

				// Since we have reached a new row of data,
				// add an empty row to our data array.
				arrData.push( [] );

			}

			var strMatchedValue;

			// Now that we have our delimiter out of the way,
			// let's check to see which kind of value we
			// captured (quoted or unquoted).
			if (arrMatches[ 2 ]){

				// We found a quoted value. When we capture
				// this value, unescape any double quotes.
				strMatchedValue = arrMatches[ 2 ].replace(
					new RegExp( "\"\"", "g" ),
					"\""
					);

			} else {

				// We found a non-quoted value.
				strMatchedValue = arrMatches[ 3 ];

			}


			// Now that we have our value string, let's add
			// it to the data array.
			arrData[ arrData.length - 1 ].push( strMatchedValue );
		}

		// Return the parsed data.
		return( arrData );
	},

	warn_page_name_change: function(frm) {
		frappe.msgprint(__("Note: Changing the Page Name will break previous URL to this page."));
	},

	notify: function(subject, body, route, onclick) {
		console.log('push notifications are evil and deprecated');
	},

	set_title: function(title) {
		frappe._original_title = title;
		if(frappe._title_prefix) {
			title = frappe._title_prefix + " " + title.replace(/<[^>]*>/g, "");
		}
		document.title = title;
	},

	set_title_prefix: function(prefix) {
		frappe._title_prefix = prefix;

		// reset the original title
		frappe.utils.set_title(frappe._original_title);
	},

	is_image_file: function(filename) {
		if (!filename) return false;
		// url can have query params
		filename = filename.split('?')[0];
		return (/\.(gif|jpg|jpeg|tiff|png|svg)$/i).test(filename);
	},

	play_sound: function(name) {
		try {
			if (frappe.boot.user.mute_sounds) {
				return;
			}

			var audio = $("#sound-" + name)[0];
			audio.volume = audio.getAttribute("volume");
			audio.play();

		} catch(e) {
			console.log("Cannot play sound", name, e);
			// pass
		}

	},
	split_emails: function(txt) {
		var email_list = [];

		if (!txt) {
			return email_list;
		}

		// emails can be separated by comma or newline
		txt.split(/[,\n](?=(?:[^"]|"[^"]*")*$)/g).forEach(function(email) {
			email = email.trim();
			if (email) {
				email_list.push(email);
			}
		});

		return email_list;
	},
	supportsES6: function() {
		try {
			new Function("(a = 0) => a");
			return true;
		}
		catch (err) {
			return false;
		}
	}(),
	throttle: function (func, wait, options) {
		var context, args, result;
		var timeout = null;
		var previous = 0;
		if (!options) options = {};

		let later = function () {
			previous = options.leading === false ? 0 : Date.now();
			timeout = null;
			result = func.apply(context, args);
			if (!timeout) context = args = null;
		};

		return function () {
			var now = Date.now();
			if (!previous && options.leading === false) previous = now;
			let remaining = wait - (now - previous);
			context = this;
			args = arguments;
			if (remaining <= 0 || remaining > wait) {
				if (timeout) {
					clearTimeout(timeout);
					timeout = null;
				}
				previous = now;
				result = func.apply(context, args);
				if (!timeout) context = args = null;
			} else if (!timeout && options.trailing !== false) {
				timeout = setTimeout(later, remaining);
			}
			return result;
		};
	},
	debounce: function(func, wait, immediate) {
		var timeout;
		return function() {
			var context = this, args = arguments;
			var later = function() {
				timeout = null;
				if (!immediate) func.apply(context, args);
			};
			var callNow = immediate && !timeout;
			clearTimeout(timeout);
			timeout = setTimeout(later, wait);
			if (callNow) func.apply(context, args);
		};
	},
	get_form_link: function(doctype, name, html = false, display_text = null) {
		display_text = display_text || name;
		doctype = encodeURIComponent(doctype);
		name = encodeURIComponent(name);
		const route = ['#Form', doctype, name].join('/');
		if (html) {
			return `<a href="${route}">${display_text}</a>`;
		}
		return route;
	},
	get_route_label(route_str) {
		let route = route_str.split('/');

		if (route[2] === 'Report' || route[0] === 'query-report') {
			return __('{0} Report', [route[3] || route[1]]);
		}
		if (route[0] === 'List') {
			return __('{0} List', [route[1]]);
		}
		if (route[0] === 'modules') {
			return __('{0} Modules', [route[1]]);
		}
		if (route[0] === 'dashboard') {
			return __('{0} Dashboard', [route[1]]);
		}
		return __(frappe.utils.to_title_case(route[0], true));
	},
	report_column_total: function(values, column, type) {
		if (column.column.disable_total) {
			return '';
		} else if (values.length > 0) {
			if (column.column.fieldtype == "Percent" || type === "mean") {
				return values.reduce((a, b) => a + flt(b)) / values.length;
			} else if (column.column.fieldtype == "Int") {
				return values.reduce((a, b) => a + cint(b));
			} else if (frappe.model.is_numeric_field(column.column.fieldtype)) {
				return values.reduce((a, b) => a + flt(b));
			} else {
				return null;
			}
		}
		else {
			return null;
		}
	},
	setup_search($wrapper, el_class, text_class, data_attr) {
		const $search_input = $wrapper.find('[data-element="search"]').show();
		$search_input.focus().val('');
		const $elements = $wrapper.find(el_class).show();

		$search_input.off('keyup').on('keyup', () => {
			let text_filter = $search_input.val().toLowerCase();
			// Replace trailing and leading spaces
			text_filter = text_filter.replace(/^\s+|\s+$/g, '');
			for (let i = 0; i < $elements.length; i++) {
				const text_element = $elements.eq(i).find(text_class);
				const text = text_element.text().toLowerCase();

				let name = '';
				if (data_attr && text_element.attr(data_attr)) {
					name = text_element.attr(data_attr).toLowerCase();
				}

				if (text.includes(text_filter) || name.includes(text_filter)) {
					$elements.eq(i).css('display', '');
				} else {
					$elements.eq(i).css('display', 'none');
				}
			}
		});
	},
	deep_equal(a, b) {
		return deep_equal(a, b);
	},

	file_name_ellipsis(filename, length) {
		let first_part_length = length * 2 / 3;
		let last_part_length = length - first_part_length;
		let parts = filename.split('.');
		let extn = parts.pop();
		let name = parts.join('');
		let first_part = name.slice(0, first_part_length);
		let last_part = name.slice(-last_part_length);
		if (name.length > length) {
			return `${first_part}...${last_part}.${extn}`;
		} else {
			return filename;
		}
	},
	get_decoded_string(dataURI) {
		// decodes base64 to string
		let parts = dataURI.split(',');
		const encoded_data = parts[1];
		return decodeURIComponent(escape(atob(encoded_data)));
	},
	copy_to_clipboard(string) {
		let input = $("<input>");
		$("body").append(input);
		input.val(string).select();

		document.execCommand("copy");
		input.remove();

		frappe.show_alert({
			indicator: 'green',
			message: __('Copied to clipboard.')
		});
	},
	is_rtl() {
		return ["ar", "he", "fa"].includes(frappe.boot.lang);
	},
	bind_actions_with_object($el, object) {
		// remove previously bound event
		$($el).off('click.class_actions');
		// attach new event
		$($el).on('click.class_actions', '[data-action]', e => {
			let $target = $(e.currentTarget);
			let action = $target.data('action');
			let method = object[action];
			method ? object[action](e, $target) : null;
		});

		return $el;
	},

	get_browser() {
		var ua = navigator.userAgent,
			tem,
			M =
				ua.match(
					/(opera|chrome|safari|firefox|msie|trident(?=\/))\/?\s*(\d+)/i
				) || [];
		if (/trident/i.test(M[1])) {
			tem = /\brv[ :]+(\d+)/g.exec(ua) || [];
			return { name: "IE", version: tem[1] || "" };
		}
		if (M[1] === "Chrome") {
			tem = ua.match(/\bOPR|Edge\/(\d+)/);
			if (tem != null) {
				return { name: "Opera", version: tem[1] };
			}
		}
		M = M[2]
			? [M[1], M[2]]
			: [navigator.appName, navigator.appVersion, "-?"];
		if ((tem = ua.match(/version\/(\d+)/i)) != null) {
			M.splice(1, 1, tem[1]);
		}
		return {
			name: M[0],
			version: M[1],
		};
	},

	get_formatted_duration(value, duration_options) {
		let duration = '';
		if (value) {
			let total_duration = frappe.utils.seconds_to_duration(value, duration_options);

			if (total_duration.days) {
				duration += total_duration.days + __('d', null, 'Days (Field: Duration)');
			}
			if (total_duration.hours) {
				duration += (duration.length ? " " : "");
				duration += total_duration.hours + __('h', null, 'Hours (Field: Duration)');
			}
			if (total_duration.minutes) {
				duration += (duration.length ? " " : "");
				duration += total_duration.minutes + __('m', null, 'Minutes (Field: Duration)');
			}
			if (total_duration.seconds) {
				duration += (duration.length ? " " : "");
				duration += total_duration.seconds + __('s', null, 'Seconds (Field: Duration)');
			}
		}
		return duration;
	},

	seconds_to_duration(value, duration_options) {
		let secs = value;
		let total_duration = {
			days: Math.floor(secs / (3600 * 24)),
			hours: Math.floor(secs % (3600 * 24) / 3600),
			minutes: Math.floor(secs % 3600 / 60),
			seconds: Math.floor(secs % 60)
		};
		if (duration_options.hide_days) {
			total_duration.hours = Math.floor(secs / 3600);
			total_duration.days = 0;
		}
		return total_duration;
	},

	duration_to_seconds(days=0, hours=0, minutes=0, seconds=0) {
		let value = 0;
		if (days) {
			value += days * 24 * 60 * 60;
		}
		if (hours) {
			value += hours * 60 * 60;
		}
		if (minutes) {
			value += minutes * 60;
		}
		if (seconds) {
			value += seconds;
		}
		return value;
	},

	get_duration_options: function(docfield) {
		let duration_options = {
			hide_days: docfield.hide_days,
			hide_seconds: docfield.hide_seconds
		};
		return duration_options;
	}
});

// Array de duplicate
if (!Array.prototype.uniqBy) {
	Object.defineProperty(Array.prototype, 'uniqBy', {
		value: function (key) {
			var seen = {};
			return this.filter(function (item) {
				var k = key(item);
				return seen.hasOwnProperty(k) ? false : (seen[k] = true);
			});
		}
	});
	Object.defineProperty(Array.prototype, 'move', {
		value: function(from, to) {
			this.splice(to, 0, this.splice(from, 1)[0]);
		}
	});
}

// Pluralize
String.prototype.plural = function(revert) {
	const plural = {
		"(quiz)$": "$1zes",
		"^(ox)$": "$1en",
		"([m|l])ouse$": "$1ice",
		"(matr|vert|ind)ix|ex$": "$1ices",
		"(x|ch|ss|sh)$": "$1es",
		"([^aeiouy]|qu)y$": "$1ies",
		"(hive)$": "$1s",
		"(?:([^f])fe|([lr])f)$": "$1$2ves",
		"(shea|lea|loa|thie)f$": "$1ves",
		sis$: "ses",
		"([ti])um$": "$1a",
		"(tomat|potat|ech|her|vet)o$": "$1oes",
		"(bu)s$": "$1ses",
		"(alias)$": "$1es",
		"(octop)us$": "$1i",
		"(ax|test)is$": "$1es",
		"(us)$": "$1es",
		"([^s]+)$": "$1s",
	};

	const singular = {
		"(quiz)zes$": "$1",
		"(matr)ices$": "$1ix",
		"(vert|ind)ices$": "$1ex",
		"^(ox)en$": "$1",
		"(alias)es$": "$1",
		"(octop|vir)i$": "$1us",
		"(cris|ax|test)es$": "$1is",
		"(shoe)s$": "$1",
		"(o)es$": "$1",
		"(bus)es$": "$1",
		"([m|l])ice$": "$1ouse",
		"(x|ch|ss|sh)es$": "$1",
		"(m)ovies$": "$1ovie",
		"(s)eries$": "$1eries",
		"([^aeiouy]|qu)ies$": "$1y",
		"([lr])ves$": "$1f",
		"(tive)s$": "$1",
		"(hive)s$": "$1",
		"(li|wi|kni)ves$": "$1fe",
		"(shea|loa|lea|thie)ves$": "$1f",
		"(^analy)ses$": "$1sis",
		"((a)naly|(b)a|(d)iagno|(p)arenthe|(p)rogno|(s)ynop|(t)he)ses$":
			"$1$2sis",
		"([ti])a$": "$1um",
		"(n)ews$": "$1ews",
		"(h|bl)ouses$": "$1ouse",
		"(corpse)s$": "$1",
		"(us)es$": "$1",
		s$: "",
	};

	const irregular = {
		move: "moves",
		foot: "feet",
		goose: "geese",
		sex: "sexes",
		child: "children",
		man: "men",
		tooth: "teeth",
		person: "people",
	};

	const uncountable = [
		"sheep",
		"fish",
		"deer",
		"moose",
		"series",
		"species",
		"money",
		"rice",
		"information",
		"equipment",
	];

	// save some time in the case that singular and plural are the same
	if (uncountable.indexOf(this.toLowerCase()) >= 0) return this;

	// check for irregular forms
	let word;
	let pattern;
	let replace;
	for (word in irregular) {
		if (revert) {
			pattern = new RegExp(irregular[word] + "$", "i");
			replace = word;
		} else {
			pattern = new RegExp(word + "$", "i");
			replace = irregular[word];
		}
		if (pattern.test(this)) return this.replace(pattern, replace);
	}

	let array;
	if (revert) array = singular;
	else array = plural;

	// check for matches using regular expressions
	let reg;
	for (reg in array) {
		pattern = new RegExp(reg, "i");

		if (pattern.test(this)) return this.replace(pattern, array[reg]);
	}

	return this;
};
