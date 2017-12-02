frappe.ui.Filter = Class.extend({
	init(opts) {
		$.extend(this, opts);

		this.doctype = this.filter_group.doctype;
		this.utils = frappe.ui.filter_utils;
		this.make();
		this.make_select();
		this.set_events();
	},
	make() {
		this.filter_edit_area = $(frappe.render_template("edit_filter", {}))
			.appendTo(this.filter_group.wrapper.find('.filter-edit-area'));
	},
	make_select() {
		var me = this;
		this.fieldselect = new frappe.ui.FieldSelect({
			parent: this.filter_edit_area.find('.fieldname-select-area'),
			doctype: this.doctype,
			filter_fields: this.filter_fields,
			select(doctype, fieldname) {
				me.set_field(doctype, fieldname);
			}
		});
		if(this.fieldname) {
			this.fieldselect.set_value(this._doctype || this.doctype, this.fieldname);
		}
	},
	set_events() {
		var me = this;

		this.filter_edit_area.find("a.remove-filter").on("click", function() {
			me.remove();
		});

		this.filter_edit_area.find(".set-filter-and-run").on("click", function() {
			me.filter_edit_area.removeClass("new-filter");
			me.filter_group.base_list.run();
			me.apply();
		});

		// add help for "in" codition
		me.filter_edit_area.find('.condition').change(function() {
			if(!me.field) return;
			var condition = $(this).val();
			if(in_list(["in", "like", "not in", "not like"], condition)) {
				me.set_field(me.field.df.parent, me.field.df.fieldname, 'Data', condition);
				if(!me.field.desc_area) {
					me.field.desc_area = $('<div class="text-muted small">').appendTo(me.field.wrapper);
				}
				// set description
				me.field.desc_area.html((in_list(["in", "not in"], condition)==="in"
					? __("values separated by commas")
					: __("use % as wildcard"))+'</div>');
			} else {
				//if condition selected after refresh
				me.set_field(me.field.df.parent, me.field.df.fieldname, null, condition);
			}
		});

		// set the field
		if(me.fieldname) {
			// pre-sets given (could be via tags!)
			return this.set_values(me._doctype, me.fieldname, me.condition, me.value);
		} else {
			me.set_field(me.doctype, 'name');
		}
	},

	setup_state(is_new, hidden) {
		is_new ? this.filter_edit_area.addClass("new-filter") : this.freeze();
		if(hidden) this.$filter_tag.hide();
	},

	apply() {
		var f = this.get_value();
		this.filter_group.filters = this.filter_group.filters.filter(f => f !== this); // remove filter
		this.filter_group.push_new_filter(f);
		this.filter_edit_area.remove();
		this.filter_group.update_filters();
	},

	remove(dont_run) {
		this.filter_edit_area.remove();
		this.$filter_tag && this.$filter_tag.remove();
		this.field = null;
		this.filter_group.update_filters();

		if(!dont_run) {
			this.filter_group.base_list.refresh(true);
		}
	},

	set_values(doctype, fieldname, condition, value) {
		// presents given (could be via tags!)
		this.set_field(doctype, fieldname);

		// change 0,1 to Yes, No for check field type
		if(this.field.df.original_type==='Check') {
			if(value==0) value = 'No';
			else if(value==1) value = 'Yes';
		}

		if(condition) {
			this.filter_edit_area.find('.condition').val(condition).change();
		}
		if(value!=null) {
			return this.field.set_value(value);
		}
	},

	set_field(doctype, fieldname, fieldtype, condition) {
		var me = this;

		// set in fieldname (again)
		var cur = me.field ? {
			fieldname: me.field.df.fieldname,
			fieldtype: me.field.df.fieldtype,
			parent: me.field.df.parent,
		} : {};

		var original_docfield = me.fieldselect.fields_by_name[doctype][fieldname];
		if(!original_docfield) {
			frappe.msgprint(__("Field {0} is not selectable.", [fieldname]));
			return;
		}

		var df = copy_dict(me.fieldselect.fields_by_name[doctype][fieldname]);

		// filter field shouldn't be read only or hidden
		df.read_only = 0;
		df.hidden = 0;

		if(!condition) this.set_default_condition(df, fieldtype);
		this.set_fieldtype(df, fieldtype);

		// called when condition is changed,
		// don't change if all is well
		if(me.field && cur.fieldname == fieldname && df.fieldtype == cur.fieldtype &&
			df.parent == cur.parent) {
			return;
		}

		// clear field area and make field
		me.fieldselect.selected_doctype = doctype;
		me.fieldselect.selected_fieldname = fieldname;

		// save old text
		var old_text = null;
		if(me.field) {
			old_text = me.field.get_value();
		}

		var field_area = me.filter_edit_area.find('.filter-field').empty().get(0);
		var f = frappe.ui.form.make_control({
			df: df,
			parent: field_area,
			only_input: true,
		})
		f.refresh();

		me.field = f;
		if(old_text && me.field.df.fieldtype===cur.fieldtype) {
			me.field.set_value(old_text);
		}

		// run on enter
		$(me.field.wrapper).find(':input').keydown(function(ev) {
			if(ev.which==13) {
				me.filter_group.base_list.run();
			}
		})
	},

	set_fieldtype(df, fieldtype) {
		// reset
		if(df.original_type)
			df.fieldtype = df.original_type;
		else
			df.original_type = df.fieldtype;

		df.description = ''; df.reqd = 0;
		df.ignore_link_validation = true;

		// given
		if(fieldtype) {
			df.fieldtype = fieldtype;
			return;
		}

		// scrub
		if(df.fieldname=="docstatus") {
			df.fieldtype="Select",
			df.options=[
				{value:0, label:__("Draft")},
				{value:1, label:__("Submitted")},
				{value:2, label:__("Cancelled")}
			]
		} else if(df.fieldtype=='Check') {
			df.fieldtype='Select';
			df.options='No\nYes';
		} else if(['Text','Small Text','Text Editor','Code','Tag','Comments',
			'Dynamic Link','Read Only','Assign'].indexOf(df.fieldtype)!=-1) {
			df.fieldtype = 'Data';
		} else if(df.fieldtype=='Link' && ['=', '!='].indexOf(this.filter_edit_area.find('.condition').val())==-1) {
			df.fieldtype = 'Data';
		}
		if(df.fieldtype==="Data" && (df.options || "").toLowerCase()==="email") {
			df.options = null;
		}
		if(this.filter_edit_area.find('.condition').val()== "Between" && (df.fieldtype == 'Date' || df.fieldtype == 'Datetime')){
			df.fieldtype = 'DateRange';
		}
	},

	set_default_condition(df, fieldtype) {
		if(!fieldtype) {
			// set as "like" for data fields
			if (df.fieldtype == 'Data') {
				this.filter_edit_area.find('.condition').val('like');
			} else if (df.fieldtype == 'Date' || df.fieldtype == 'Datetime'){
				this.filter_edit_area.find('.condition').val('Between');
			}else{
				this.filter_edit_area.find('.condition').val('=');
			}
		}
	},

	get_value() {
		return [this.fieldselect.selected_doctype,
			this.field.df.fieldname, this.get_condition(), this.get_selected_value()];
	},

	get_selected_value() {
		return this.utils.get_selected_value(this.field, this.get_condition());
	},

	get_condition() {
		return this.filter_edit_area.find('.condition').val();
	},

	set_condition(condition) {
		this.filter_edit_area.find('.condition').val(condition);
	},

	freeze() {
		!this.$filter_tag ? this.make_tag() : this.set_filter_button_text();
		this.filter_edit_area.hide();
	},

	make_tag() {
		this.$filter_tag = this.get_filter_tag_element()
			.insertAfter(this.filter_group.wrapper.find(".active-tag-filters .add-filter"));
		this.set_filter_button_text();
		this.bind_tag();
	},

	bind_tag() {
		this.$filter_tag.find(".remove-filter").on("click", this.remove.bind(this));

		let filter_button = this.$filter_tag.find(".toggle-filter");
		filter_button.on("click", () => {
			filter_button.closest('.tag-filters-area').find('.filter-edit-area').show()
			this.filter_edit_area.toggle();
		})
	},

	set_filter_button_text() {
		this.$filter_tag.find(".toggle-filter").html(this.get_filter_button_text());
	},

	get_filter_button_text() {
		let value = this.utils.get_formatted_value(this.field, this.get_selected_value());
		return `${__(this.field.df.label)} ${__(this.get_condition())} ${__(value)}`;
	},

	get_filter_tag_element() {
		return $(`<div class="filter-tag btn-group">
			<button class="btn btn-default btn-xs toggle-filter"
				title="${ __("Edit Filter") }">
			</button>
			<button class="btn btn-default btn-xs remove-filter"
				title="${ __("Remove Filter") }">
				<i class="fa fa-remove text-muted"></i>
			</button>
		</div>`);
	},
});

frappe.ui.filter_utils = {
	get_formatted_value(field, value) {
		if(field.df.fieldname==="docstatus") {
			value = {0:"Draft", 1:"Submitted", 2:"Cancelled"}[value] || value;
		} else if(field.df.original_type==="Check") {
			value = {0:"No", 1:"Yes"}[cint(value)];
		}
		return frappe.format(value, field.df, {only_value: 1});
	},

	get_selected_value(field, condition) {
		var val = field.get_value();

		if(typeof val==='string') {
			val = strip(val);
		}

		if(field.df.original_type == 'Check') {
			val = (val=='Yes' ? 1 :0);
		}

		if(condition.indexOf('like', 'not like')!==-1) {
			// automatically append wildcards
			if(val) {
				if(val.slice(0,1) !== "%") {
					val = "%" + val;
				}
				if(val.slice(-1) !== "%") {
					val = val + "%";
				}
			}
		} else if(in_list(["in", "not in"], condition)) {
			if(val) {
				val = $.map(val.split(","), function(v) { return strip(v); });
			}
		} if(val === '%') {
			val = "";
		}

		return val;
	},
}
