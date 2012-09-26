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

// Tree
// ---------------------------------

function Tree(parent, width, do_animate) {
  this.width = width;
  this.nodes = {};
  this.allnodes = {};
  this.cur_node;
  this.is_root = 1;
  this.do_animate = do_animate;
  var me = this;
  this.exp_img = 'lib/images/icons/plus.gif';
  this.col_img = 'lib/images/icons/minus.gif';
  
  this.body = $a(parent, 'div');
  if(width)$w(this.body, width);

  this.addNode = function(parent, id, imagesrc, onclick, onexpand, opts, label) {
    var t = new TreeNode(me, parent, id, imagesrc, onclick, onexpand, opts, label);
    
    if(!parent) {
      me.nodes[id]=t; // add to roots
    } else {
      parent.nodes[id]=t; // add to the node
    }
    me.allnodes[id] = t;

    // note: this will only be for groups
    if(onexpand)
      t.create_expimage();
    t.expanded_once = 0;

    return t;
    
  }
  var me = this;
  this.collapseall = function() {
    for(n in me.allnodes) {
      me.allnodes[n].collapse();
    }
  }
}

function TreeNode(tree, parent, id, imagesrc, onclick, onexpand, opts, label) {
  var me = this;
  if(!parent) parent = tree;
  this.parent = parent;
  this.nodes = {};
  this.onclick = onclick;
  this.onexpand = onexpand;
  this.text = label ? label : id;
  this.tree = tree;

  if(opts) 
  	this.opts = opts;
  else 
  	this.opts = {
  		show_exp_img:1
  		,show_icon:1
  		,label_style:{padding:'2px', cursor: 'pointer', fontSize:'11px'}
		,onselect_style:{fontWeight: 'bold'}
		,ondeselect_style:{fontWeight: 'normal'}
  	} // only useful for 1st node in the tree

  var tc = 1;
  if(this.opts.show_exp_img) tc+=1;

  if(!this.parent.tab) {
  	this.parent.tab = make_table(this.parent.body, 2, tc, '100%');
  	$y(this.parent.tab,{tableLayout:'fixed',borderCollapse: 'collapse'});
  } else {
    this.parent.tab.append_row(); this.parent.tab.append_row();
  } 
  
  var mytab = this.parent.tab;
  
  // expand / collapse
  if(this.opts.show_exp_img) {
    this.exp_cell=$td(mytab,mytab.rows.length-2, 0);
    $y(this.exp_cell, {cursor:'pointer', textAlign:'center', verticalAlign:'middle',width:'20px'});
    this.exp_cell.innerHTML = '&nbsp;';
  } else {
    // pass
  }
  this.create_expimage = function() {
  	if(!me.opts.show_exp_img) return; // no expand image
    if(!me.expimage) {
      me.exp_cell.innerHTML='';
      me.expimage = $a(me.exp_cell, 'img');
      me.expimage.src = me.exp_img ? me.exp_img : me.tree.exp_img;
      me.expimage.onclick = me.toggle;
    }
  }
  
  // label
  this.label = $a($td(mytab, mytab.rows.length-2, tc-1), 'div');
  $y(this.label, this.opts.label_style);
  
  // image
  if(this.opts.show_icon) { // for second row, where children will come icon to be included
    var t2 = make_table($a(this.label,'div'), 1, 2, '100%', ['20px',null]);
    $y(t2,{borderCollapse:'collapse'});
    this.img_cell = $td(t2, 0, 0);
    $y(this.img_cell, {cursor:'pointer',verticalAlign:'middle',width:'20px'});
    if(!imagesrc) imagesrc = "lib/images/icons/folder.gif";
    this.usrimg = $a(this.img_cell, 'img');
    this.usrimg.src = imagesrc;
    
    this.label = $td(t2, 0, 1);
    $y(this.label,{verticalAlign:'middle'});
  }  

  this.loading_div = $a($td(mytab, mytab.rows.length-1, this.opts.show_exp_img ? 1 : 0), "div", "comment", {fontSize:'11px'});
  $dh(this.loading_div);  
  this.loading_div.innerHTML = 'Loading...';

  this.body = $a($td(mytab, mytab.rows.length-1, this.opts.show_exp_img ? 1 : 0), "div", '', {overflow:'hidden', display:'none'});

  this.select = function() {
    me.show_selected();
    if(me.onclick)me.onclick(me);
  }

  this.show_selected = function() {
    if(me.tree.cur_node)me.tree.cur_node.deselect();
  	if(me.opts.onselect_style) $y(me.label,me.opts.onselect_style)
    //me.label.style.fontWeight = 'bold';
    me.tree.cur_node = me;
  }
  
  this.deselect = function() {
  	if(me.opts.ondeselect_style) $y(me.label,me.opts.ondeselect_style)
    //me.label.style.fontWeight = 'normal';
    me.tree.cur_node=null
  }
	
  this.expanded = 0;
  this.toggle = function() {
    if(me.expanded)
    	me.collapse();
    else 
    	me.expand();
  }
  this.collapse = function() {
    me.expanded = 0;
    $(me.body).slideUp();
    me.expimage.src = me.exp_img ? me.exp_img : me.tree.exp_img;
  }
  this.expand = function() {
    if(me.onexpand && !me.expanded_once){
    	me.onexpand(me);
    	if(!me.tree.do_animate) me.show_expanded(); // else to be called from expand (for animation)
   	} else {
   		me.show_expanded();
   	}
    me.expanded = 1;
    me.expanded_once = 1;
    me.expimage.src = me.col_img ? me.col_img : me.tree.col_img;
  }
  this.show_expanded = function() {  	
  	if(me.tree.do_animate && (!keys(me.nodes).length)) return; // no children
  	$(me.body).slideDown();
  }

  this.setlabel = function(l) {
    me.label.value = l;
    me.label.innerHTML = l;
  }

  this.setlabel(this.text);

  this.setcolor = function(c) {
    this.backColor = c;
	  if(cur_node!=this)
	  $bg(this.body,this.backColor);
  }
  
  this.label.onclick= function(e) { me.select(); }
  this.label.ondblclick = function(e) { me.select(); if(me.ondblclick)me.ondblclick(me); }
  
  this.clear_child_nodes = function() {
    if(this.tab){
      this.tab.parentNode.removeChild(this.tab);
      delete this.tab;
    }
    this.expanded_once = 0;
  }
}
