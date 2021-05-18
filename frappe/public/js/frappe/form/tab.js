export default class Tab {
	constructor(layout, df) {
		this.layout = layout;
		this.df = df || {};
		this.label = this.df && this.df.label || 'Details';
		this.fields_list = [];
		this.fields_dict = {};
		this.make();
		this.refresh();
	}

	make() {
		if (!this.layout.page) {
			this.layout.page = $('<div class="form-page"></div>').appendTo(this.layout.wrapper);
		}

		const id = `${frappe.scrub(this.layout.doctype, '-')}-${this.df.fieldname}`;
		this.parent = $(`<li class="nav-item">
			<a class="nav-link ${this.df.active ? "active": ""}" id="${id}-tab"
				data-toggle="tab" href="#${id}" role="tab"
				aria-controls="home" aria-selected="true">
					${__(this.label)}
			</a>
		</li>`).appendTo(this.layout.tabs_list);

		this.wrapper = $(`<div class="tab-pane fade show ${this.df.active ? "active": ""}"
			id="${id}" role="tabpanel" aria-labelledby="${id}-tab">
		`).appendTo(this.layout.tabs_content);

		this.layout.tabs.push(this);
	}

	set_content() {

	}

	refresh() {
		if (!this.df) return;

		// hide if explicitly hidden
		let hide = this.df.hidden || this.df.hidden_due_to_dependency;
		if (!hide && this.layout && this.layout.frm && !this.layout.frm.get_perm(this.df.permlevel || 0, "read")) {
			hide = true;
		}
		
		hide && this.toggle(false);
	}

	toggle(show) {
	 	this.parent.toggleClass('hide', !show);
		this.wrapper.toggleClass('hide', !show);
		this.parent.toggleClass('show', show);
		this.wrapper.toggleClass('show', show);
		this.hidden = !show;
	}

	show() {
		this.parent.show();
	}

	hide() {
		this.parent.hide();
	}

	set_active() {
		this.parent.find('.nav-link').tab('show');
		this.wrapper.addClass('show');
	}

	is_active() {
		return this.wrapper.hasClass('active');
	}

	is_hidden() {
		this.wrapper.hasClass('hide')
			&& this.parent.hasClass('hide');
	}
}
