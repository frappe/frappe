export default class Chart {
	static get toolbox() {
		return {
			title: 'Chart',
			icon: '<svg height="18" width="18" viewBox="0 0 512 512"><path d="M117.547 234.667H10.88c-5.888 0-10.667 4.779-10.667 10.667v256C.213 507.221 4.992 512 10.88 512h106.667c5.888 0 10.667-4.779 10.667-10.667v-256a10.657 10.657 0 00-10.667-10.666zM309.12 0H202.453c-5.888 0-10.667 4.779-10.667 10.667v490.667c0 5.888 4.779 10.667 10.667 10.667H309.12c5.888 0 10.667-4.779 10.667-10.667V10.667C319.787 4.779 315.008 0 309.12 0zM501.12 106.667H394.453c-5.888 0-10.667 4.779-10.667 10.667v384c0 5.888 4.779 10.667 10.667 10.667H501.12c5.888 0 10.667-4.779 10.667-10.667v-384c0-5.889-4.779-10.667-10.667-10.667z"/></svg>'
		};
	}

	static get isReadOnlySupported() {
		return true;
	}

	constructor({data, api, config, readOnly}) {
		this.data = data;
		this.api = api;
		this.config = config;
		this.readOnly = readOnly;
		this.sections = {};
		this.col = this.data.col ? this.data.col : "12";
		this.pt = this.data.pt ? this.data.pt : "0";
		this.pr = this.data.pr ? this.data.pr : "0";
		this.pb = this.data.pb ? this.data.pb : "0";
		this.pl = this.data.pl ? this.data.pl : "0";
		this.allow_customization = !this.readOnly;
	}

	render() {
		let me = this;
		this.wrapper = document.createElement('div');
		this._make_fieldgroup(this.wrapper, [{
			fieldtype: "Select", 
			label: "Chart Name", 
			fieldname: "chart_name",
			options: this.config.page_data.charts.items.map(({ chart_name }) => chart_name),
			change: function() {
				if (this.value) {
					me._make_charts(this.value);
				}
			}
		}]);
		if (this.data && this.data.chart_name) {
			this._make_charts(this.data.chart_name);
		}
		return this.wrapper;
	}

	save(blockContent) {
		return {
			chart_name: blockContent.getAttribute('chart_name'),
			col: this._getCol(),
			pt: this._getPadding("t"),
			pr: this._getPadding("r"),
			pb: this._getPadding("b"),
			pl: this._getPadding("l")
		};
	}

	rendered() {
		var e = this.wrapper.parentNode.parentNode;
		e.classList.add("col-" + this.col);
		e.classList.add("pt-" + this.pt);
		e.classList.add("pr-" + this.pr);
		e.classList.add("pb-" + this.pb);
		e.classList.add("pl-" + this.pl);
	}

	_getCol() {
		var e = 12;
		t = "col-12";
		n = this.wrapper.parentNode.parentNode;
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
		var e = arguments.length > 0 && void 0 !== arguments[0] ? arguments[0] : "l";
		t = 0;
		n = "p" + e + "-0";
		r = this.wrapper.parentNode.parentNode;
		a = new RegExp(/\pl-.+?\b/, "g");
		i = new RegExp(/\pr-.+?\b/, "g");
		o = new RegExp(/\pt-.+?\b/, "g");
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
		this.chart_field = new frappe.ui.FieldGroup({
			"fields": ddf_list,
			"parent": parent
		});
		this.chart_field.make();
	}

	_make_charts(chart_name) {
		let chart = this.config.page_data.charts.items.find(obj => {
			return obj.chart_name == chart_name;
		});
		this.wrapper.innerHTML = '';
		this.sections = {};
		chart.in_customize_mode = !this.readOnly;
		this.sections["charts"] = new frappe.widget.SingleWidgetGroup({
			container: this.wrapper,
			type: "chart",
			columns: 1,
			class_name: "widget-charts",
			// hidden: Boolean(this.onboarding_widget),
			options: {
				allow_sorting: this.allow_customization,
				allow_create: this.allow_customization,
				allow_delete: this.allow_customization,
				allow_hiding: false,
				allow_edit: true,
				max_widget_count: 2,
			},
			widgets: chart
		});
		this.wrapper.setAttribute("chart_name", chart_name);
		if (!this.readOnly) {
			this.sections["charts"].customize();
		}
	}
}