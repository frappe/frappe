export default class Shortcut {
	static get toolbox() {
		return {
			title: 'Shortcut',
			icon: '<svg height="18" width="18" viewBox="0 0 122.88 115.71"><path d="M116.56 3.69l-3.84 53.76-17.69-15c-19.5 8.72-29.96 23.99-30.51 43.77-17.95-26.98-7.46-50.4 12.46-65.97L64.96 3l51.6.69zM28.3 0h14.56v19.67H32.67c-4.17 0-7.96 1.71-10.72 4.47-2.75 2.75-4.46 6.55-4.46 10.72l-.03 46c.03 4.16 1.75 7.95 4.5 10.71 2.76 2.76 6.56 4.48 10.71 4.48h58.02c4.15 0 7.95-1.72 10.71-4.48 2.76-2.76 4.48-6.55 4.48-10.71V73.9h17.01v11.33c0 7.77-3.2 17.04-8.32 22.16-5.12 5.12-12.21 8.32-19.98 8.32H28.3c-7.77 0-14.86-3.2-19.98-8.32C3.19 102.26 0 95.18 0 87.41l.03-59.1c-.03-7.79 3.16-14.88 8.28-20C13.43 3.19 20.51 0 28.3 0z" fill-rule="evenodd" clip-rule="evenodd"/></svg>'
		};
	}

	static get isReadOnlySupported() {
		return true;
	}

	constructor({data, api, config, readOnly}){
		this.data = data;
		this.api = api;
		this.config = config;
		this.readOnly = readOnly;
		this.sections = {};
		this.col = this.data.col ? this.data.col : "12",
		this.pt = this.data.pt ? this.data.pt : "0",
		this.pr = this.data.pr ? this.data.pr : "0",
		this.pb = this.data.pb ? this.data.pb : "0",
		this.pl = this.data.pl ? this.data.pl : "0"
	}

	render() {
		let me = this;
		this.wrapper = document.createElement('div');
		this._make_fieldgroup(this.wrapper, [{
			fieldtype: "Select", 
			label: "Shortcut Name", 
			fieldname: "shortcut_name",
			options: this.config.page_data.shortcuts.items.map(({ label }) => label),
			change: function() {
				if (this.value) {
					me._make_shortcuts(this.value);
				}
			}
		}]);
		if (this.data && this.data.shortcut_name) {
			this._make_shortcuts(this.data.shortcut_name)
		}
		return this.wrapper;
	}

	save(blockContent) {
		return {
			shortcut_name: blockContent.getAttribute('shortcut_name'),
			col: this._getCol(),
			pt: this._getPadding("t"),
			pr: this._getPadding("r"),
			pb: this._getPadding("b"),
			pl: this._getPadding("l")
		}
	}

	rendered() {
		var e = this.wrapper.parentNode.parentNode;
		e.classList.add("col-" + this.col)
		e.classList.add("pt-" + this.pt)
		e.classList.add("pr-" + this.pr)
		e.classList.add("pb-" + this.pb)
		e.classList.add("pl-" + this.pl)
	}

	_getCol() {
		var e = 12,
		t = "col-12",
		n = this.wrapper.parentNode.parentNode,
		r = new RegExp(/\bcol-.+?\b/, "g");
		if (n.className.match(r)) {
			n.classList.forEach(function (e) {
				e.match(r) && (t = e);
			});
			var a = t.split("-");
			e = parseInt(a[1]);
		}
		return e;
	}

	_getPadding() {
		var e = arguments.length > 0 && void 0 !== arguments[0] ? arguments[0] : "l",
		t = 0,
		n = "p" + e + "-0",
		r = this.wrapper.parentNode.parentNode,
		a = new RegExp(/\pl-.+?\b/, "g"),
		i = new RegExp(/\pr-.+?\b/, "g"),
		o = new RegExp(/\pt-.+?\b/, "g"),
		c = new RegExp(/\pb-.+?\b/, "g");
		if ("l" == e) {
			if (r.className.match(a)) {
				r.classList.forEach(function (e) {
					e.match(a) && (n = e);
				});
				var s = n.split("-");
				t = parseInt(s[1]);
			}
		} else if ("r" == e) {
			if (r.className.match(i)) {
				r.classList.forEach(function (e) {
					e.match(i) && (n = e);
				});
				var l = n.split("-");
				t = parseInt(l[1]);
			}
		} else if ("t" == e) {
			if (r.className.match(o)) {
				r.classList.forEach(function (e) {
					e.match(o) && (n = e);
				});
				var u = n.split("-");
				t = parseInt(u[1]);
			}
		} else if ("b" == e && r.className.match(c)) {
			r.classList.forEach(function (e) {
				e.match(c) && (n = e);
			});
			var p = n.split("-");
			t = parseInt(p[1]);
		}
		return t;
	}

	_make_fieldgroup(parent, ddf_list) {
		this.shortcut_field = new frappe.ui.FieldGroup({
			"fields": ddf_list,
			"parent": parent
		});
		this.shortcut_field.make();
	}

	_make_shortcuts(shortcut_name) {
		let shortcut = this.config.page_data.shortcuts.items.find(obj => {
			return obj.label == shortcut_name
		});
		this.wrapper.innerHTML = '';
		this.sections = {};
		this.sections["shortcuts"] = new frappe.widget.SingleWidgetGroup({
			container: this.wrapper,
			type: "shortcut",
			columns: 3,
			options: {
				allow_sorting: this.allow_customization,
				allow_create: this.allow_customization,
				allow_delete: this.allow_customization,
				allow_hiding: false,
				allow_edit: true,
			},
			widgets: shortcut
		});
		this.wrapper.setAttribute("shortcut_name", shortcut_name);
	}
}