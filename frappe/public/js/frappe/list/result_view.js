frappe.provide("frappe.views");

// opts = { doctype, values }
// frappe.views.render_result_view = function (opts) {

// }

frappe.views.ResultView = Class.extend({
	init: function(opts) {
		$.extend(this, opts);

		this.meta = frappe.get_meta(this.doctype);
		this.image_field = this.meta.image_field || 'image';
		this.settings = frappe.listview_settings[this.doctype] || {};
		if(this.meta.__listview_template) {
			this.template_name = this.doctype + "_listview";
			frappe.templates[this.template_name] = this.meta.__listview_template;
		}
		this.set_fields();
		this.set_columns();
		this.id_list = [];
		if(this.settings.group_by)
			this.group_by = this.settings.group_by;

		var me = this;
		this.doclistview.onreset = function() {
			me.id_list = [];
		}
		this.order_by = this.settings.order_by;
		this.group_by = this.settings.group_by;
	},
	set_fields: function() {
		var me = this;
		var tabDoctype = "`tab" + this.doctype + "`.";
		this.fields = [];
		this.stats = ['_user_tags'];

		var add_field = function(fieldname) {
			if(!fieldname.includes("`tab")) {
				fieldname = tabDoctype + "`" + fieldname + "`";
			}
			if(!me.fields.includes(field))
				me.fields.push(field);
		}

		['name', 'owner', 'docstatus', '_user_tags', '_comments',
		'modified', 'modified_by', '_assign', '_liked_by', '_seen'
		].map(add_field);

		// add title field
		if(this.meta.title_field) {
			this.title_field = this.meta.title_field;
			add_field(this.meta.title_field);
		}

		// enabled / disabled
		if(frappe.meta.has_field(this.doctype, 'enabled')) { add_field('enabled'); };
		if(frappe.meta.has_field(this.doctype, 'disabled')) { add_field('disabled'); };

		// add workflow field (as priority)
		this.workflow_state_fieldname = frappe.workflow.get_state_fieldname(this.doctype);
		if(this.workflow_state_fieldname) {
			if (!frappe.workflow.workflows[this.doctype]["override_status"]) {
				add_field(this.workflow_state_fieldname);
			}
			this.stats.push(this.workflow_state_fieldname);
		}

		this.meta.fields.forEach(function(df, i) {
			if(df.in_list_view && frappe.perm.has_perm(me.doctype, df.permlevel, "read")) {
				if(df.fieldtype=="Image" && df.options) {
					add_field(df.options);
				} else {
					add_field(df.fieldname);
				}
				// currency field for symbol (multi-currency)
				if(df.fieldtype=="Currency" && df.options) {
					if(df.options.includes(":")) {
						add_field(df.options.split(":")[1]);
					} else {
						add_field(df.options);
					};
				}
			}
		});

		// additional fields
		if(this.settings.add_fields) {
			this.settings.add_fields.forEach(add_field);
		}

		if(me.meta.__kanban_column_fields)
			me.fields = me.fields.concat(me.meta.__kanban_column_fields);
	},
})