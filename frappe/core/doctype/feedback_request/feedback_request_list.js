frappe.listview_settings['Feedback Request'] = {
	colwidths: {
		subject: 2,
	},
	column_render: {
		rating: function(doc) {
			var html = ""
			for (var i = 0; i < 5; i++) {
				html += repl("<span class='indicator %(color)s'></span>", 
					{color: i<doc.rating? "blue": "darkgrey"})
			}

			return html;
		}
	}
}