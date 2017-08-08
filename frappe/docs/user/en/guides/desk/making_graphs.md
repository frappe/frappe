# Making Graphs

The Frappé UI **Graph** object enables you to render simple line, bar or percentage graphs for single or multiple discreet sets of data points. You can also set special checkpoint values and summary stats.

### Example: Line graph
Here's an example of a simple sales graph:

		// Data
		let months = ['August, 2016', 'September, 2016', 'October, 2016', 'November, 2016',
			'December, 2016', 'January, 2017', 'February, 2017', 'March, 2017', 'April, 2017',
			'May, 2017', 'June, 2017', 'July, 2017'];

		let values1 = [24100, 31000, 17000, 12000, 27000, 16000, 27400, 11000, 8500, 15000, 4000, 20130];
		let values2 = [17890, 10400, 12350, 20400, 17050, 23000, 7100, 13800, 16000, 20400, 11000, 13000];
		let goal = 25000;
		let current_val = 20130;

		let g = new frappe.ui.Graph({
			parent: $('.form-graph').empty(),
			height: 200,					// optional
			mode: 'line',					// 'line', 'bar' or 'percentage'

			title: 'Sales',
			subtitle: 'Monthly',

			y: [
				{
					title: 'Data 1',
					values: values1,
					formatted: values1.map(d => '$ ' + d),
					color: 'green'		// Indicator colors: 'grey', 'blue', 'red',
								// 'green', 'light-green', 'orange', 'purple', 'darkgrey',
								// 'black', 'yellow', 'lightblue'
				},
				{
					title: 'Data 2',
					values: values2,
					formatted: values2.map(d => '$ ' + d),
					color: 'light-green'
				}
			],

			x: {
				values: months.map(d => d.substring(0, 3)),
				formatted: months
			},

			specific_values: [
				{
					name: 'Goal',
					line_type: 'dashed',	// 'dashed' or 'solid'
					value: goal
				},
			],

			summary: [
				{
					name: 'This month',
					color: 'orange',
					value: '$ ' + current_val
				},
				{
					name: 'Goal',
					color: 'blue',
					value: '$ ' + goal
				},
				{
					name: 'Completed',
					color: 'green',
					value: (current_val/goal*100).toFixed(1) + "%"
				}
			]
		});

<img src="/docs/assets/img/desk/line_graph_sales.png" class="screenshot">

`bar` mode yeilds:

<img src="/docs/assets/img/desk/bar_graph.png" class="screenshot">

You can set the `colors` property of `x` to an array of color values for `percentage` mode:

<img src="/docs/assets/img/desk/percentage_graph.png" class="screenshot">

You can also change the values of an existing graph with a new set of `y` values:

		setTimeout(() => {
			g.change_values([
				{
					values: data[2],
					formatted: data[2].map(d => d + 'L')
				},
				{
					values: data[3],
					formatted: data[3].map(d => d + 'L')
				}
			]);
		}, 1000);

<img src="/docs/assets/img/desk/animated_line_graph.gif" class="screenshot">
