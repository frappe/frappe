// wrapper on Select HTMLElement

wn.ele.Select = function(s){
	if(s.inp) s = s.inp;
	$.extend(this, {
		clear: function() {
			if(s) { 
				var tmplen = s.length; for(var i=0;i<tmplen; i++) s.options[0] = null; 
			} 
		},

		get_value: function(s) { 
			if(s.custom_select) {
				return s.inp.value ? s.inp.value : '';
			}
			try {
				if(s.selectedIndex<s.options.length) return s.options[s.selectedIndex].value;
				else return '';
			} catch(err) { return ''; /* IE fix */ }
		},

		add_options: function(list, sel_val, o_style) {
			for(var i=0, len=list.length; i<len; i++) {
				var o = new Option(list[i], list[i], false, (list[i]==sel_val? true : false));
				if(o_style) wn.style(o, o_style);
				s.options[s.options.length] = o;	
			}
		}
		
	})
	
}

// bc
empty_select = function(ele) { new wn.ele.Select(ele).clear(); }
sel_val = function(ele) { new wn.ele.Select(ele).get_value(); }
add_sel_options = function(ele, list, sel_val, o_style) { 
	new wn.ele.Select(ele).get_value(list, sel_val, o_style); 
}