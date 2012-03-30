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

// Comment Listing
// ===============
CommentList = function(parent, dt, dn) {
  this.wrapper = $a(parent, 'div', '', {margin:'16px'});
  this.input_area = $a(this.wrapper, 'div', '', {margin:'2px'});
  this.lst_area = $a(this.wrapper, 'div', '', {margin:'2px'});
  
  this.make_input();
  this.make_lst();
  this.dt;
  this.dn;
}

CommentList.prototype.run = function() {
  this.lst.run();
}

CommentList.prototype.make_input = function() {
  var me = this;
  // make the input text area and button
  this.input = $a(this.input_area, 'textarea', '', {height:'60px', width:'300px', fontSize:'14px'});
  this.btn = $btn($a(this.input_area, 'div'), 'Post', function() {me.add_comment();},{marginTop:'8px'});
}

// Add comment listing
// --------------------
CommentList.prototype.add_comment = function() {
	var me = this;
	var callback = function(input, dt, dn) {
		me.lst.run();
		
	}
	wn.widgets.form.comments.add(this.input, cur_frm.docname, cur_frm.doctype, callback)
}

// Make comment listing
// --------------------
CommentList.prototype.make_lst = function() {
  if(!this.lst) {
	wn.require('lib/js/legacy/widgets/listing.js');
    var l = new Listing('Comments', 1);
    var me = this;
    // define the columns etc
    l.colwidths = ['100%'];

    // define options
    l.opts.hide_export = 1;     l.opts.hide_print = 1;    l.opts.hide_refresh = 1;    l.opts.no_border = 1;
    l.opts.hide_rec_label = 0;    l.opts.show_calc = 0;    l.opts.round_corners = 0;
    l.opts.alt_cell_style = {};
    l.opts.cell_style = {padding:'3px'};
    l.no_rec_message = 'No comments yet. Be the first one to comment!';
    
    l.get_query = function(){
      //----------------------     0         1             2               3             4                5                   6                                                                   7                                            8             9                      10                     11                 12                 13                 14
      this.query = repl("select t1.name, t1.comment, t1.comment_by, '', \
			t1.creation, t1.comment_doctype, t1.comment_docname, \
			ifnull(concat_ws(' ',ifnull(t2.first_name,''),ifnull(t2.middle_name,''),\
			ifnull(t2.last_name,'')),''), '', \
			DAYOFMONTH(t1.creation), MONTHNAME(t1.creation), YEAR(t1.creation), \
			hour(t1.creation), minute(t1.creation), second(t1.creation) \
			from `tabComment` t1, `tabProfile` t2 \
			where t1.comment_doctype = '%(dt)s' and t1.comment_docname = '%(dn)s' \
			and t1.comment_by = t2.name order by t1.creation desc",{dt:me.dt, dn:me.dn});
			
      this.query_max = repl("select count(name) from `tabComment` where \
		comment_doctype='%(dt)s' and comment_docname='%(dn)s'",{'dt': me.dt, 'dn': me.dn});
    }

    l.show_cell = function(cell, ri, ci, d){
      new CommentItem(cell, ri, ci, d, me)
    }
    this.lst = l;
    this.lst.make(this.lst_area);

  }
}

// Comment Item
//=============
CommentItem = function(cell, ri, ci, d, comment) {
  this.comment = comment;
  $y(cell, {padding:'4px 0px'})
  var t = make_table(cell, 1, 3, '100%', ['15%', '65%', '20%'], {padding:'4px'});
  
  // image
  this.img = $a($td(t,0,0), 'img', '', {width:'40px'});
  this.cmt_by = $a($td(t,0,0), 'div');
  this.set_picture(d, ri);

  // comment
  this.cmt_dtl = $a($td(t,0,1), 'div', 'comment', {fontSize:'11px'});
  this.cmt = $a($td(t,0,1), 'div','',{fontSize:'14px'});
  this.show_cmt($td(t,0,1), ri, ci, d);

  this.cmt_delete($td(t,0,2), ri, ci, d);
}
  
// Set picture
// -----------
CommentItem.prototype.set_picture = function(d, ri){
	this.user.src = wn.user_info(d[ri][2]).image;
	this.cmt_by.innerHTML = d[ri][7] ? d[ri][7] : d[ri][2];
}

// Set comment details
// -------------------
CommentItem.prototype.show_cmt = function(cell, ri, ci, d) {
  //time  and date of comment
  if(d[ri][4]){
    hr = d[ri][12]; min = d[ri][13]; sec = d[ri][14];
    if(parseInt(hr) > 12) { time = (parseInt(hr)-12) + ':' + min + ' PM' }
    else{ time = hr + ':' + min + ' AM'}
  }
  this.cmt_dtl.innerHTML = 'On ' + d[ri][10].substring(0,3) + ' ' + d[ri][9] + ', ' + d[ri][11] + ' at ' + time;
  this.cmt.innerHTML = replace_newlines(d[ri][1]);
}

// Set delete button
// -----------------
CommentItem.prototype.cmt_delete = function(cell, ri, ci, d) {
  var me = this;
  if(d[ri][2] == user || d[ri][3] == user) {
    del = $a(cell,'i','icon-remove-sign',{cursor:'pointer'});
    del.cmt_id = d[ri][0];
    del.onclick = function(){ 
      wn.widgets.form.comments.remove(cur_frm.doctype, cur_frm.docname, this.cmt_id, 
      	function() { me.comment.lst.run(); })
    }
  }
}