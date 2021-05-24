import get_dialog_constructor from "../widgets/widget_dialog.js";
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

	constructor({data, api, config, readOnly, block}) {
		this.data = data;
		this.api = api;
		this.block = block;
		this.config = config;
		this.readOnly = readOnly;
		this.col = this.data.col ? this.data.col : "12";
		this.pt = this.data.pt ? this.data.pt : "0";
		this.pr = this.data.pr ? this.data.pr : "0";
		this.pb = this.data.pb ? this.data.pb : "0";
		this.pl = this.data.pl ? this.data.pl : "0";
		this.allow_customization = !this.readOnly;
		this.options = {
			allow_sorting: this.allow_customization,
			allow_create: this.allow_customization,
			allow_delete: this.allow_customization,
			allow_hiding: false,
			allow_edit: true,
			max_widget_count: 2,
		};
	}

	render() {
		this.wrapper = document.createElement('div');
		this._new_chart();

		if (this.data && this.data.chart_name) {
			this._make_charts(this.data.chart_name);
		}

		if (!this.readOnly) {
			let $widget_control = $(this.wrapper).find('.widget-control');
			this.add_custom_button(
				frappe.utils.icon('dot-horizontal', 'xs'),
				(event) => {
					let evn = event;
					!$('.ce-settings.ce-settings--opened').length &&
					setTimeout(() => {
						this.api.toolbar.toggleBlockSettings();
						var position = $(evn.target).offset();
						$('.ce-settings.ce-settings--opened').offset({
							top: position.top + 25,
							left: position.left - 77
						});
					}, 50);
				},
				"tune-btn",
				`${__('Tune')}`,
				null,
				$widget_control
			);
		}

		return this.wrapper;
	}

	add_custom_button(html, action, class_name = "", title="", btn_type, wrapper) {
		if (!btn_type) btn_type = 'btn-secondary';
		let button = $(
			`<button class="btn ${btn_type} btn-xs ${class_name}" title="${title}">${html}</button>`
		);
		button.click(event => {
			event.stopPropagation();
			action && action(event);
		});
		wrapper.prepend(button);
	}

	save(blockContent) {
		return {
			chart_name: blockContent.getAttribute('chart_name'),
			col: this._getCol(),
			pt: this._getPadding("t"),
			pr: this._getPadding("r"),
			pb: this._getPadding("b"),
			pl: this._getPadding("l"),
			new: this.new_chart_widget
		};
	}

	rendered() {
		var e = this.wrapper.closest('.ce-block');
		e.classList.add("col-" + this.col);
		e.classList.add("pt-" + this.pt);
		e.classList.add("pr-" + this.pr);
		e.classList.add("pb-" + this.pb);
		e.classList.add("pl-" + this.pl);
	}

	_new_chart() {
		const dialog_class = get_dialog_constructor('chart');
		this.dialog = new dialog_class({
			label: this.label,
			type: 'chart',
			primary_action: (widget) => {
				widget.in_customize_mode = 1;
				this.chart_widget = frappe.widget.make_widget({
					...widget,
					widget_type: 'chart',
					container: this.wrapper,
					options: {
						...this.options,
						on_delete: () => this.api.blocks.delete(),
						on_edit: () => this.on_edit(this.chart_widget)
					}
				});
				this.chart_widget.customize(this.options);
				this.wrapper.setAttribute("chart_name", this.chart_widget.label);
				this.new_chart_widget = this.chart_widget.get_config();
			},
		});

		if (!this.readOnly && this.data && !this.data.chart_name) { 
			this.dialog.make();
		}
	}

	_getCol() {
		var e = 12;
		var t = "col-12";
		var n = this.wrapper.closest('.ce-block');
		var r = new RegExp(/\bcol-.+?\b/, "g");
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
		var t = 0;
		var n = "p" + e + "-0";
		var r = this.wrapper.closest('.ce-block');
		var a = new RegExp(/\pl-.+?\b/, "g");
		var i = new RegExp(/\pr-.+?\b/, "g");
		var o = new RegExp(/\pt-.+?\b/, "g");
		var c = new RegExp(/\pb-.+?\b/, "g");
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

	on_edit(chart_obj) {
		let chart = chart_obj.get_config();
		this.chart_widget.widgets = chart;
		this.wrapper.setAttribute("chart_name", chart.label);
		this.new_chart_widget = chart_obj.get_config();
	}

	_make_charts(chart_name) {
		let chart = this.config.page_data.charts.items.find(obj => {
			return obj.label == chart_name;
		});
		if (!chart) return;
		this.wrapper.innerHTML = '';
		this.chart_widget = new frappe.widget.SingleWidgetGroup({
			container: this.wrapper,
			type: "chart",
			class_name: "widget-charts",
			options: this.options,
			widgets: chart,
			api: this.api,
			block: this.block
		});
		this.wrapper.setAttribute("chart_name", chart_name);
		if (!this.readOnly) {
			this.chart_widget.customize();
		}
	}
}