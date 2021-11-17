export default class Section {
	constructor(parent, df, card_layout, layout) {
		this.layout = layout;
		this.card_layout = card_layout;
		this.parent = parent;
		this.df = df || {};
		this.fields_list = [];
		this.fields_dict = {};

		this.make();

		if (this.df.label && this.df.collapsible && localStorage.getItem(df.css_class + '-closed')) {
			this.collapse();
		}

		this.row = {
			wrapper: this.wrapper
		};

		this.refresh();
	}

	make() {
		let make_card = this.card_layout;
		this.wrapper = $(`<div class="row
				${this.df.is_dashboard_section ? "form-dashboard-section" : "form-section"}
				${ make_card ? "card-section" : "" }">
			`).appendTo(this.parent);
		this.layout && this.layout.sections.push(this);

		if (this.df) {
			if (this.df.label) {
				this.make_head();
			}
			if (this.df.description) {
				this.description_wrapper = $(
					`<div class="col-sm-12 form-section-description">
						${__(this.df.description)}
					</div>`
				);

				this.wrapper.append(this.description_wrapper);
			}
			if (this.df.css_class) {
				this.wrapper.addClass(this.df.css_class);
			}
			if (this.df.hide_border) {
				this.wrapper.toggleClass("hide-border", true);
			}
		}

		this.body = $('<div class="section-body">').appendTo(this.wrapper);

		if (this.df.body_html) {
			this.body.append(this.df.body_html);
		}
	}

	make_head() {
		this.head = $(`
			<div class="section-head">
				${__(this.df.label)}
				<span class="ml-2 collapse-indicator mb-1"></span>
			</div>
		`);

		this.head.appendTo(this.wrapper);
		this.indicator = this.head.find('.collapse-indicator');
		this.indicator.hide();

		if (this.df.collapsible) {
			// show / hide based on status
			this.collapse_link = this.head.on("click", () => {
				this.collapse();
			});
			this.set_icon();
			this.indicator.show();
		}
	}

	refresh(hide) {
		if (!this.df) return;
		// hide if explicitly hidden
		hide = hide || this.df.hidden || this.df.hidden_due_to_dependency;
		this.wrapper.toggleClass("hide-control", !!hide);
	}

	collapse(hide) {
		// unknown edge case
		if (!(this.head && this.body)) {
			return;
		}

		if (hide === undefined) {
			hide = !this.body.hasClass("hide");
		}

		this.body.toggleClass("hide", hide);
		this.head && this.head.toggleClass("collapsed", hide);

		this.set_icon(hide);

		// refresh signature fields
		this.fields_list.forEach((f) => {
			if (f.df.fieldtype == 'Signature') {
				f.refresh();
			}
		});

		// save state for next reload ('' is falsy)
		if (this.df.css_class)
			localStorage.setItem(this.df.css_class + '-closed', hide ? '1' : '');
	}

	set_icon(hide) {
		let indicator_icon = hide ? 'down' : 'up-line';
		this.indicator && this.indicator.html(frappe.utils.icon(indicator_icon, 'sm', 'mb-1'));
	}

	is_collapsed() {
		return this.body.hasClass('hide');
	}

	has_missing_mandatory () {
		let missing_mandatory = false;
		for (let j = 0, l = this.fields_list.length; j < l; j++) {
			const section_df = this.fields_list[j].df;
			if (section_df.reqd && this.layout.doc[section_df.fieldname] == null) {
				missing_mandatory = true;
				break;
			}
		}
		return missing_mandatory;
	}

	hide() {
		this.on_section_toggle(false);
	}

	show() {
		this.on_section_toggle(true);
	}

	on_section_toggle(show) {
		this.wrapper.toggleClass("hide-control", !show);
		// this.on_section_toggle && this.on_section_toggle(show);
	}
}
