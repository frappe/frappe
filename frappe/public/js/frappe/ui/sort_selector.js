frappe.ui.SortSelector = Class.extend({
	// parent:
	// change:
	// args:
	//		options: {fieldname:, label:}
	//		sort_by:
	//		sort_by_label:
	//		sort_order:
	//		doctype: (optional)
	init: function(opts) {
		$.extend(this, opts);
		this.labels = {};
		this.make();
	},
	make: function() {
		this.prepare_args();
		this.parent.find('.sort-selector').remove();
		this.wrapper = $(frappe.render_template('sort_selector', this.args)).appendTo(this.parent);
		this.bind_events();
	},
	bind_events: function() {
		var me = this;

		// order
		this.wrapper.find('.btn-order').on('click', function() {
			let btn = $(this);
			const order = $(this).attr('data-value') === 'desc' ? 'asc' : 'desc';
			const title = $(this).attr('data-value' )=== 'desc' ? __('ascending') : __('descending');

			btn.attr('data-value', order);
			btn.attr('title', title);
			me.sort_order = order;
			const icon_name = order === 'asc'? 'sort-ascending' : 'sort-descending';
			btn.find('.sort-order').html(frappe.utils.icon(icon_name, 'sm'));
			(me.onchange || me.change)(me.sort_by, me.sort_order);
		});

		// select field
		this.wrapper.find('.dropdown-menu a.option').on('click', function() {
			me.sort_by = $(this).attr('data-value');
			me.wrapper.find('.dropdown-text').html($(this).html());
			(me.onchange || me.change)(me.sort_by, me.sort_order);
		});

	},
	prepare_args: function() {
		var me = this;
		if(!this.args) {
			this.args = {};
		}

		// args as string
		if(this.args && typeof this.args === 'string') {
			var order_by = this.args;
			this.args = {}

			if (order_by.includes('`.`')) {
				// scrub table name (separated by dot), like `tabTime Log`.`modified` desc`
				order_by = order_by.split('.')[1];
			}

			var parts = order_by.split(' ');
			if (parts.length === 2) {
				var fieldname = strip(parts[0], '`');

				this.args.sort_by = fieldname;
				this.args.sort_order = parts[1];
			}
		}

		if(this.args.options) {
			this.args.options.forEach(function(o) {
				me.labels[o.fieldname] = o.label;
			});
		}

		this.setup_from_doctype();

		// if label is missing, add from options
		if(this.args.sort_by && !this.args.sort_by_label) {
			this.args.options.every(function(o) {
				if(o.fieldname===me.args.sort_by) {
					me.args.sort_by_label = o.label;
					return false;
				}
				return true;
			});
		}

	},
	setup_from_doctype: function() {
		var me = this;
		var meta = frappe.get_meta(this.doctype);
		if (!meta) return;

		var { meta_sort_field, meta_sort_order } = this.get_meta_sort_field();

		if(!this.args.sort_by) {
			if(meta_sort_field) {
				this.args.sort_by = meta_sort_field;
				this.args.sort_order = meta_sort_order;
			} else {
				// default
				this.args.sort_by = 'modified';
				this.args.sort_order = 'desc';
			}
		}

		if(!this.args.sort_by_label) {
			this.args.sort_by_label = this.get_label(this.args.sort_by);
		}

		if(!this.args.options) {
			// default options
			var _options = [
				{'fieldname': 'modified'},
				{'fieldname': 'name'},
				{'fieldname': 'creation'},
				{'fieldname': 'idx'},
			]

			// title field
			if (meta.title_field) {
				_options.splice(1, 0, {'fieldname': meta.title_field});
			}

			// sort field - set via DocType schema or Customize Form
			if (meta_sort_field) {
				_options.splice(1, 0, { 'fieldname': meta_sort_field });
			}

			// bold, mandatory and fields that are available in list view
			meta.fields.forEach(function(df) {
				if (
					(df.mandatory || df.bold || df.in_list_view)
					&& frappe.model.is_value_type(df.fieldtype)
					&& frappe.perm.has_perm(me.doctype, df.permlevel, "read")
				) {
					_options.push({fieldname: df.fieldname, label: df.label});
				}
			});

			// add missing labels
			_options.forEach(option => {
				if (!option.label) {
					option.label = me.get_label(option.fieldname);
				}
			});

			// de-duplicate
			this.args.options = _options.uniqBy(obj => {
				return obj.fieldname;
			});
		}

		// set default
		this.sort_by = this.args.sort_by;
		this.sort_order = this.args.sort_order;
	},
	get_meta_sort_field: function() {
		var meta = frappe.get_meta(this.doctype);

		if (!meta) {
			return {
				meta_sort_field: null,
				meta_sort_order: null
			}
		}

		if(meta.sort_field && meta.sort_field.includes(',')) {
			var parts = meta.sort_field.split(',')[0].split(' ');
			return {
				meta_sort_field: parts[0],
				meta_sort_order: parts[1]
			}
		} else {
			return {
				meta_sort_field: meta.sort_field || 'modified',
				meta_sort_order: meta.sort_order ? meta.sort_order.toLowerCase() : ''
			}
		}
	},
	get_label: function(fieldname) {
		if(fieldname==='idx') {
			return __("Most Used");
		} else {
			return this.labels[fieldname]
				|| frappe.meta.get_label(this.doctype, fieldname);
		}
	},
	get_sql_string: function() {
		// build string like `tabTask`.`subject` desc
		return '`tab' + this.doctype + '`.`' + this.sort_by + '` ' +  this.sort_order;
	}
})
