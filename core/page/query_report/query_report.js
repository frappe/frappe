wn.pages['query-report'].onload = function(wrapper) { 
	wn.ui.make_app_page({
		parent: wrapper,
		title: 'Query Report',
		single_column: true
	});
	
	wn.test = new wn.views.QueryReport({
		parent: wrapper,
	})	
}