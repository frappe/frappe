wn.doclistviews['Search Criteria'] = wn.views.ListView.extend({
	init: function(d) {
		this._super(d)
		this.fields = this.fields.concat([
			"`tabSearch Criteria`.criteria_name",
			"`tabSearch Criteria`.doc_type",
		]);
	},
	
	prepare_data: function(data) {
		this._super(data);
		
		if(wn.boot.profile.all_read.indexOf(data.doc_type)==-1) {
			data.report = repl("<span style=\"color:#999\">%(criteria_name)s</span>", data);
			data.edit = repl("<span style=\"color:#999\">Edit</span>", data);
		} else {
			data.report = repl("<a href=\"#!Report/%(doc_type)s/%(criteria_name)s\">\
									%(criteria_name)s</a>", data);
			data.edit = repl("<a href=\"#!Form/Search Criteria/%(name)s\">Edit</a>", data);
		}
	},
	
	columns: [
		{width: '3%', content: 'check'},
		{width: '65%', content: 'report'},
		{width: '20%', content: 'edit'},
		{width: '12%', content: 'modified',
			css: {'text-align': 'right', 'color':'#777'}}
	]
});