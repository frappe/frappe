/* Only using native widget now - no longer want to support IE6 */

function SelectWidget(parent, options, width, editable, bg_color) {
	var me = this;
	// native select
	this.inp = $a(parent, 'select');
	if(options) add_sel_options(this.inp, options);
	if(width) $y(this.inp, {width:width});
	this.set_width = function(w) { $y(this.inp, {width:w}) };
	this.set_options = function(o) { add_sel_options(this.inp, o); }
	this.inp.onchange = function() {
		if(me.onchange)me.onchange(this);
	}
	return;
}