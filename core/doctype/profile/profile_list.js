// render
wn.doclistviews['Profile'] = wn.views.ListView.extend({
	init: function(d) {
		this._super(d)
		this.fields = this.fields.concat([
			"`tabProfile`.first_name",
			"`tabProfile`.middle_name",
			"`tabProfile`.last_name",
			"`tabProfile`.enabled",
		]);
		this.stats = this.stats.concat(['enabled']);
		
		// hide Administrator and Guest user
		if(user!="Administrator") {
			this.default_filters = [
				["Profile", "name", "!=", "Administrator"], 
				["Profile", "name", "!=", "Guest"]
			];
		}
	},

	prepare_data: function(data) {
		this._super(data);
		data.fullname = $.map([data.first_name, data.middle_name, data.last_name],
			function(val) { return val; }).join(" ");
	},
	
	columns: [
		{width: '3%', content: 'check'},
		{width: '5%', content: 'avatar'},
		{width: '3%', content: function(parent, data) {
			var enabled = cint(data.enabled);
			$(parent).html(repl('<span class="docstatus"><i class="%(icon)s" \
				title="%(title)s"></i></span>', {
					icon: enabled ? "icon-pencil": "icon-exclamation-sign",
					title: enabled ? "Enabled": "Disabled",
				}));
		}},
		{width: '40%', content: 'name'},
		{width: '35%', content: 'fullname+tags'},
		{width: '17%', content:'modified',
			css: {'text-align': 'right', 'color': '#777'}},
			
	]
});