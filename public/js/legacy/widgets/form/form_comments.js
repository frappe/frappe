// Copyright (c) 2012 Web Notes Technologies Pvt Ltd (http://erpnext.com)
// 
// MIT License (MIT)
// 
// Permission is hereby granted, free of charge, to any person obtaining a 
// copy of this software and associated documentation files (the "Software"), 
// to deal in the Software without restriction, including without limitation 
// the rights to use, copy, modify, merge, publish, distribute, sublicense, 
// and/or sell copies of the Software, and to permit persons to whom the 
// Software is furnished to do so, subject to the following conditions:
// 
// The above copyright notice and this permission notice shall be included in 
// all copies or substantial portions of the Software.
// 
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, 
// INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A 
// PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT 
// HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF 
// CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE 
// OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
// 

wn.widgets.form.comments = {	
	n_comments: {},
	comment_list: {},
	
	sync: function(dt, dn, r) {
		var f = wn.widgets.form.comments;

		f.n_comments[dn] = r.n_comments;
		f.comment_list[dn] = r.comment_list;
	},
	
	add: function(input, dt, dn, callback) { 
		$c('webnotes.widgets.form.comments.add_comment', wn.widgets.form.comments.get_args(input, dt, dn), 
			function(r,rt) {
				// update the comments
				wn.widgets.form.comments.update_comment_list(input, dt, dn);
		
				// clean up the text area
				input.value = '';
				callback(input, dt, dn);
			}
		);
	},
	
	remove: function(dt, dn, comment_id, callback) {
		$c('webnotes.widgets.form.comments.remove_comment',{
				id:comment_id, 
				dt:dt, 
				dn:dn
			}, callback
		);
	},
	
	get_args: function(input, dt, dn) { 
		return {
			comment: input.value,
			comment_by: user,
			comment_by_fullname: user_fullname,
			comment_doctype: dt,
			comment_docname: dn
		}
	},
	
	update_comment_list: function(input, dt, dn) {
		var f = wn.widgets.form.comments;
		
		// update no of comments
		f.n_comments[dn] = cint(f.n_comments[dn]) + 1;
		
		// update comment list
		f.comment_list[dn] = add_lists(
			[f.get_args(input, dt, dn)], 
			f.comment_list[dn]
		);
	}
}