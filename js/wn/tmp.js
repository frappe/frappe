/// listjs - render grid

render_grid: function() {
	//this.gridid = wn.dom.set_unique_id()
	if(this.columns[0].field!='_idx') {
		this.columns = [{field:'_idx', name: 'Sr.', width: 40}].concat(this.columns);
	}
	$.each(this.columns, function(i, c) {
		if(!c.id) c.id = c.field;
	})
	
	// add sr in data
	$.each(this.data, function(i, v) {
		v._idx = i+1;
	})
	
	wn.require('lib/js/lib/slickgrid/slick.grid.css');
	wn.require('lib/js/lib/slickgrid/slick-default-theme.css');
	wn.require('lib/js/lib/slickgrid/jquery.event.drag.min.js');
	wn.require('lib/js/lib/slickgrid/slick.core.js');
	wn.require('lib/js/lib/slickgrid/slick.grid.js');
	
	var options = {
		enableCellNavigation: true,
		enableColumnReorder: false
	};		
	grid = new Slick.Grid(this.$w.find('.result-grid')
		.css('border', '1px solid grey')
		.css('height', '500px')
		.get(0), this.data, 
		this.columns, options);
    
},