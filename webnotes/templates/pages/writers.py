# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes
from webnotes.webutils import render_blocks

def get_context(context):
	bloggers = webnotes.conn.sql("""select * from `tabBlogger` 
	 	where ifnull(posts,0) > 0 and ifnull(disabled,0)=0 
		order by posts desc""", as_dict=1)
		
	writers_context = {
		"bloggers": bloggers,
		"texts": {
			"all_posts_by": "All posts by"
		},
		"categories": webnotes.conn.sql_list("select name from `tabBlog Category` order by name")
	}
	
	writers_context.update(webnotes.doc("Blog Settings", "Blog Settings").fields)
	writers_context.update(context)
	
	return render_blocks(writers_context)
