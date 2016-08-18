frappe.provide("frappe.ui");

frappe.ui.Chart = Class.extend({
	init: function(opts) {
		this.opts = {};
		$.extend(this.opts, opts);
		this.show_chart(false);

		if(this.opts.data && ((this.opts.data.columns && this.opts.data.columns.length >= 1)
			|| (this.opts.data.rows && this.opts.data.rows.length >= 1))) {
				this.chart = this.render_chart();
				this.show_chart(true);
		}

		return this.chart;
	},

	render_chart: function() {
		var chart_dict = {
			bindto: this.opts.bind_to,
		    data: {},
			axis: {
		        x: {
		            type: 'category' // this needed to load string x value
		        },
				y: {
					padding: { bottom: 10 }
				}
			},
			padding: {
				left: 60,
				top: 30,
				right: 30,
				bottom: 10
			},
			pie: {
				expand : false
			},
			bar: {
				"width": 10
			}
		};

		$.extend(chart_dict, this.opts);

		chart_dict["data"]["type"] = this.opts.chart_type || "line";

		return c3.generate(chart_dict);
	},

	show_chart: function(show) {
		this.opts.wrapper.find(this.opts.bind_to).toggle(show);
	},

	set_chart_size: function(width, height) {
		this.chart.resize({
			width: width,
			height: height
		});
	}
});
