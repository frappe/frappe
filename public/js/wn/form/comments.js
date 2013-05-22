wn.ui.form.Comments = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.make();
	},
	make: function() {
		var me = this;
		this.wrapper =this.parent;
		this.row = $("<div class='row'>").appendTo(this.parent);
		this.input = $('<div class="col col-lg-10">\
			<textarea rows="3"></textarea></div>')
			.appendTo(this.row)
			.find("textarea");
		this.button = $('<div class="col col-lg-1">\
			<button class="btn btn-default btn-go" class="col col-lg-1">\
				<i class="icon-ok"></i></button>\
			</div>')
			.appendTo(this.row)
			.find("button")
			.click(function() {
				me.add_comment();
			});
		this.list = $('<div class="comments" style="margin-top: 15px;"></div>')
			.appendTo(this.parent);
	},
	refresh: function() {
		var me = this;
		if(this.frm.doc.__islocal) {
			this.wrapper.toggle(false);
			return;
		}
		this.wrapper.toggle(true);
		this.list.empty();
		var comments = JSON.parse(this.frm.doc.__comments || "[]");
		$.each(comments, function(i, c) {
			if(c.comment_by==user) {
				c["delete"] = '<a class="close" href="#">&times;</a>';
			}
			c.image = wn.user_info(c.comment_by).image;
			c.comment_on = dateutil.comment_when(c.creation);
			c.fullname = wn.user_info(c.comment_by).fullname;
			
			$(repl('<div class="comment alert col col-lg-10" data-name="%(name)s">\
				<div class="row">\
					<div class="col col-lg-1">\
						<span class="avatar avatar-small"><img src="%(image)s"></span>\
					</div>\
					<div class="col col-lg-11">\
						%(comment)s%(delete)s<br>\
						<span class="small text-muted">%(fullname)s / %(comment_on)s</span>\
					</div>\
				</div>\
				</div>', c))
				.appendTo(me.list)
				.on("click", ".close", function() {
					var name = $(this).parent().attr("data-name");
					me.delete_comment(name);
					return false;
				})
		});
	},
	add_comment: function() {
		var me = this,
			txt = me.input.val();
			
		if(txt) {
			var comment = {
				doctype: "Comment",
				comment_doctype: me.frm.doctype,
				comment_docname: me.frm.docname,
				comment: txt,
				comment_by: user
			};
			
			wn.call({
				method: "webnotes.client.insert",
				args: {
					doclist:[comment]
				},
				callback: function(r) {
					if(!r.exc) {
						var comments = JSON.parse(me.frm.doc.__comments || "[]");
						me.frm.doc.__comments = JSON.stringify(r.message.concat(comments));
						me.input.val("");
						me.refresh();
					}
				}
			});
		}
	},
	delete_comment: function(name) {
		var me = this;
		wn.call({
			method: "webnotes.client.delete",
			args: {
				doctype: "Comment",
				name: name
			},
			callback: function(r) {
				if(!r.exc) {
					me.frm.doc.__comments = JSON.stringify(
						$.map(JSON.parse(me.frm.doc.__comments || "[]"), 
							function(v) { 
								if(v.name==name) return null; 
								else return v; 
							}
						)
					);
					me.refresh();
				}
			}
		});		
	}
})