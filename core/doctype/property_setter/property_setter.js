// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt 

$.extend(cur_frm.cscript, {
	validate: function(doc) {
		if(doc.property_type=='Check' && !in_list(['0','1'], doc.value)) {
			msgprint('Value for a check field can be either 0 or 1');
			validated = false;
		}
	}
})