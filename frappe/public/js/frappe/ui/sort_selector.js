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
		this.make();
	},
	make: function() {
		this.prepare_args();
		this.wrapper = $(frappe.render_template('sort_selector', this.args)).appendTo(this.parent);
		this.bind_events();
	},
	bind_events: function() {
		var me = this;

		// order
		this.wrapper.find('.btn-order').on('click', function() {
			var btn = $(this);
			var order = $(this).attr('data-value')==='desc' ? 'asc' : 'desc';

			btn.attr('data-value', order);
			me.sort_order = order;
			btn.find('.octicon')
				.removeClass('octicon-arrow-' + (order==='asc' ? 'down' : 'up'))
				.addClass('octicon-arrow-' + (order==='desc' ? 'down' : 'up'));
			(me.onchange || me.change)(me.sort_by, me.sort_order);
		});

		// select field
		this.wrapper.find('.dropdown a.option').on('click', function() {
			me.sort_by = $(this).attr('data-value');
			me.wrapper.find('.dropdown .dropdown-text').html($(this).html());
			(me.onchange || me.change)(me.sort_by, me.sort_order);
		});

	},
	prepare_args: function() {
		var me = this;
		// make from doctype if not given
		if(!this.args && this.doctype) {
			this.setup_from_doctype();
		}

		// if label is missing, add from options
		if(this.args.sort_by && !this.args.sort_by_label) {
			this.args.options.every(function(o) {
				if(o.fieldname===me.args.sort_by) {
					me.args.sort_by_label = o.label;
				}
			});
		}
	},
	setup_from_doctype: function() {
		var args = {};
		var me = this;
		var meta = frappe.get_meta(this.doctype);
		if(meta.sort_field) {
			if(meta.sort_field.indexOf(',')!==-1) {
				parts = meta.sort_field.split(',')[0].split(' ');
				args.sort_by = parts[0];
				args.sort_order = parts[1];
			} else {
				args.sort_by = meta.sort_field;
				args.sort_order = meta.sort_order.toLowerCase();
			}
		} else {
			// default
			args.sort_by = 'modified';
			args.sort_order = 'desc';
		}
		args.sort_by_label = this.get_label(args.sort_by);

		// default options
		args._options = [
			{'fieldname': 'modified'},
		]

		// title field
		if(meta.title_field) {
			args._options.push({'fieldname': meta.title_field});
		}

		// bold or mandatory
		meta.fields.forEach(function(df) {
			if(df.mandatory || df.bold) {
				args._options.push({fieldname: df.fieldname, label: df.label});
			}
		});

		args._options.push({'fieldname': 'name'});
		args._options.push({'fieldname': 'creation'});
		args._options.push({'fieldname': 'idx'});

		// de-duplicate
		var added = [];
		args.options = [];
		args._options.forEach(function(o) {
			if(added.indexOf(o.fieldname)===-1) {
				args.options.push(o);
				added.push(o.fieldname);
			}
		});

		// add missing labels
		args.options.forEach(function(o) {
			if(!o.label) {
				o.label = me.get_label(o.fieldname);
			}
		});

		// set default
		this.args = args;
		this.sort_by = args.sort_by;
		this.sort_order = args.sort_order;
	},
	get_label: function(fieldname) {
		if(fieldname==='idx') {
			return __("Most Used");
		} else {
			return frappe.meta.get_label(this.doctype, fieldname);
		}
	}
})