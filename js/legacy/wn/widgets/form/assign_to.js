// assign to is lined to todo
// refresh - load todos
// create - new todo
// delete to do
wn.widgets.form.sidebar.AssignTo = Class.extend({
	init: function(parent, sidebar, doctype, docname) {
		var me = this;
		this.doctype = doctype;
		this.name = docname;
		this.wrapper = $a(parent, 'div', 'sidebar-comment-wrapper');
		this.body = $a(this.wrapper, 'div');
		this.add_btn = $btn($a(this.wrapper, 'div', 'sidebar-comment-message'), 'Assign', 
			function() {
				me.add();
			})
		
		this.refresh();
	},
	refresh: function() {
		var me = this;
		$c('webnotes.widgets.form.assign_to.get', {
			doctype: me.doctype,
			name: me.name
		}, function(r,rt) {
			me.render(r.message)
		})
	},
	render: function(d) {
		var me = this;
		$(this.body).empty();
		if(this.dialog) {
			this.dialog.hide();			
		}
		
		for(var i=0; i<d.length; i++) {
			$(this.body).append(repl('<div>%(owner)s \
				<a class="close" href="#" data-owner="%(owner)s">&#215</a></div>', d[i]))
		}

		// set remove
		$(this.body).find('a.close').click(function() {
			$c('webnotes.widgets.form.assign_to.remove', {
				doctype: me.doctype,
				name: me.name,
				assign_to: $(this).attr('data-owner')		
			}, function(r,rt) {me.render(r.message);});
			return false;
		});
	},
	add: function() {
		var me = this;
		if(!me.dialog) {
			me.dialog = new wn.widgets.Dialog({
				title: 'Add to To Do',
				width: 350,
				fields: [
					{fieldtype:'Link', fieldname:'assign_to', options:'Profile', 
						label:'Assign To', 
						description:'Add to To Do List of', reqd:true},
					{fieldtype:'Data', fieldname:'description', label:'Comment',
						'default': 'Assigned by ' + user}, 
					{fieldtype:'Date', fieldname:'date', label:'Complete By'}, 
					{fieldtype:'Select', fieldname:'priority', label:'Priority',
						options:'Low\nMedium\nHigh', 'default':'Medium'},
					{fieldtype:'Check', fieldname:'notify', label:'Notify By Email'},
					{fieldtype:'Button', label:'Add', fieldname:'add_btn'}
				]
			});
			me.dialog.fields_dict.add_btn.input.onclick = function() {
				
				var assign_to = me.dialog.fields_dict.assign_to.get_value();
				if(assign_to) {
					$c('webnotes.widgets.form.assign_to.add', {
						doctype: me.doctype,
						name: me.name,
						assign_to: assign_to,
						description: me.dialog.fields_dict.description.get_value(),
						priority: me.dialog.fields_dict.priority.get_value(),
						date: me.dialog.fields_dict.date.get_value(),
						notify: me.dialog.fields_dict.notify.get_value()
					}, function(r,rt) {me.render(r.message);});
				}
			}
		}
		me.dialog.clear();
		me.dialog.show();
	}
});

