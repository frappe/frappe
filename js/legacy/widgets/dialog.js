//
// Dialog - old style dialog - deprecated
//

var cur_dialog;
var top_index=91;

function Dialog(w, h, title, content) {
	this.make({width:w, title:title});

	if(content)this.make_body(content);

	this.onshow = '';
	this.oncancel = '';
	this.no_cancel_flag = 0; // allow to cancel
	this.display = false;
	this.first_button = false;
}

Dialog.prototype = new wn.widgets.Dialog()

Dialog.prototype.make_body = function(content) {
	this.rows = {}; this.widgets = {};
	for(var i in content) this.make_row(content[i]);
}

Dialog.prototype.clear_inputs = function(d) {
	for(var wid in this.widgets) {
		var w = this.widgets[wid];

		var tn = w.tagName ? w.tagName.toLowerCase() : '';
		if(tn=='input' || tn=='textarea') {
			w.value = '';
		} else if(tn=='select') {
			sel_val(w.options[0].value);
		} else if(w.txt) {
			w.txt.value = '';
		} else if(w.input) {
			w.input.value = '';
		}
	}
}

Dialog.prototype.make_row = function(d) {
	var me = this;
	
	this.rows[d[1]] = $a(this.body, 'div', 'dialog_row');
	var row = this.rows[d[1]];

	if(d[0]!='HTML') {
		var t = make_table(row,1,2,'100%',['30%','70%']);
		row.tab = t;
		var c1 = $td(t,0,0);
		var c2 = $td(t,0,1);
		if(d[0]!='Check' && d[0]!='Button')
			$t(c1, d[1]);
	}
	
	if(d[0]=='HTML') {
		if(d[2])row.innerHTML = d[2];
		this.widgets[d[1]]=row;
	} 
	else if(d[0]=='Check') {
		var i = $a_input(c2, 'checkbox','',{width:'20px'});
		c1.innerHTML = d[1];
		this.widgets[d[1]] = i;
	} 
	else if(d[0]=='Data') {
		c1.innerHTML = d[1];
		c2.style.overflow = 'auto';
		this.widgets[d[1]] = $a_input(c2, 'text');
		if(d[2])$a(c2, 'div', 'field_description').innerHTML = d[2];
	} 
	else if(d[0]=='Link') {
		c1.innerHTML = d[1];
		var f = make_field({fieldtype:'Link', 'label':d[1], 'options':d[2]}, '', c2, this, 0, 1);
		f.not_in_form = 1;
		f.dialog = this;
		f.refresh();
		this.widgets[d[1]] = f.input;
	}
	else if(d[0]=='Date') {
		c1.innerHTML = d[1];
		var f = make_field({fieldtype:'Date', 'label':d[1], 'options':d[2]}, '', c2, this, 0, 1);
		f.not_in_form = 1;
		f.refresh();
		f.dialog = this;
		this.widgets[d[1]] = f.input;
	}
	else if(d[0]=='Password') {
		c1.innerHTML = d[1];
		c2.style.overflow = 'auto';
		this.widgets[d[1]] = $a_input(c2, 'password');
		if(d[3])$a(c2, 'div', 'field_description').innerHTML = d[3];
		
	} 
	else if(d[0]=='Select') {
		c1.innerHTML = d[1];
		this.widgets[d[1]] = $a(c2, 'select', '', {width:'160px'})
		if(d[2])$a(c2, 'div', 'field_description').innerHTML = d[2];
		if(d[3])add_sel_options(this.widgets[d[1]], d[3], d[3][0]);
	} 
	else if(d[0]=='Text') {
		c1.innerHTML = d[1];
		c2.style.overflow = 'auto';
		this.widgets[d[1]] = $a(c2, 'textarea');		
		if(d[2])$a(c2, 'div', 'field_description').innerHTML = d[2];
	} 
	else if(d[0]=='Button') {
		c2.style.height = '32px';
		var b = $btn(c2, d[1], function(btn) { 
			if(btn._onclick) btn._onclick(me) }, null, null, 1);
		b.dialog = me;
		if(!this.first_button) {
			$(b).addClass('primary');
			this.first_button = true;
		}
		if(d[2]) {
			b._onclick = d[2];
		}
		this.widgets[d[1]] = b;
	}
}


