# Making Charts using c3.js

Frappé bundles the c3.js libary to make charts inside the app and provides a wrapper class so that you can start using charts out of the box. To use chart, you need the x and y data, make a wrapper block and then just make the chart object.

### Time Series Example

		page.chart = new frappe.ui.Chart({
			// attach the chart here
			wrapper: $('<div>').appendTo(page.body),

			// pass the data, like
			// ['x', '2016-01-01', '2016-01-02']
			// ['Value', 20, 30]
			data: {
				x: 'x',
				xFormat: '%Y-%m-%d',
				columns: [data[0], data[1]],
			},
			legend: {
				show: false
			},
			axis: {
				x: {
					type: 'timeseries',
				},
				y: {
					min: 0,
					padding: {bottom: 10}
				}
			}
		});

### Help

For more options, see the [c3js.org](http://c3js.org/examples.html) docs