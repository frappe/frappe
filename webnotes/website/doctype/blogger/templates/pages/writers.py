# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import webnotes

def get_context():
	bloggers = webnotes.conn.sql("""select * from `tabBlogger` 
	 	where ifnull(posts,0) > 0 and ifnull(disabled,0)=0 
		order by posts desc""", as_dict=1)
		
	args = {
		"bloggers": bloggers,
		"texts": {
			"all_posts_by": "All posts by"
		},
		"categories": webnotes.conn.sql_list("select name from `tabBlog Category` order by name")
	}
	
	args.update(webnotes.doc("Blog Settings", "Blog Settings").fields)
	return args