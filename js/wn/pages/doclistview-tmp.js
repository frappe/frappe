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

wn.provide('wn.body');
wn.provide('wn.list_views');

wn.body.ListPage = function(doctype) {
	wn.require('lib/css/body/list.css');
	wn.require('lib/js/wn/body/tags.js');
	wn.require('lib/js/wn/utils/datetime.js');

	var me = this;
	$.extend(this, {
		make: function() {
			// page
			me.label = 'List/' + doctype;
			wn.require('lib/js/wn/body/page.js');
			me.page = new wn.body.Page(me.label, 1);
			me.page.update_history = function() {		
				window.location.hash = 'List/' + encodeURIComponent(doctype);
			}			
			var $w = $(me.page.wrapper);
			$w.append("<div></div><div></div>")
			me.page_head = 
				new wn.body.PageHead($w.find('> div:eq(0)').get(0), 
					wn.model.label_of(doctype) + ' List');
			
			me.list	= 
				new wn.body.List(me, $w.find('> div:eq(1)').get(0), doctype);
				
			me.make_sidebar();
		},
		
		make_sidebar: function() {
			me.page.sidebar.style.marginTop = '13px';
			if(wn.profile.can_read.indexOf(doctype)!=-1) {
				new wn.ui.Button({
					parent: me.page.sidebar,
					css_class: 'blue-pill',
					label: '+ New ' + wn.model.label_of(doctype),
					style: {fontSize:'11px', margin: '13px', marginTop:'0px'},
					onclick: function() {
						wn.open('Form', doctype);
					}
				})
			}
				
			
			// sidebar
			wn.require('lib/js/wn/body/page_sidebar.js')
			me.sidebar = new wn.body.page_sidebar.Sidebar(me.page.sidebar, {
				sections: [
					{
						title: 'Top Tags',
						render: function(body) {
							new wn.body.tags.TagCloud(body, doctype, function(tag) { 
								me.set_tag_filter(tag) });
						}
					}
				]
			});
		},
		
		// add a filter when a tag is clicked
		set_tag_filter: function(tag) {
			me.list.flist.set_filter_display();
			var l = tag.label;
			if(tag.fieldname=='_user_tags') l = '%' + tag.label
			me.list.flist.add_filter(tag.fieldname, 'like', l);
			me.list.refresh();
		}
		
	});
	me.make();
}


// args (list name)
wn.body.List = function(list_page, parent, doctype) {
	var me = this;
	me.start = 0;
	me.page_len = 20;
	
	$.extend(this, {
		setup: function() {
			wn.require('lib/js/wn/model/list.js');
			
			// doctype for rendering
			var dt = wn.model.get_doctype(doctype);

			me.preloaded = wn.list.has(doctype);

			// get the list
			var res = wn.list.get(doctype, null, me.start, me.page_len, 1);
			me.list = res.message || [];
			if(res.list_view_js) {
				eval('me.list_view_obj=' + res.list_view_js);
			}
		},
		
		make: function() {
			// body
			me.make_body();
			me.make_filters();
			me.setup();
			me.render(me.list);
			if(me.preloaded)
				me.reload();
		},
		
		make_body: function() {			
			// new / refresh area
			me.toolbar_area = wn.dom.add(parent, 'div');
			
			// list area
			me.list_area = wn.dom.add(parent, 'div');
			
			// more btn
			me.more_btn_area = wn.dom.add(parent, 'div', 'more_btn_area');
			me.nothing_more = wn.dom.add(parent, 'div', 'nothing_more round');
			
		},
		
		make_filters: function() {
			me.filter_area = wn.dom.add(me.toolbar_area, 'div');
			wn.require('lib/js/wn/body/filter.js');
			me.flist = new wn.body.FilterList(me, me.filter_area, doctype);
			
		},
		
		reload: function() {
			wn.list.diff(doctype, (me.list.length ? me.list[0].modified : null), 
				me.render_reload);
		},
		
		render_reload: function(res) {	
			me.list = res.new_list;
			me.list_area.innerHTML = ''

			if(res.list_view_js) {
				eval('me.list_view_obj=' + res.list_view_js);
			}

			me.render(me.list);
			
			// update heading
		},
		
		refresh: function() {			
			// get the list
			me.start = 0;
			me.list = wn.list.get(doctype, 
				me.flist.get_filters(), 
				me.start, me.page_len);
			me.render(me.list);
		},
		
		extend: function() {
			me.start += me.page_len
			var add = wn.list.get(doctype, me.flist.get_filters(), me.start, me.page_len);
			me.list = me.list.concat(add);
			me.render(add);
		},
		
		// render the list
		render: function(list) {
			if(me.start==0)
				me.list_area.innerHTML = '';

			$.each(list, function(i, d) {
				d.doctype = doctype;
				if(!d.__deleted) 
					new wn.body.ListItem(me, me.list_area, d);
			});

			// show filters, they may be hidden later
			wn.dom.show(me.filter_area);

			if(list.length >= me.page_len) {
				me.show_more_btn();
			} else {
				me.hide_more_btn();
			}
		},
		
		show_more_btn: function() {
			if(!me.more_btn) {
				me.more_btn = new wn.ui.Button({
					parent: me.more_btn_area,
					label: 'Show more results',
					onclick: function() {
						me.extend();
					},
					style: {
						width: '200px',
						fontSize:'14px'
					}
				})
			}
			wn.dom.show(me.more_btn_area);
			wn.dom.hide(me.nothing_more);
		},
		
		hide_more_btn: function() {
			wn.dom.hide(me.more_btn_area);
			wn.dom.show(me.nothing_more);
			if(me.list.length) {
				me.nothing_more.innerHTML = 'Thats it';
			} else {
				me.nothing_more.innerHTML = 'No matches :( Try again.';
				
				if(!me.flist.get_filters().length) {
					wn.dom.hide(me.filter_area);

					// new link
					if(wn.profile.can_create.indexOf(doctype)!=-1) {
						$(me.nothing_more).html('<div class="new_link">\
							<span class="link_type" onclick="wn.open(\'Form\', \'%(doctype)s\')">\
							Click here to create your first %(doctype_label)s\
							</span>\
						</div>'.repl({
							doctype:doctype,
							doctype_label: wn.model.label_of(doctype)
						}));
					}					
				}
			}
		}
		
		
	});
	me.make();
}

// title (link), owner, last update, delete / archive, tags
wn.body.ListItem = function(list, parent, args) {
	var me = this;
	$.extend(this, {
		make: function() {
			me.wrapper = wn.dom.add(parent, 'div', 'list_item');
			me.wrapper.innerHTML = '<div>\
				<span class="pre_subject"></span>\
				<span class="link_type subject">%(label)s</span>\
				<span class="post_subject"></span>\
				<span class="wn-icon ic-round_minus delete_btn"></span>\
				<span class="user_info">%(owner)s %(timestamp)s</span>\
			</div>\
			<div class="list_view"></div>'.repl({
				label: args.label || args.name,
				owner: args.owner,
				timestamp: wn.utils.datetime.when(args.modified)
			});
			
			$w = $(me.wrapper);
			// hide delete if no perms
			if(!(wn.model.get_doctype(args.doctype).get_perm()[0] || {}).cancel) {
				$w.find('.delete_btn').css('display','none');
			} else {
				$w.find('.delete_btn').click(function() {
					wn.require('lib/js/wn/ui/confirm.js');
					if(wn.ui.confirm('You sure you want to delete?', function() {
						wn.http.post({
							args: {
								cmd:'webnotes.widgets.menus.delete_doc',
								doctype:args.doctype, 
								name:args.name
							}
						});
						$w.slideUp();
					}));
				})
			}
			
			// open
			$w.find('.subject')
				.bind('click', function() {
					wn.open('Form', args.doctype, args.name);
				});
			
			// render body
			me.render_body($w);
		},
		
		render_body: function($w) {
			var lv = list.list_view_obj
			if(lv) {
				if(lv.subject) {
					$w.find('.subject').html(lv.subject.repl(args));
				}
				if(lv.render) {
					lv.render($w, args);
				} 
			}
		},

		render_tag: function() {

		}

	});
	me.make();
}