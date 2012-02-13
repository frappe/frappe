import webnotes

@webnotes.whitelist()
def savedocs():
	"""save / submit / cancel / update doclist"""
	try:
		from webnotes.model.doclist import DocList
		form = webnotes.form_dict

		doclist = DocList()
		doclist.from_compressed(form.get('docs'), form.get('docname'))

		# action
		action = form.get('action')

		if action=='Update': action='update_after_submit'

		getattr(doclist, action.lower())()

		# update recent documents
		webnotes.user.update_recent(doclist.doc.doctype, doclist.doc.name)

		# send updated docs
		webnotes.response['saved'] = '1'
		webnotes.response['main_doc_name'] = doclist.doc.name
		webnotes.response['docname'] = doclist.doc.name
		webnotes.response['docs'] = [doclist.doc] + doclist.children

	except Exception, e:
		webnotes.msgprint('Did not save')
		webnotes.errprint(webnotes.utils.getTraceback())
		raise e
