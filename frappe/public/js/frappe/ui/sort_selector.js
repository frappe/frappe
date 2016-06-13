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
		if(!this.args) {
			this.args = {};
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

		if(!this.args.sort_by) {
			if(meta.sort_field) {
				if(meta.sort_field.indexOf(',')!==-1) {
					parts = meta.sort_field.split(',')[0].split(' ');
					this.args.sort_by = parts[0];
					this.args.sort_order = parts[1];
				} else {
					this.args.sort_by = meta.sort_field;
					this.args.sort_order = meta.sort_order.toLowerCase();
				}
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
			]

			// title field
			if(meta.title_field) {
				_options.push({'fieldname': meta.title_field});
			}

			// bold or mandatory
			meta.fields.forEach(function(df) {
				if(df.mandatory || df.bold) {
					_options.push({fieldname: df.fieldname, label: df.label});
				}
			});

			_options.push({'fieldname': 'name'});
			_options.push({'fieldname': 'creation'});
			_options.push({'fieldname': 'idx'});

			// de-duplicate
			var added = [];
			this.args.options = [];
			_options.forEach(function(o) {
				if(added.indexOf(o.fieldname)===-1) {
					me.args.options.push(o);
					added.push(o.fieldname);
				}
			});

			// add missing labels
			this.args.options.forEach(function(o) {
				if(!o.label) {
					o.label = me.get_label(o.fieldname);
				}
			});
		}

		// set default
		this.sort_by = this.args.sort_by;
		this.sort_order = this.args.sort_order;
	},
	get_label: function(fieldname) {
		if(fieldname==='idx') {
			return __("Most Used");
		} else {
			return this.labels[fieldname]
				|| frappe.meta.get_label(this.doctype, fieldname);
		}
	}
})