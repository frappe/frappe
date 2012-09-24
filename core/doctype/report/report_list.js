wn.doclistviews['Report'] = wn.views.ListView.extend({
	init: function(d) {
		this._super(d)
		this.fields = this.fields.concat([
			"`tabReport`.ref_doctype",
		]);
	},
	
	prepare_data: function(data) {
		this._super(data);
		
		if(wn.boot.profile.all_read.indexOf(data.ref_doctype)==-1) {
			data.report = repl("<span style=\"color:#999\">%(name)s</span>", data);
		} else {
			data.report = repl("<a href=\"#!Report2/%(ref_doctype)s/%(name)s\">\
									%(name)s</a>", data);
		}
},
	
	columns: [
		{width: '3%', content: 'check'},
		{width: '82%', content: 'report'},
		{width: '15%', content: 'modified',
			css: {'text-align': 'right', 'color':'#777'}}
	]
});