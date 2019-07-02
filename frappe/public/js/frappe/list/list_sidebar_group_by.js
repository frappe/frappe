
frappe.provide('frappe.views');

frappe.views.ListGroupBy = class ListGroupBy {

    constructor(opts) {
        $.extend(this, opts);
        this.user_settings = frappe.get_user_settings(this.doctype);
        this.group_by_fields = [];
        if(this.user_settings.group_by_fields) {
			this.group_by_fields = this.user_settings.group_by_fields;
			this.add_group_by_dropdown_fields(this.group_by_fields);
        }
        this.add_group_by_dropdown_fields(['assigned_to']);
        this.make_group_by_fields_modal();
        console.log(this);
    }

    make_group_by_fields_modal() {
        let d = new frappe.ui.Dialog ({
			title: __("Add Filter By"),
			fields: this.get_group_by_dropdown_fields()
		});
		d.set_primary_action("Add", (values) => {
			this.page.sidebar.find('.group-by-field a').not("[data-fieldname='assigned_to']").remove();
			let fields = values[this.doctype];
			delete values[this.doctype];
			if(!fields) {
				frappe.model.user_settings.save(this.doctype,'group_by_fields',null);
			} else {
				this.add_group_by_dropdown_fields(fields);
				frappe.model.user_settings.save(this.doctype,'group_by_fields',fields);
			}
			d.hide();
		});

		this.page.sidebar.find(".add-list-group-by a ").on("click", () => {
			d.show();
		});
    }

    add_group_by_dropdown_fields(fields) {
		if(fields) {
            console.log('jere');
			fields.forEach((field)=> {
				let field_label = field === 'assigned_to'? 'Assigned To': frappe.meta.get_label(this.doctype, field);
				this.list_group_by_dropdown = $(frappe.render_template("list_sidebar_group_by", {
					field_label: field_label,
					group_by_field: field,
				}));

				this.list_group_by_dropdown.on('click', (e)=> {
					let dropdown = $(e.currentTarget).find('.group-by-dropdown');
					dropdown.find('.group-by-loading').show();
					dropdown.find('.group-by-item').remove();
					this.get_group_by_count(field, dropdown);
				});
				this.list_group_by_dropdown.insertAfter(this.page.sidebar.find('.list-group-by-label'));
			});
		}
    }
    
    get_group_by_dropdown_fields() {
		let group_by_fields = [];
		let fields = this.list_view.meta.fields.filter((f)=> ["Select", "Link"].includes(f.fieldtype));
		group_by_fields.push({
			label: __(this.doctype),
			fieldname: this.doctype,
			fieldtype: 'MultiCheck',
			columns: 2,
			options: fields
				.map(df => ({
					label: __(df.label),
					value: df.fieldname,
					checked: this.group_by_fields.includes(df.fieldname)
				}))
		});
		return group_by_fields;
	}

	get_group_by_count(field, dropdown) {
		let current_filters = this.list_view.get_filters_for_args(), field_list;
		frappe.call('frappe.desk.listview.get_group_by_count',
			{doctype: this.doctype, current_filters: current_filters, field: field}).then((data) => {
			dropdown.find('.group-by-loading').hide();
			if(field === 'assigned_to') {
				let current_user  = data.message.find(user => user.name === frappe.session.user);
				if(current_user) {
					let current_user_count = current_user.count;
					this.get_html_for_group_by('Me', current_user_count).appendTo(dropdown);
				}
				field_list = data.message.filter(user => !['Guest', frappe.session.user, 'Administrator'].includes(user.name) && user.count!==0 );
			} else {
				field_list = data.message.filter(field => field.count!==0 );
			}
			field_list.forEach((f) => {
				if(f.name === null) {
					f.name = 'Not Specified';
				}
				this.get_html_for_group_by(f.name, f.count).appendTo(dropdown);
			});
			if(field_list.length) {
				this.sidebar.setup_dropdown_search(dropdown, '.group-by-value');
			} else {
				dropdown.find('.dropdown-search').hide();
			}
			this.setup_group_by_filter(dropdown, field);
		});
	}

	setup_group_by_filter(dropdown, field) {
		dropdown.find("li a").on("click", (e) => {
			let value = $(e.currentTarget).find($('.group-by-value')).text().trim();
			let fieldname = field === 'assigned_to'? '_assign': field;
			this.list_view.filter_area.remove(field);
			if(value === 'Not Specified') {
				this.list_view.filter_area.add(this.doctype, fieldname, "like", '');
			} else {
				if(value === 'Me') value = frappe.session.user;
				this.list_view.filter_area.add(this.doctype, fieldname, "like", `%${value}%`);
			}
		});
	}

	get_html_for_group_by(name, count) {
		if (count > 99) count='99+';
		let html = $('<li class="group-by-item"><a class="badge-hover" href="#" onclick="return false;"><span class="group-by-value">'
					+ name + '</span><span class="badge pull-right" style="position:relative">' + count + '</span></a></li>');
		return html;
	}

}