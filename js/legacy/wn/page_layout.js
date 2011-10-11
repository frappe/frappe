/* standard 2-column layout with
	wrapper
		+ wtab
			+ main
				+ head
				+ toolbar_area
				+ body
				+ footer
			+ sidebar_area

*/
wn.PageLayout = function(args) {
	$.extend(this, args)
	this.wrapper 		= $a(this.parent, 'div');
	this.wtab 			= make_table(this.wrapper, 1, 2, '100%', [this.main_width, this.sidebar_width]);
	this.main 			= $a($td(this.wtab,0,0), 'div', 'layout_wrapper');
	this.sidebar_area 	= $a($td(this.wtab,0,1), 'div');
	this.head 			= $a(this.main, 'div');
	this.toolbar_area 	= $a(this.main, 'div');
	this.body 			= $a(this.main, 'div');
	this.footer 		= $a(this.main, 'div');
	if(this.heading) {
		this.page_head = new PageHeader(this.head, this.heading);
	}
}