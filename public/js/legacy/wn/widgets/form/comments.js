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

wn.widgets.form.sidebar.Comments = function(parent, sidebar, doctype, docname) {
	var me = this;
	this.sidebar = sidebar;
	this.doctype = doctype; this.docname = docname;
	
	this.refresh = function() {
		$c('webnotes.widgets.form.comments.get_comments', {dt: me.doctype, dn: me.docname, limit: 5}, function(r, rt) {
			wn.widgets.form.comments.sync(me.doctype, me.docname, r);
			me.make_body();
			me.refresh_latest_comment();
		});
	}
	
	this.refresh_latest_comment = function() {
		var wrapper = cur_frm.page_layout.body;
		if(!$(wrapper).find(".latest-comment").length) {
			$('<div class="latest-comment alert alert-info" style="margin-top:20px;">').prependTo(wrapper);
		}
		var comment_list = wn.widgets.form.comments.comment_list[me.docname];
		if(comment_list) {
			$(wrapper).find(".latest-comment")
				.html(repl('<div style="width: 70%; float:left;">\
					Last Comment: <b>%(comment)s</b></div>\
					<div style="width: 25%; float:right; text-align: right; font-size: 90%">\
						by %(comment_by_fullname)s</div>\
					<div class="clear"></div>', comment_list[0]))					
				.toggle(true);
		} else {
			$(wrapper).find(".latest-comment").toggle(false);			
		}
	}
	
	
	this.make_body = function() {
		if(this.wrapper) this.wrapper.innerHTML = '';
		else this.wrapper = $a(parent, 'div', 'sidebar-comment-wrapper');

		this.input = $a_input(this.wrapper, 'text');
		$(this.input).keydown(function(e) {
			if(e.which==13) {
				$(me.btn).click();
			}
		})
		this.btn = $btn(this.wrapper, 'Post', function() { me.add_comment() }, {marginLeft:'8px'});

		this.render_comments()

	}
	this.render_comments = function() {
		var f = wn.widgets.form.comments;
		var cl = f.comment_list[me.docname]
		this.msg = $a(this.wrapper, 'div', 'help small');

		if(cl) {
			this.msg.innerHTML = cl.length + ' out of ' + f.n_comments[me.docname] + ' comments';
			for(var i=0; i< cl.length; i++) {
				this.render_one_comment(cl[i]);
			}
		} else {
			this.msg.innerHTML = 'Be the first one to comment.'
		}
	}

	//
	this.render_one_comment = function(det) {
		// comment
		$a(this.wrapper, 'div', 'social sidebar-comment-text', '', det.comment);
		// by etc
		$a(this.wrapper, 'div', 'sidebar-comment-info', '', comment_when(det.creation) + ' by ' + det.comment_by_fullname);
	}
	
	this.add_comment = function() {
		if(!this.input.value) return;
		this.btn.set_working();
		wn.widgets.form.comments.add(this.input, me.doctype, me.docname, function() {
			me.btn.done_working();
			me.make_body();
			me.refresh_latest_comment();
		});
	}
	
	this.refresh();
}
