// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.form.MultiSelect = Class.extend({
	init: function(opts) {
		/* help: Options: doctype, get_query, target */
		$.extend(this, opts);

		var me = this;
		if(this.doctype!="[Select]") {
			frappe.model.with_doctype(this.doctype, function(r) {
				me.make();
			});
		} else {
			this.make();
		}
	},
	make: function() {
		me = this;
		this.dialog = new frappe.ui.Dialog({
			title: __("Select {0}", [(this.doctype=='[Select]') ? __("value") : __(this.doctype)+"s"]),
			fields: [
				// customer field
				{
					fieldtype: "Link",
					fieldname: 'Customer',
					doctype: 'Customer',
					options: 'Customer',
					get_query: me.get_query
				},
				{
					fieldtype: "Link",
					fieldname: me.doctype,
					doctype: me.doctype,
					options: me.doctype,
					get_query: me.get_query
				},
				{
					fieldtype: "HTML", fieldname: "results_area"
				},
				{
					fieldtype: "Button", fieldname: "make_new", label: __("Make a new " + me.doctype)
				}
			],
			primary_action_label: __("Get Items"),
			primary_action: function() {
				console.log("here pri action");
				me.action(me.selections);
			}
		});

		this.parent = this.dialog.body;
		$wrapper =
		this.$wrapper = this.dialog.fields_dict.results_area.$wrapper.append(`<div class="results"
			style="border: 1px solid #d1d8dd; border-radius: 3px; height: 400px; overflow: auto;"></div>`);
		this.$customer_field = this.dialog.fields_dict['Customer'];
		this.link_field = this.dialog.fields_dict[this.doctype];
		this.link_field.$wrapper.addClass('hide');
		this.$results = this.$wrapper.find('.results');
		this.$make_new_btn = this.dialog.fields_dict.make_new.$wrapper;
		this.$placeholder = $(`<div class="multiselect-empty-state"> <span class="text-center" style="margin-top: -40px;">
			<i class="fa fa-2x fa-tags text-extra-muted"></i> <p class="text-extra-muted">No ${this.doctype} found</p>
			<button class="btn btn-default btn-xs text-muted" data-fieldtype="Button" data-fieldname="make_new"
			placeholder="" value="">Make a new ${this.doctype}</button></span> </div>`);
		this.selections = [];

		this.get_results();
		this.dialog.show();
	},

	make_results: function(results) {
		var me = this;
		if(results.length === 0) {
			this.$make_new_btn.addClass('hide');
			this.$results.append(me.$placeholder);
			return;
		}
		this.$results.append(`
			<div class="list-item list-item--head">
				<div class="list-item__content ellipsis" style="flex: 0 0 10px;">
					<input type="checkbox"/>
				</div>
				<div class="list-item__content">
					${__(me.doctype)}
				</div>
				<div class="list-item__content" style="flex: 2 0 0px;">
					${__('Description')}
				</div>
			</div>
		`);

		var result_rows = results.map(
			result => make_result_row(result)
		);
		this.$results.append(result_rows);

		function make_result_row(result) {
			var template = `
				<div class="list-item-container" data-filename="${result.value}">
					<div class="list-item">
						<div class="list-item__content ellipsis" style="flex: 0 0 10px;">
							<input type="checkbox"/>
						</div>
						<div class="list-item__content ellipsis">
							${result.value}
						</div>
						<div class="list-item__content ellipsis" style="flex: 2 0 0px;">
							${result.description}
						</div>
					</div>
				</div>`;

			return $(template);
		}

		// events
		this.$results.on('change', '.list-item-container :checkbox', function (e) {
			var $item = $(this).closest('.list-item-container');
			var filename = $item.attr('data-filename');
			var $target = $(e.target);

			var checked = $target.is(':checked');
			if (checked){
				me.selections.push(filename);
			} else {
				var index = me.selections.indexOf(filename);
				if (index > -1) me.selections.splice(index, 1);
			}
		});
		this.$results.on('click', '.list-item-container', function (e) {
			if (!$(e.target).is(':checkbox')) {
				$(this).find(':checkbox').trigger('click');
			}
		});
		this.$results.on('click', '.list-item--head :checkbox', function (e) {
			if ($(e.target).is(':checked')) {
				me.$results.find('.list-item-container :checkbox:not(:checked)').trigger('click');
			} else {
				me.$results.find('.list-item-container :checkbox(:checked)').trigger('click');
			}
		});
		$(this.parent).on('click', '.btn[data-fieldname="make_new"]', function(e) {
			me.link_field.new_doc();
		});
	},

	get_results: function() {
		var me = this;
		var args = {
			txt: '',
			doctype: me.doctype
		}
		this.link_field.set_custom_query(args);
		frappe.call({
			type: "GET",
			method:'frappe.desk.search.search_link',
			no_spinner: true,
			args: args,
			callback: function(r) {
				me.make_results(r.results);
			}
		});
	},

});