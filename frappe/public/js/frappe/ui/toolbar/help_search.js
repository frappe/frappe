frappe.provide('frappe.search');

frappe.search.Help = frappe.search.BaseSearch.extend({
	get_results: function(keywords) {
		var results = [];
		var me = this;
		frappe.call({
			method: "frappe.utils.help.get_help",
			args: {
				text: keywords
			},
			callback: function(r) {
				if(r.message) {
					r.message.forEach(function(e) {
						var title = e[0];
						var intro = e[1];
						var fpath = '#" data-path="' + e[2];
						results.push(me.render_result(keywords, [fpath, title, intro]));
					});
				}
				me.show_results(results, keywords);
			}
		});
	},

	show_results: function(results, keywords) {
		this._super();
		this.show_help_article();
	},

	show_help_article: function() {
			//edit links
			href = e.target.href;
			if(href.indexOf('blob') > 0) {
				window.open(href, '_blank');
			}

			var converter = new Showdown.converter();
			var path = $(this).attr("data-path");
			if(path) {
				e.preventDefault();
				frappe.call({
					method: "frappe.utils.help.get_help_content",
					args: {
						path: path
					},
					callback: function (r) {
						if(r.message && r.message.title) {
							$result_modal.find('.modal-title').html("<span>"
								+ r.message.title + "</span>");
							$result_modal.find('.modal-body').html(r.message.content);
							$result_modal.modal('show');
						}
					}
				});
			}
		}

});