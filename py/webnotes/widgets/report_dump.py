# Copyright (c) 2012 Web Notes Technologies Pvt Ltd (http://erpnext.com)
# 
# MIT License (MIT)
# 
# Permission is hereby granted, free of charge, to any person obtaining a 
# copy of this software and associated documentation files (the "Software"), 
# to deal in the Software without restriction, including without limitation 
# the rights to use, copy, modify, merge, publish, distribute, sublicense, 
# and/or sell copies of the Software, and to permit persons to whom the 
# Software is furnished to do so, subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in 
# all copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
# INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
# PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
# HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF 
# CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE 
# OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#

import webnotes
import json

@webnotes.whitelist()
def get_data():
	from startup.report_data_map import data_map
	
	doctypes = json.loads(webnotes.form_dict.get("doctypes"))
	out = {}
	for d in doctypes:
		args = data_map[d]
		conditions = order_by = ""
		if args.get("conditions"):
			conditions = " where " + " and ".join(args["conditions"])
		if args.get("order by"):
			order_by = " order by " + args["order_by"]
		
		out[d] = {}
		out[d]["data"] = webnotes.conn.sql("""select %s from `tab%s` %s %s""" % (",".join(args["columns"]),
			d, conditions, order_by), as_list=1)
		out[d]["columns"] = map(lambda c: c.split(" as ")[-1], args["columns"])
	
	return out
