// Copyright (c) 2017, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

// opts:
//		frm
// 		wrapper
// 		get_items
//  	add_btn_label
// 		remove_btn_label
//		field_mapper: 
//			cdt
//			child_table_field
//			item_field 		
// 		attribute

frappe.CheckboxEditor = Class.extend({
	init: function(opts) {
		$.extend(this, opts);

		this.doctype = this.field_mapper.cdt;
		this.fieldname = this.field_mapper.child_table_field;
		this.item_fieldname = this.field_mapper.item_field;
		
		$(this.wrapper).html('<div class="help">' + __("Loading") + '...</div>');

		if(this.get_items) {
			this.get_items();
		}
	},
	render_items: function(callback) {
		let me = this;
		$(this.wrapper).empty();

		if(this.checkbox_selector) {
			let toolbar = $('<p><button class="btn btn-default btn-add btn-sm" style="margin-right: 5px;"></button>\
				<button class="btn btn-sm btn-default btn-remove"></button></p>').appendTo($(this.wrapper));

			toolbar.find(".btn-add")
				.html(__(this.add_btn_label))
				.on("click", function() {
				$(me.wrapper).find('input[type="checkbox"]').each(function(i, check) {
					if(!$(check).is(":checked")) {
						check.checked = true;
					}
				});
			});

			toolbar.find(".btn-remove")
				.html(__(this.remove_btn_label))
				.on("click", function() {
				$(me.wrapper).find('input[type="checkbox"]').each(function(i, check) {
					if($(check).is(":checked")) {
						check.checked = false;
					}
				});
			});
		}

		$.each(this.items, function(i, item) {
			$(me.wrapper).append(frappe.render(me.editor_template, {'item': item}));
		});

		$(this.wrapper).find('input[type="checkbox"]').change(function() {
			if(me.fieldname && me.doctype && me.item_field) {
				me.set_items_in_table();
				me.frm.dirty();
			}
		});

		callback && callback()
	},
	show: function() {
		let me = this;

		// uncheck all items
		$(this.wrapper).find('input[type="checkbox"]')
			.each(function(i, checkbox) { checkbox.checked = false; });

		// set user items as checked
		$.each((me.frm.doc[this.fieldname] || []), function(i, row) {
			let selector = repl('[%(attribute)s="%(value)s"] input[type="checkbox"]', {
				attribute: me.attribute,
				value: row[me.item_fieldname]
			});

			let checkbox = $(me.wrapper)
				.find(selector).get(0);
			if(checkbox) checkbox.checked = true;
		});
	},

	get_selected_unselected_items: function() {
		let checked_items = [];
		let unchecked_items = [];
		let selector = repl('[%(attribute)s]', { attribute: this.attribute });
		let me = this;

		$(this.wrapper).find(selector).each(function() {
			if($(this).find('input[type="checkbox"]:checked').length) {
				checked_items.push($(this).attr(me.attribute));
			} else {
				unchecked_items.push($(this).attr(me.attribute));
			}
		});

		return {
			checked_items: checked_items,
			unchecked_items: unchecked_items
		}
	},

	set_items_in_table: function() {
		let opts = this.get_selected_unselected_items();
		let existing_items_map = {};
		let existing_items_list = [];
		let me = this;

		$.each(me.frm.doc[this.fieldname] || [], function(i, row) {
			existing_items_map[row[me.item_fieldname]] = row.name;
			existing_items_list.push(row[me.item_fieldname]);
		});

		// remove unchecked items
		$.each(opts.unchecked_items, function(i, item) {
			if(existing_items_list.indexOf(item)!=-1) {
				frappe.model.clear_doc(me.doctype, existing_items_map[item]);
			}
		});

		// add new items that are checked
		$.each(opts.checked_items, function(i, item) {
			if(existing_items_list.indexOf(item)==-1) {
				let row = frappe.model.add_child(me.frm.doc, me.doctype, me.fieldname);
				row[me.item_fieldname] = item;
			}
		});

		refresh_field(this.fieldname);
	}
});