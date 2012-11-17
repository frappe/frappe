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
		this.list = new wn.ui.Listing({
			parent: $(this.dialog.body),
			appframe: this.dialog.appframe,
			new_doctype: this.doctype,
			doctype: this.doctype,
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
						fields: [ '`tab' + me.doctype + '`.name'],
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
				if(this.data.length==1) {
					$ln.click();
				}
			}
		});
		this.list.filter_list.add_filter(this.doctype, 'name', 'like');
		this.list.run();
	}
})