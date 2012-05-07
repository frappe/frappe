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
	
	wn.require('js/lib/slickgrid/slick.grid.css');
	wn.require('js/lib/slickgrid/slick-default-theme.css');
	wn.require('js/lib/slickgrid/jquery.event.drag.min.js');
	wn.require('js/lib/slickgrid/slick.core.js');
	wn.require('js/lib/slickgrid/slick.grid.js');
	
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


//////////


	build_open_links: function(p) {
		var open_links = [];
		// make popover content
		var me = this;
		
		$.each(me.opened.concat([me.page]), function(i, p) {
			var route = wn.get_route(p._route);
		
			if(route[0]=='Form') {
				var openlist = keys(wn.views.formview[route[1]].frm.opendocs).sort();
				$.each(openlist, function(i,v) {
					if(me.page!=p || (me.page==p && me.page.frm.docname!=v)) {
						open_links.push(repl('<p><a href="#!Form/%(dt)s/%(dn)s">%(dn)s (%(dt)s)</a></p>', {
							dt: route[1],
							dn: v
						}));
					}
				});
			} else {
				if(me.page!=p) {
					open_links.push(repl('<p><a href="%(route)s">%(label)s</a></p>', {
						route: p._route,
						label: p.label
					}));				
				}
			}
		});
		return open_links;
	},
	
	select_opened_page: function() {
		var me = this;
		// side image with popover
		this.opened_selector = $('<div id="opened-page-selector">\
			<div class="popover-container"></div></div>')
			.appendTo(this.container)
			.hover(function() {
				$(this).toggleClass('active')
			}).click(function() {
				// build links
				$('#opened-page-selector .popover-container')
					.attr('data-content', me.build_open_links().reverse().join(''));


				$(this).find('.popover-container').popover('show');
				me.popoveropen = true;
				return false;
			})
			
		this.opened_selector.find('.popover-container').popover({
			title: "Open Pages",
			trigger: 'manual',
			delay: 0
		});
		
		$(document).click(function() {

			if(me.popoveropen) {
				$('#opened-page-selector .popover-container').popover('hide');
				me.popoveropen = false;				
			}
		})
		
		this.move_left(this.opened_selector);
	},
	show: function(label) { 
		return this.change_to(label); 
	}
});

////

me.set_get_query();
new wn.ui.Search({
	query: me.get_query ? me.get_query() : null,
	doctype:me.df.options,
	callback: function(val) {
		me.set_input_value(val)
	}
});