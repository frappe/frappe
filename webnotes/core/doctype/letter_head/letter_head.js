// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt 

cur_frm.cscript.refresh = function(doc) {	
	cur_frm.set_intro("");
	if(doc.__islocal) {
		cur_frm.set_intro(wn._("Step 1: Set the name and save."));
	} else if(!cur_frm.doc.content) {
		cur_frm.set_intro(wn._("Step 2: Set Letterhead content."));
	}
}