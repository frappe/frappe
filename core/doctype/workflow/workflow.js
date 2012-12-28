wn.provide("wn.core")

wn.core.Workflow = wn.ui.form.Controller.extend({
	refresh: function(doc) {
		this.frm.set_intro("");
		if(doc.is_custom=="No" && !in_list(user_roles, 'Administrator')) {
			// make the document read-only
			this.frm.perm[0][WRITE] = 0;

			this.frm.set_intro('Standard Workflow editable by Administrator only. \
			To edit workflow, copy this and create a new Custom workflow for this Document Type')		
		} else {
			if(doc.is_active) {
				this.frm.set_intro("This Workflow is active.");
			}
		}
	}
});

cur_frm.cscript = new wn.core.Workflow({frm:cur_frm});