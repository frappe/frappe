// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide('frappe.utils');

frappe.utils = {
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
	is_html: function(txt) {
		if (!txt) return false;

		if(txt.indexOf("<br>")==-1 && txt.indexOf("<p")==-1
			&& txt.indexOf("<img")==-1 && txt.indexOf("<div")==-1) {
			return false;
		}
		return true;
	},
	strip_whitespace: function(html) {
		return (html || "").replace(/<p>\s*<\/p>/g, "").replace(/<br>(\s*<br>\s*)+/g, "<br><br>");
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
	is_url: function(txt) {
		return txt.toLowerCase().substr(0,7)=='http://'
			|| txt.toLowerCase().substr(0,8)=='https://'
	},
	remove_script_and_style: function(txt) {
		var div = document.createElement('div');
		div.innerHTML = txt;
		["script", "style", "noscript", "title", "meta", "base", "head"].forEach(function(e, i) {
			var elements = div.getElementsByTagName(e);
			var i = elements.length;
			while (i--) {
				elements[i].parentNode.removeChild(elements[i]);
			}
		});
		return div.innerHTML;
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
	filter_dict: function(dict, filters) {
		var ret = [];
		if(typeof filters=='string') {
			return [dict[filters]]
		}
		$.each(dict, function(i, d) {
			for(key in filters) {
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
	set_intro: function(me, wrapper, txt, append, indicator) {
		if(!me.intro_area) {
			me.intro_area = $('<div class="intro-area">')
				.prependTo(wrapper);
		}
		if(txt) {
			if(!append) {
				me.intro_area.empty();
			}
			if(indicator) {
				me.intro_area.html('<div class="indicator '+indicator+'">'+txt+'</div>')
			} else {
				me.intro_area.html('<p class="text-muted">'+txt+'</div>')
			}
		} else {
			me.intro_area.remove();
			me.intro_area = null;
		}
	},
	set_footnote: function(me, wrapper, txt) {
		if(!me.footnote_area) {
			me.footnote_area = $('<div class="text-muted footnote-area">')
				.appendTo(wrapper);
		}

		if(txt) {
			if(txt.search(/<p>/)==-1) txt = '<p>' + txt + '</p>';
			me.footnote_area.html(txt);
		} else {
			me.footnote_area.remove();
			me.footnote_area = null;
		}
		return me.footnote_area;
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
				regExp = /^((([a-z]|\d|[!#\$%&'\*\+\-\/=\?\^_`{\|}~]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])+(\.([a-z]|\d|[!#\$%&'\*\+\-\/=\?\^_`{\|}~]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])+)*)|((\x22)((((\x20|\x09)*(\x0d\x0a))?(\x20|\x09)+)?(([\x01-\x08\x0b\x0c\x0e-\x1f\x7f]|\x21|[\x23-\x5b]|[\x5d-\x7e]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])|(\\([\x01-\x09\x0b\x0c\x0d-\x7f]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF]))))*(((\x20|\x09)*(\x0d\x0a))?(\x20|\x09)+)?(\x22)))@((([a-z]|\d|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])|(([a-z]|\d|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])([a-z]|\d|-|\.|_|~|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])*([a-z]|\d|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])))\.)+(([a-z]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])|(([a-z]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])([a-z]|\d|-|\.|_|~|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])*([a-z]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])))$/i;
				break;
			case "url":
				regExp = /^(https?|s?ftp):\/\/(((([a-z]|\d|-|\.|_|~|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])|(%[\da-f]{2})|[!\$&'\(\)\*\+,;=]|:)*@)?(((\d|[1-9]\d|1\d\d|2[0-4]\d|25[0-5])\.(\d|[1-9]\d|1\d\d|2[0-4]\d|25[0-5])\.(\d|[1-9]\d|1\d\d|2[0-4]\d|25[0-5])\.(\d|[1-9]\d|1\d\d|2[0-4]\d|25[0-5]))|((([a-z]|\d|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])|(([a-z]|\d|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])([a-z]|\d|-|\.|_|~|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])*([a-z]|\d|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])))\.)+(([a-z]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])|(([a-z]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])([a-z]|\d|-|\.|_|~|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])*([a-z]|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])))\.?)(:\d*)?)(\/((([a-z]|\d|-|\.|_|~|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])|(%[\da-f]{2})|[!\$&'\(\)\*\+,;=]|:|@)+(\/(([a-z]|\d|-|\.|_|~|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])|(%[\da-f]{2})|[!\$&'\(\)\*\+,;=]|:|@)*)*)?)?(\?((([a-z]|\d|-|\.|_|~|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])|(%[\da-f]{2})|[!\$&'\(\)\*\+,;=]|:|@)|[\uE000-\uF8FF]|\/|\?)*)?(#((([a-z]|\d|-|\.|_|~|[\u00A0-\uD7FF\uF900-\uFDCF\uFDF0-\uFFEF])|(%[\da-f]{2})|[!\$&'\(\)\*\+,;=]|:|@)|\/|\?)*)?$/i;
				break;
			case "dateIso":
				regExp = /^(\d{4})\D?(0[1-9]|1[0-2])\D?([12]\d|0[1-9]|3[01])$/;
				break;
			default:
				return false;
				break;
		}

		// test regExp if not null
		return '' !== val ? regExp.test( val ) : false;
	},
	guess_style: function(text, default_style, _colour) {
		var style = default_style || "default";
		var colour = "darkgrey";
		if(text) {
			if(has_words(["Pending", "Review", "Medium", "Not Approved", "Pending"], text)) {
				style = "warning";
				colour = "orange";
			} else if(has_words(["Open", "Urgent", "High"], text)) {
				style = "danger";
				colour = "red";
			} else if(has_words(["Closed", "Finished", "Converted", "Completed", "Confirmed",
				"Approved", "Yes", "Active", "Available", "Paid"], text)) {
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
        while (arrMatches = objPattern.exec( strData )){

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
		frappe.msgprint("Note: Changing the Page Name will break previous URL to this page.");
	},

	if_notify_permitted: function(callback) {
		if (Notify.needsPermission) {
			Notify.requestPermission(callback);
		} else {
			callback && callback();
		}
	},

	notify: function(subject, body, route, onclick) {
		if(!route) route = "messages";
		if(!onclick) onclick = function() {
			frappe.set_route(route);
		}

		frappe.utils.if_notify_permitted(function() {
			var notify = new Notify(subject, {
			    body: body.replace(/<[^>]*>/g, ""),
			    notifyClick: onclick
			});
			notify.show();
		});
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

	}
};
