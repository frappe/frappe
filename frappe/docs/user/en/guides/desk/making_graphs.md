# Making Graphs

The Frappe UI **Graph** object enables you to render simple line and bar graphs for a discreet set of data points. You can also set special checkpoint values and summary stats.

### Example: Line graph
Here's is an example of a simple sales graph:

		render_graph: function() {
			$('.form-graph').empty();

			var months = ['Aug', 'Sep', 'Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul'];
			var values = [2410, 3100, 1700, 1200, 2700, 1600, 2740, 1000, 850, 1500, 400, 2013];

			var goal = 2500;
			var current_val = 2013;

			new frappe.ui.Graph({
				parent: $('.form-graph'),
				width: 700,
				height: 140,
				mode: 'line-graph',

				title: 'Sales',
				subtitle: 'Monthly',
				y_values: values,
				x_points: months,

				specific_values: [
					{
						name: "Goal",
						line_type: "dashed",	// "dashed" or "solid"
						value: goal
					},
				],
				summary_values: [
					{
						name: "This month",
						color: 'green',		// Indicator colors: 'grey', 'blue', 'red',
									// 'green', 'orange', 'purple', 'darkgrey',
									// 'black', 'yellow', 'lightblue'
						value: '₹ ' + current_val
					},
					{
						name: "Goal",
						color: 'blue',
						value: '₹ ' + goal
					},
					{
						name: "Completed",
						color: 'green',
						value: (current_val/goal*100).toFixed(1) + "%"
					}
				]
			});
		},

<img src="{{docs_base_url}}/assets/img/desk/line_graph.png" class="screenshot">

Setting the mode to 'bar-graph':

<img src="{{docs_base_url}}/assets/img/desk/bar_graph.png" class="screenshot">
