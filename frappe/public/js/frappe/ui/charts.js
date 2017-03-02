frappe.provide("frappe.ui");

frappe.ui.Chart = Class.extend({
	init: function(opts) {
		this.opts = {};
		$.extend(this.opts, opts);
		this.show_chart(false);

		this.opts.bind_to = frappe.dom.set_unique_id(this.opts.wrapper);

		if(this.opts.data && ((this.opts.data.columns && this.opts.data.columns.length >= 1)
			|| (this.opts.data.rows && this.opts.data.rows.length >= 1))) {
				this.chart = this.render_chart();
				this.show_chart(true);
		}

		return this.chart;
	},

	render_chart: function() {
		var chart_dict = {
			bindto: '#' + this.opts.bind_to,
		    data: {},
			axis: {
		        x: {
		            type: this.opts.x_type || 'category' // this needed to load string x value
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

		if(this.opts.x_type==='timeseries') {
			if(!chart_dict.axis.x.tick) {
				chart_dict.axis.x.tick = {}
			}
			chart_dict.axis.x.tick.culling = {max: 15};
			chart_dict.axis.x.tick.format = frappe.boot.sysdefaults.date_format
				.replace('yyyy', '%Y').replace('mm', '%m').replace('dd', '%d');
		};

		// set color
		if(!chart_dict.data.colors) {
			colors = ['#4E50A6', '#7679FB', '#A3A5FC', '#925191', '#5D3EA4', '#8D5FFA',
				'#5E3AA8', '#7B933D', '#4F8EA8'];
			chart_dict.data.colors = {};
			chart_dict.data.columns.forEach(function(d, i) {
				if(d[0]!=='x') {
					chart_dict.data.colors[d[0]] = colors[i-1];
				}
			});
		}

		return c3.generate(chart_dict);
	},

	show_chart: function(show) {
		this.opts.wrapper.toggle(show);
	},

	set_chart_size: function(width, height) {
		this.chart.resize({
			width: width,
			height: height
		});
	}
});
