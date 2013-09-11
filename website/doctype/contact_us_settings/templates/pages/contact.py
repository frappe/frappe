import webnotes

def get_context():
	bean = webnotes.bean("Contact Us Settings", "Contact Us Settings")
	
	query_options = filter(None, bean.doc.query_options.replace(",", "\n").split()) if \
			bean.doc.query_options else ["Sales", "Support", "General"]
	
	address = webnotes.bean("Address", bean.doc.address).doc if bean.doc.address else None
	
	return {
		"query_options": query_options,
		"address": address,
		"heading": bean.doc.heading,
		"introduction": bean.doc.introduction
	}
