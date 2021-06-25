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
	get_unique_id: function() {
		const id = 'unique-' + frappe.dom.id_count;
		frappe.dom.id_count++;
		return id;
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
		const evil_tags = ["script", "style", "noscript", "title", "meta", "base", "head"];
		const regex = new RegExp(evil_tags.map(tag => `<${tag}>.*<\\/${tag}>`).join('|'), 's');
		if (!regex.test(txt)) {
			// no evil tags found, skip the DOM method entirely!
			return txt;
		}

		var div = document.createElement('div');
		div.innerHTML = txt;
		var found = false;
		evil_tags.forEach(function(e) {
			var elements = div.getElementsByTagName(e);
			i = elements.length;
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
	is_element_in_viewport: function (el, tolerance=0) {

		//special bonus for those using jQuery
		if (typeof jQuery === "function" && el instanceof jQuery) {
			el = el[0];
		}

		var rect = el.getBoundingClientRect();

		return (
			rect.top + tolerance >= 0
			&& rect.left + tolerance >= 0
			&& rect.bottom - tolerance <= $(window).height()
			&& rect.right - tolerance <= $(window).width()
		);
	},

	is_element_in_modal(element) {
		return Boolean($(element).parents('.modal').length);
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
	activate: function($parent, $child, common_class, active_class='active') {
		$parent.find(`.${common_class}.${active_class}`)
			.removeClass(active_class);
		$child.addClass(active_class);
	},
	freeze: function(msg, css_class) {
		// blur
		if (!$('#freeze').length) {
			var freeze = $('<div id="freeze" class="modal-backdrop fade"></div>')
				.on("click", function() {
					if (cur_frm && cur_frm.cur_grid) {
						cur_frm.cur_grid.toggle_view();
						return false;
					}
				})
				.appendTo("#body");

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
	},
	handle_broken_images(container) {
		$(container).find('img').on('error', (e) => {
			const $img = $(e.currentTarget);
			$img.addClass('no-image');
		});
	},
	scroll_to_bottom(container) {
		const $container = $(container);
		$container.scrollTop($container[0].scrollHeight);
	},
	file_to_base64(file_obj) {
		return new Promise(resolve => {
			const reader = new FileReader();
			reader.onload = function() {
				resolve(reader.result);
			};
			reader.readAsDataURL(file_obj);
		});
	},
	scroll_to_section(section_name) {
		setTimeout(() => {
			const section = $(`a:contains("${section_name}")`);
			if (section.length) {
				if(section.parent().hasClass('collapsed')) {
					// opens the section
					section.click();
				}
				frappe.ui.scroll(section.parent().parent());
			}
		}, 200);
	},
	pixel_to_inches(pixels) {
		const div = $('<div id="dpi" style="height: 1in; width: 1in; left: 100%; position: fixed; top: 100%;"></div>');
		div.appendTo(document.body);

		const dpi_x = document.getElementById('dpi').offsetWidth;
		const inches = pixels / dpi_x;
		div.remove();

		return inches;
	}
};

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

frappe.load_image = (src, onload, onerror, preprocess = () => {}) => {
	var tester = new Image();
	tester.onload = function() {
		onload(this);
	};
	tester.onerror = onerror;

	preprocess(tester);
	tester.src = src;
}

frappe.timeout = seconds => {
	return new Promise((resolve) => {
		setTimeout(() => resolve(), seconds * 1000);
	});
};

frappe.scrub = function(text, spacer='_') {
	return text.replace(/ /g, spacer).toLowerCase();
};

frappe.unscrub = function(txt) {
	return frappe.model.unscrub(txt);
};

frappe.get_data_pill = (label, target_id=null, remove_action=null, image=null) => {
	let data_pill_wrapper = $(`
		<button class="data-pill btn">
			<div class="flex align-center ellipsis">
				${image ? image : ''}
				<span class="pill-label ${image ? "ml-2" : ""}">${label}</span>
			</div>
		</button>
	`);

	if (remove_action) {
		let remove_btn = $(`
			<span class="remove-btn cursor-pointer">
				${frappe.utils.icon('close', 'sm')}
			</span>
		`).click(() => {
			remove_action(target_id || label, data_pill_wrapper);
		});
		data_pill_wrapper.append(remove_btn);
	}

	return data_pill_wrapper;
};

frappe.get_modal = function(title, content) {
	return $(`<div class="modal fade" style="overflow: auto;" tabindex="-1">
		<div class="modal-dialog">
			<div class="modal-content">
				<div class="modal-header">
					<div class="fill-width flex title-section">
						<span class="indicator hidden"></span>
						<h4 class="modal-title">${title}</h4>
					</div>
					<div class="modal-actions">
						<button class="btn btn-modal-minimize btn-link hide">
							${frappe.utils.icon('collapse')}
						</button>
						<button class="btn btn-modal-close btn-link" data-dismiss="modal">
							${frappe.utils.icon('close-alt', 'sm', 'close-alt')}
						</button>
					</div>
				</div>
				<div class="modal-body ui-front">${content}</div>
				<div class="modal-footer hide">
					<div class="custom-actions"></div>
					<div class="standard-actions">
						<button type="button" class="btn btn-secondary btn-sm hide btn-modal-secondary">
						</button>
						<button type="button" class="btn btn-primary btn-sm hide btn-modal-primary">
							${__("Confirm")}
						</button>
					</div>
				</div>
			</div>
		</div>
	</div>`);
};

frappe.is_online = function() {
	if (frappe.boot.developer_mode == 1) {
		// always online in developer_mode
		return true;
	}
	if ('onLine' in navigator) {
		return navigator.onLine;
	}
	return true;
};

// bind online/offline events
$(window).on('online', function() {
	frappe.show_alert({
		indicator: 'green',
		message: __('You are connected to internet.')
	});
});

$(window).on('offline', function() {
	frappe.show_alert({
		indicator: 'orange',
		message: __('Connection lost. Some features might not work.')
	});
});
