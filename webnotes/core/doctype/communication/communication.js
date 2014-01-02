cur_frm.cscript.onload = function(doc) {
	cur_frm.fields_dict.user.get_query = function() {
		return {
			query: "webnotes.core.doctype.communication.communication.get_user"
		}
	};
		
	if(doc.content)
		doc.content = wn.utils.remove_script_and_style(doc.content);
}