// opts { width, height, title, fields (like docfields) }

wn.widgets.FieldGroup = function() {
	
	this.make_fields = function(body, fl) {
		$y(this.body, {padding:'11px'});
		this.fields_dict = {}; // reset
		for(var i=0; i<fl.length; i++) {
			var df = fl[i];
			var div = $a(body, 'div', '', {margin:'6px 0px'})
			f = make_field(df, null, div, null);
			f.not_in_form = 1;
			this.fields_dict[df.fieldname] = f
			f.refresh();
		}
	}
	
	/* get values */
	this.get_values = function() {
		var ret = {};
		var errors = [];
		for(var key in this.fields_dict) {
			var f = this.fields_dict[key];
			var v = f.get_value ? f.get_value() : null;

			if(f.df.reqd && !v) 
				errors.push(f.df.label + ' is mandatory');

			if(v) ret[f.df.fieldname] = v;
		}
		if(errors.length) {
			msgprint('<b>Please check the following Errors</b>\n' + errors.join('\n'));
			return null;
		}
		return ret;
	}
	
	/* set field value */
	this.set_value = function(key, val){
		var f = this.fields_dict[key];
		if(f) {
			f.set_input(val);
			f.refresh_mandatory();
		}		
	}

	/* set values from a dict */
	this.set_values = function(dict) {	
		for(var key in dict) {
			if(this.fields_dict[key]) {
				this.set_value(key, dict[key]);
			}
		}
	}
}