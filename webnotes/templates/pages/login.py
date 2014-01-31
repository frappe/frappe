import webnotes
from webnotes.webutils import render_blocks

def get_context(context):
	return render_blocks(context)
