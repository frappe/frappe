// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd.
// MIT License. See license.txt

// search widget

// options: doctype, callback, query (if applicable)
wn.ui.Search = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		var me = this;
		wn.model.with_doctype(this.doctype, function(r) {
			me.make();
			me.dialog.show();
			me.list.$w.find('.list-filters input[type="text"]').focus();
		});
	},
	make: function() {
		var me = this;
		this.dialog = new wn.ui.Dialog({
			title: this.doctype + ' Search',
			width: 500
		});
		var parent = $('<div class="row"><div class="col-md-12"></div></div>')
			.appendTo(this.dialog.body)
			.find(".col-md-12")
		this.list = new wn.ui.Listing({
			parent: parent,
			appframe: this.dialog.appframe,
			new_doctype: this.doctype,
			doctype: this.doctype,
			type: "GET",
			method: 'webnotes.widgets.reportview.get',
			show_filters: true,
			style: 'compact',
			get_args: function() {
				if(me.query) {
					me.page_length = 50; // there has to be a better way :(
					return {
						query: me.query
					}
				} else {
					return {
						doctype: me.doctype,
						fields: me.get_fields(),
						filters: me.list.filter_list.get_filters(),
						docstatus: ['0','1']
					}
				}
			},
			render_row: function(parent, data) {
				$ln = $('<a href="#" data-name="'+data.name+'">'
					+ data.name +'</a>')
					.appendTo(parent)
					.click(function() {
						var val = $(this).attr('data-name');
						me.dialog.hide(); 
						if(me.callback)
							me.callback(val);
						else 
							wn.set_route('Form', me.doctype, val);
						return false;
					});
					
				// other values
				$.each(data, function(key, value) {
					if(key!=="name") {
						$("<span>")
							.html(value)
							.css({"margin-left": "15px", "display": "block"})
							.appendTo(parent);
					}
				})
				if(this.data.length==1) {
					$ln.click();
				}
			}
		});
		this.list.filter_list.add_filter(this.doctype, 'name', 'like');
		this.list.run();
	},
	get_fields: function() {
		var me = this;
		var fields = [ '`tab' + me.doctype + '`.name'];
		$.each((wn.model.get("DocType", me.doctype)[0].search_fields || "").split(","), 
			function(i, field) {
				if(strip(field)) {
					fields.push('`tab' + me.doctype + '`.' + strip(field));
				}
			}
		)
		return fields;
	}
})