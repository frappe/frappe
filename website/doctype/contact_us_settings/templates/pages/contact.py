import webnotes

def get_context():
	return {
		"obj": webnotes.bean("Contact Us Settings", "Contact Us Settings").get_controller()
	}