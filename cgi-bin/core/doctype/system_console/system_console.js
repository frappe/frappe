cur_frm.cscript['Server (Python)'] = function(doc, dt, dn) {
	doc.response = 'Executing...'
	refresh_field('response');
	$c_obj([doc], 'execute_server', '', function(r, rt) {
		doc = locals[doc.doctype][doc.name];
		if(r.exc) {
			doc.response = r.exc;
		} else {
			doc.response = 'Worked!'.bold()
		}
		refresh_field('response');
	})
}

cur_frm.cscript['Client (JS)'] = function(doc, dt, dn) {
	try {
		doc.response = eval(doc.script);		
	} catch(e) {
		doc.response = e.toString() 
			+ '\nMessage:' + e.message
			+ '\nLine Number:' + e.lineNumber
			+ '\nStack:' + e.stack;
	}
	refresh_field('response');
}