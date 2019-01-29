frappe.ui.Filter = class {
	constructor(opts) {
		$.extend(this, opts);
		if (this.value === null || this.value === undefined) {
			this.value = '';
		}

		this.utils = frappe.ui.filter_utils;
		this.conditions = [
			["=", __("Equals")],
			["!=", __("Not Equals")],
			["like", __("Like")],
			["not like", __("Not Like")],
			["in", __("In")],
			["not in", __("Not In")],
			["is", __("Is")],
			[">", ">"],
			["<", "<"],
			[">=", ">="],
			["<=", "<="],
			["Between", __("Between")],
			["descendants of", __("Descendants Of")],
			["not descendants of", __("Not Descendants Of")],
			["ancestors of", __("Ancestors Of")],
			["not ancestors of", __("Not Ancestors Of")],
			["Previous", __("Previous")],
			["Next", __("Next")]
		];
		this.invalid_condition_map = {
			Date: ['like', 'not like'],
			Datetime: ['like', 'not like'],
			Data: ['Between', 'Previous', 'Next'],
			Select: ['like', 'not like'],
			Link: ["Between", 'Previous', 'Next'],
			Currency: ["Between", 'Previous', 'Next'],
			Color: ["Between", 'Previous', 'Next']
		};
		this.make();
		this.make_select();
		this.set_events();
		this.setup();
	}

	make() {
		this.filter_edit_area = $(frappe.render_template("edit_filter", {
			conditions: this.conditions
		}))
			.appendTo(this.parent.find('.filter-edit-area'));
	}

	make_select() {
		this.fieldselect = new frappe.ui.FieldSelect({
			parent: this.filter_edit_area.find('.fieldname-select-area'),
			doctype: this.parent_doctype,
			filter_fields: this.filter_fields,
			select: (doctype, fieldname) => {
				this.set_field(doctype, fieldname);
			}
		});

		if(this.fieldname) {
			this.fieldselect.set_value(this.doctype, this.fieldname);
		}
	}

	set_events() {
		this.filter_edit_area.find("a.remove-filter").on("click", () => {
			this.remove();
		});

		this.filter_edit_area.find(".set-filter-and-run").on("click", () => {
			this.filter_edit_area.removeClass("new-filter");
			this.on_change();
			this.update_filter_tag();
		});

		this.filter_edit_area.find('.condition').change(() => {
			if(!this.field) return;

			let condition = this.get_condition();
			let fieldtype = null;

			if(["in", "like", "not in", "not like"].includes(condition)) {
				fieldtype = 'Data';
				this.add_condition_help(condition);
			}

			if (['Select', 'MultiSelect'].includes(this.field.df.fieldtype) && ["in", "not in"].includes(condition)) {
				fieldtype = 'MultiSelect';
			}

			this.set_field(this.field.df.parent, this.field.df.fieldname, fieldtype, condition);
		});
	}

	setup() {
		const fieldname = this.fieldname || 'name';
		// set the field
		return this.set_values(this.doctype, fieldname, this.condition, this.value);
	}

	setup_state(is_new) {
		let promise = Promise.resolve();
		if (is_new) {
			this.filter_edit_area.addClass("new-filter");
		} else {
			promise = this.update_filter_tag();
		}

		if(this.hidden) {
			promise.then(() => this.$filter_tag.hide());
		}
	}

	freeze() {
		this.update_filter_tag();
	}

	update_filter_tag() {
		return this._filter_value_set.then(() => {
			!this.$filter_tag ? this.make_tag() : this.set_filter_button_text();
			this.filter_edit_area.hide();
		});
	}

	remove() {
		this.filter_edit_area.remove();
		this.$filter_tag && this.$filter_tag.remove();
		this.field = null;
		this.on_change(true);
	}

	set_values(doctype, fieldname, condition, value) {
		// presents given (could be via tags!)
		if (this.set_field(doctype, fieldname) === false) {
			return
		}

		if(this.field.df.original_type==='Check') {
			value = (value==1) ? 'Yes' : 'No';
		}
		if(condition) this.set_condition(condition, true);

		// set value can be asynchronous, so update_filter_tag should happen after field is set
		this._filter_value_set = Promise.resolve();

		if (['in', 'not in'].includes(condition) && Array.isArray(value)) {
			value = value.join(',');
		}

		if (Array.isArray(value)) {
			this._filter_value_set = this.field.set_value(value);
		} else if (value !== undefined || value !== null) {
			this._filter_value_set = this.field.set_value((value + '').trim());
		}
		return this._filter_value_set;
	}

	set_field(doctype, fieldname, fieldtype, condition) {
		// set in fieldname (again)
		let cur = {};
		if(this.field) for(let k in this.field.df) cur[k] = this.field.df[k];

		let original_docfield = (this.fieldselect.fields_by_name[doctype] || {})[fieldname];
		if(!original_docfield) {
			console.warn(`Field ${fieldname} is not selectable.`);
			this.remove();
			return false;
		}

		let df = copy_dict(original_docfield);

		// filter field shouldn't be read only or hidden
		df.read_only = 0;
		df.hidden = 0;
		df.is_filter = true;

		let c = condition ? condition : this.utils.get_default_condition(df);
		this.set_condition(c);

		this.utils.set_fieldtype(df, fieldtype, this.get_condition());

		// called when condition is changed,
		// don't change if all is well
		if(this.field && cur.fieldname == fieldname && df.fieldtype == cur.fieldtype &&
			df.parent == cur.parent) {
			return;
		}

		// clear field area and make field
		this.fieldselect.selected_doctype = doctype;
		this.fieldselect.selected_fieldname = fieldname;

		if(["Previous", "Next"].includes(condition) && ['Date', 'Datetime', 'DateRange', 'Select'].includes(this.field.df.fieldtype)) {
			df.fieldtype = 'Select';
			df.options = [
				{
					label: __('1 week'),
					value: '1 week'
				},
				{
					label: __('1 month'),
					value: '1 month'
				},
				{
					label: __('3 months'),
					value: '3 months'
				},
				{
					label: __('6 months'),
					value: '6 months'
				},
				{
					label: __('1 year'),
					value: '1 year'
				}
			];
		}

		this.make_field(df, cur.fieldtype);
	}

	make_field(df, old_fieldtype) {
		let old_text = this.field ? this.field.get_value() : null;
		this.hide_invalid_conditions(df.fieldtype, df.original_type);
		this.hide_nested_set_conditions(df);
		let field_area = this.filter_edit_area.find('.filter-field').empty().get(0);
		let f = frappe.ui.form.make_control({
			df: df,
			parent: field_area,
			only_input: true,
		});
		f.refresh();

		this.field = f;
		if(old_text && f.fieldtype===old_fieldtype) {
			this.field.set_value(old_text);
		}

		// run on enter
		$(this.field.wrapper).find(':input').keydown(e => {
			if(e.which==13 && this.field.df.fieldtype !== 'MultiSelect') {
				this.on_change();
			}
		});
	}

	get_value() {
		return [
			this.fieldselect.selected_doctype,
			this.field.df.fieldname,
			this.get_condition(),
			this.get_selected_value(),
			this.hidden
		];
	}
	get_selected_value() {
		return this.utils.get_selected_value(this.field, this.get_condition());
	}

	get_condition() {
		return this.filter_edit_area.find('.condition').val();
	}

	set_condition(condition, trigger_change=false) {
		let $condition_field = this.filter_edit_area.find('.condition');
		$condition_field.val(condition);
		if(trigger_change) $condition_field.change();

	}

	make_tag() {
		this.$filter_tag = this.get_filter_tag_element()
			.insertAfter(this.parent.find(".active-tag-filters .add-filter"));
		this.set_filter_button_text();
		this.bind_tag();
	}

	bind_tag() {
		this.$filter_tag.find(".remove-filter").on("click", this.remove.bind(this));

		let filter_button = this.$filter_tag.find(".toggle-filter");
		filter_button.on("click", () => {
			filter_button.closest('.tag-filters-area').find('.filter-edit-area').show();
			this.filter_edit_area.toggle();
		});
	}

	set_filter_button_text() {
		this.$filter_tag.find(".toggle-filter").html(this.get_filter_button_text());
	}

	get_filter_button_text() {
		let value = this.utils.get_formatted_value(this.field, this.get_selected_value());
		return `${__(this.field.df.label)} ${__(this.get_condition())} ${__(value)}`;
	}

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
	}

	add_condition_help(condition) {
		let $desc = this.field.desc_area;
		if(!$desc) {
			$desc = $('<div class="text-muted small">').appendTo(this.field.wrapper);
		}
		// set description
		$desc.html((in_list(["in", "not in"], condition)==="in"
			? __("values separated by commas")
			: __("use % as wildcard"))+'</div>');
	}

	hide_invalid_conditions(fieldtype, original_type) {
		let invalid_conditions = this.invalid_condition_map[fieldtype] ||
			this.invalid_condition_map[original_type] || [];

		for (let condition of this.conditions) {
			this.filter_edit_area.find(`.condition option[value="${condition[0]}"]`).toggle(
				!invalid_conditions.includes(condition[0])
			);
		}
	}

	hide_nested_set_conditions(df) {
		if ( !( df.fieldtype == "Link" && frappe.boot.nested_set_doctypes.includes(df.options))) {
			this.filter_edit_area.find(`.condition option[value="descendants of"]`).hide();
			this.filter_edit_area.find(`.condition option[value="not descendants of"]`).hide();
			this.filter_edit_area.find(`.condition option[value="ancestors of"]`).hide();
			this.filter_edit_area.find(`.condition option[value="not ancestors of"]`).hide();
		}else {
			this.filter_edit_area.find(`.condition option[value="descendants of"]`).show();
			this.filter_edit_area.find(`.condition option[value="not descendants of"]`).show();
			this.filter_edit_area.find(`.condition option[value="ancestors of"]`).show();
			this.filter_edit_area.find(`.condition option[value="not ancestors of"]`).show();
		}
	}
};

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
		let val = field.get_value();

		if(typeof val==='string') {
			val = strip(val);
		}

		if(field.df.original_type == 'Check') {
			val = (val=='Yes' ? 1 :0);
		}

		if(condition.indexOf('like', 'not like')!==-1) {
			// automatically append wildcards
			if(val && !(val.startsWith('%') || val.endsWith('%'))) {
				val = '%' + val + '%';
			}
		} else if(in_list(["in", "not in"], condition)) {
			if(val) {
				val = val.split(',').map(v => strip(v));
			}
		} if(val === '%') {
			val = "";
		}

		return val;
	},

	get_default_condition(df) {
		if (df.fieldtype == 'Data') {
			return 'like';
		} else if (df.fieldtype == 'Date' || df.fieldtype == 'Datetime'){
			return 'Between';
		} else {
			return '=';
		}
	},

	set_fieldtype(df, fieldtype, condition) {
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
			];
		} else if(df.fieldtype=='Check') {
			df.fieldtype='Select';
			df.options='No\nYes';
		} else if(['Text','Small Text','Text Editor','Code','Tag','Comments',
			'Dynamic Link','Read Only','Assign'].indexOf(df.fieldtype)!=-1) {
			df.fieldtype = 'Data';
		} else if(df.fieldtype=='Link' && ['=', '!=', 'descendants of', 'ancestors of', 'not descendants of', 'not ancestors of'].indexOf(condition)==-1) {
			df.fieldtype = 'Data';
		}
		if(df.fieldtype==="Data" && (df.options || "").toLowerCase()==="email") {
			df.options = null;
		}
		if(condition == "Between" && (df.fieldtype == 'Date' || df.fieldtype == 'Datetime')){
			df.fieldtype = 'DateRange';
		}
		if (condition === 'is') {
			df.fieldtype = 'Select';
			df.options = [
				{ label: __('Set'), value: 'set' },
				{ label: __('Not Set'), value: 'not set' },
			];
		}
	}
};
