frappe.provide('frappe.search');

frappe.search.Global = frappe.search.BaseSearch.extend({
	get_results: function(keywords) {
		var results = [];
		var me = this;
		frappe.call({
			method: "frappe.utils.global_search.search",
			args: {
				text: keywords, start: 0, limit: 20
			},
			callback: function(r) {
				if(r.message) {
					r.message.forEach(function(e) {
						var fpath = '#Form/' + e.doctype + '/' + e.name;
						var title = e.doctype + ": " + e.name;
						results.push(me.render_result(keywords, [fpath, title, e.content]));
					});
				}
				me.show_results(results, keywords);
			}
		});
	}
});