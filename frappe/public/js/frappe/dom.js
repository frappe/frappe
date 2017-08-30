// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// add a new dom element
frappe.provide('frappe.dom');

frappe.dom = {
	id_count: 0,
	freeze_count: 0,
	by_id: function(id) {
		return document.getElementById(id);
	},
	set_unique_id: function(ele) {
		var $ele = $(ele);
		if($ele.attr('id')) {
			return $ele.attr('id');
		}
		var id = 'unique-' + frappe.dom.id_count;
		$ele.attr('id', id);
		frappe.dom.id_count++;
		return id;
	},
	eval: function(txt) {
		if(!txt) return;
		var el = document.createElement('script');
		el.appendChild(document.createTextNode(txt));
		// execute the script globally
		document.getElementsByTagName('head')[0].appendChild(el);
	},
	remove_script_and_style: function(txt) {
		var div = document.createElement('div');
		div.innerHTML = txt;
		var found = false;
		["script", "style", "noscript", "title", "meta", "base", "head"].forEach(function(e, i) {
			var elements = div.getElementsByTagName(e);
			var i = elements.length;
			while (i--) {
				found = true;
				elements[i].parentNode.removeChild(elements[i]);
			}
		});

		// remove links with rel="stylesheet"
		var elements = div.getElementsByTagName('link');
		var i = elements.length;
		while (i--) {
			if (elements[i].getAttribute("rel")=="stylesheet"){
				found = true;
				elements[i].parentNode.removeChild(elements[i]);
			}
		}
		if(found) {
			return div.innerHTML;
		} else {
			// don't disturb
			return txt;
		}
	},
	is_element_in_viewport: function (el) {

		//special bonus for those using jQuery
		if (typeof jQuery === "function" && el instanceof jQuery) {
			el = el[0];
		}

		var rect = el.getBoundingClientRect();

		return (
			rect.top >= 0
			&& rect.left >= 0
			// && rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) && /*or $(window).height() */
			// && rect.right <= (window.innerWidth || document.documentElement.clientWidth) /*or $(window).width() */
		);
	},

	set_style: function(txt, id) {
		if(!txt) return;

		var se = document.createElement('style');
		se.type = "text/css";

		if (id) {
			var element = document.getElementById(id);
			if (element) {
				element.parentNode.removeChild(element);
			}
			se.id = id;
		}

		if (se.styleSheet) {
			se.styleSheet.cssText = txt;
		} else {
			se.appendChild(document.createTextNode(txt));
		}
		document.getElementsByTagName('head')[0].appendChild(se);
		return se;
	},
	add: function(parent, newtag, className, cs, innerHTML, onclick) {
		if(parent && parent.substr)parent = frappe.dom.by_id(parent);
		var c = document.createElement(newtag);
		if(parent)
			parent.appendChild(c);

		// if image, 3rd parameter is source
		if(className) {
			if(newtag.toLowerCase()=='img')
				c.src = className
			else
				c.className = className;
		}
		if(cs) frappe.dom.css(c,cs);
		if(innerHTML) c.innerHTML = innerHTML;
		if(onclick) c.onclick = onclick;
		return c;
	},
	css: function(ele, s) {
		if(ele && s) {
			$.extend(ele.style, s);
		}
		return ele;
	},
	freeze: function(msg, css_class) {
		// blur
		if(!$('#freeze').length) {
			var freeze = $('<div id="freeze" class="modal-backdrop fade"></div>')
				.on("click", function() {
					if (cur_frm && cur_frm.cur_grid) {
						cur_frm.cur_grid.toggle_view();
						return false;
					}
				})
				.appendTo("#body_div");

			freeze.html(repl('<div class="freeze-message-container"><div class="freeze-message"><p class="lead">%(msg)s</p></div></div>',
				{msg: msg || ""}));

			setTimeout(function() { freeze.addClass("in") }, 1);

		} else {
			$("#freeze").addClass("in");
		}

		if (css_class) {
			$("#freeze").addClass(css_class);
		}

		frappe.dom.freeze_count++;
	},
	unfreeze: function() {
		if(!frappe.dom.freeze_count) return; // anything open?
		frappe.dom.freeze_count--;
		if(!frappe.dom.freeze_count) {
			var freeze = $('#freeze').removeClass("in").remove();
		}
	},
	save_selection: function() {
		// via http://stackoverflow.com/questions/5605401/insert-link-in-contenteditable-element
		if (window.getSelection) {
			var sel = window.getSelection();
			if (sel.getRangeAt && sel.rangeCount) {
				var ranges = [];
				for (var i = 0, len = sel.rangeCount; i < len; ++i) {
					ranges.push(sel.getRangeAt(i));
				}
				return ranges;
			}
		} else if (document.selection && document.selection.createRange) {
			return document.selection.createRange();
		}
		return null;
	},
	restore_selection: function(savedSel) {
		if (savedSel) {
			if (window.getSelection) {
				var sel = window.getSelection();
				sel.removeAllRanges();
				for (var i = 0, len = savedSel.length; i < len; ++i) {
					sel.addRange(savedSel[i]);
				}
			} else if (document.selection && savedSel.select) {
				savedSel.select();
			}
		}
	},
	is_touchscreen: function() {
		return ('ontouchstart' in window)
	}
}

frappe.ellipsis = function(text, max) {
	if(!max) max = 20;
	text = cstr(text);
	if(text.length > max) {
		text = text.substr(0, max) + '...';
	}
	return text;
};

frappe.run_serially = function(tasks) {
	var result = Promise.resolve();
	tasks.forEach(task => {
		if(task) {
			result = result.then ? result.then(task) : Promise.resolve();
		}
	});
	return result;
};

frappe.timeout = seconds => {
	return new Promise((resolve) => {
		setTimeout(() => resolve(), seconds * 1000);
	});
};

frappe.scrub = function(text) {
	return text.replace(/ /g, "_").toLowerCase();
};

frappe.get_modal = function(title, content) {
	return $(frappe.render_template("modal", {title:title, content:content})).appendTo(document.body);
};

// add <option> list to <select>
(function($) {
	$.fn.add_options = function(options_list) {
		// create options
		for(var i=0, j=options_list.length; i<j; i++) {
			var v = options_list[i];
			if (is_null(v)) {
				var value = null;
				var label = null;
			} else {
				var is_value_null = is_null(v.value);
				var is_label_null = is_null(v.label);

				if (is_value_null && is_label_null) {
					var value = v;
					var label = __(v);
				} else {
					var value = is_value_null ? "" : v.value;
					var label = is_label_null ? __(value) : __(v.label);
				}
			}
			$('<option>').html(cstr(label)).attr('value', value).appendTo(this);
		}
		// select the first option
		this.selectedIndex = 0;
		return $(this);
	}
	$.fn.set_working = function() {
		this.prop('disabled', true);
	}
	$.fn.done_working = function() {
		this.prop('disabled', false);
	}
})(jQuery);

(function($) {
	function pasteIntoInput(el, text) {
		el.focus();
		if (typeof el.selectionStart == "number") {
			var val = el.value;
			var selStart = el.selectionStart;
			el.value = val.slice(0, selStart) + text + val.slice(el.selectionEnd);
			el.selectionEnd = el.selectionStart = selStart + text.length;
		} else if (typeof document.selection != "undefined") {
			var textRange = document.selection.createRange();
			textRange.text = text;
			textRange.collapse(false);
			textRange.select();
		}
	}

	function allowTabChar(el) {
		$(el).keydown(function(e) {
			if (e.which == 9) {
				pasteIntoInput(this, "\t");
				return false;
			}
		});

		// For Opera, which only allows suppression of keypress events, not keydown
		$(el).keypress(function(e) {
			if (e.which == 9) {
				return false;
			}
		});
	}

	$.fn.allowTabs = function() {
		if (this.jquery) {
			this.each(function() {
				if (this.nodeType == 1) {
					var nodeName = this.nodeName.toLowerCase();
					if (nodeName == "textarea" || (nodeName == "input" && this.type == "text")) {
						allowTabChar(this);
					}
				}
			})
		}
		return this;
	}
})(jQuery);