import get_dialog_constructor from "../widgets/widget_dialog.js";
export default class Card {
	static get toolbox() {
		return {
			title: 'Card',
			icon: '<svg height="24" width="24" viewBox="0 0 24 24"><path d="M7 15h3a1 1 0 000-2H7a1 1 0 000 2zM19 5H5a3 3 0 00-3 3v9a3 3 0 003 3h14a3 3 0 003-3V8a3 3 0 00-3-3zm1 12a1 1 0 01-1 1H5a1 1 0 01-1-1v-6h16zm0-8H4V8a1 1 0 011-1h14a1 1 0 011 1z"/></svg>'
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
		this.sections = {};
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
		};
	}

	render() {
		this.wrapper = document.createElement('div');
		this._new_card();

		if (this.data && this.data.card_name) {
			this._make_cards(this.data.card_name);
		}

		if (!this.readOnly) {
			this._add_tune_button();
		}

		return this.wrapper;
	}

	_add_tune_button() {
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

	validate(savedData) {
		if (!savedData.card_name) {
			return false;
		}

		return true;
	}

	save(blockContent) {
		return {
			card_name: blockContent.getAttribute('card_name'),
			col: this._getCol(),
			pt: this._getPadding("t"),
			pr: this._getPadding("r"),
			pb: this._getPadding("b"),
			pl: this._getPadding("l"),
			new: this.new_card_widget
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

	_new_card() {
		const dialog_class = get_dialog_constructor('links');
		this.dialog = new dialog_class({
			label: this.label,
			type: 'card',
			primary_action: (widget) => {
				widget.in_customize_mode = 1;
				this.card_widget = frappe.widget.make_widget({
					...widget,
					widget_type: 'links',
					container: this.wrapper,
					options: {
						...this.options,
						on_delete: () => this.api.blocks.delete(),
						on_edit: () => this.on_edit(this.card_widget)
					}
				});
				this.card_widget.customize(this.options);
				this.wrapper.setAttribute("card_name", this.card_widget.label);
				this.new_card_widget = this.card_widget.get_config();
				this._add_tune_button();
			},
		});

		if (!this.readOnly && this.data && !this.data.card_name) { 
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
		this.card_field = new frappe.ui.FieldGroup({
			"fields": ddf_list,
			"parent": parent
		});
		this.card_field.make();
	}

	on_edit(card_obj) {
		let card = card_obj.get_config();
		this.card_widget.widgets = card;
		this.wrapper.setAttribute("card_name", card.label);
		this.new_card_widget = card_obj.get_config();
	}

	_make_cards(card_name) {
		let card = this.config.page_data.cards.items.find(obj => {
			return obj.label == card_name;
		});
		this.wrapper.innerHTML = '';
		card.in_customize_mode = !this.readOnly;
		this.card_widget = new frappe.widget.SingleWidgetGroup({
			container: this.wrapper,
			type: "links",
			options: this.options,
			widgets: card,
			api: this.api,
			block: this.block
		});
		this.wrapper.setAttribute("card_name", card_name);
		if (!this.readOnly) {
			this.card_widget.customize();
		}
	}
}