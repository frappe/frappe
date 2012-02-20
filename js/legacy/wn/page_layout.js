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
	this.wrapper 		= $a(this.parent, 'div', 'layout-wrapper layout-wrapper-background');
	this.main 			= $a(this.wrapper, 'div', 'layout-main-section');
	this.sidebar_area 	= $a(this.wrapper, 'div', 'layout-side-section');
	$a(this.wrapper, 'div', '', {clear:'both'});
	this.head 			= $a(this.main, 'div');	
	this.toolbar_area 	= $a(this.main, 'div');
	this.body 			= $a(this.main, 'div');
	this.footer 		= $a(this.main, 'div');
	if(this.heading) {
		this.page_head = new PageHeader(this.head, this.heading);
	}
}