wn.doclistviews['Report'] = wn.views.ListView.extend({
	init: function(d) {
		this._super(d)
		this.fields = this.fields.concat([
			"`tabReport`.ref_doctype",
		]);
	},
	
	prepare_data: function(data) {
		this._super(data);
		data.report = repl("<a href=\"#!Report2/%(ref_doctype)s/%(name)s\">\
								%(name)s</a>", data);
	},
	
	columns: [
		{width: '3%', content: 'check'},
		{width: '85%', content: 'report'},
		{width: '12%', content: 'modified',
			css: {'text-align': 'right', 'color':'#777'}}
	]
});