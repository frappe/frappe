import webnotes

def get_context():
	return {
		"obj": webnotes.bean("About Us Settings", "About Us Settings").get_controller()
	}