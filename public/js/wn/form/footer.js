// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

wn.ui.form.Footer = Class.extend({
	init: function(opts) {
		var me = this;
		$.extend(this, opts);
		this.make();
		this.make_assignments();
		this.make_attachments();
		this.make_tags();
		this.make_comments();
		// render-complete
		$(this.frm.wrapper).on("render_complete", function() {
			me.refresh();
		})
	},
	make: function() {
		var me = this;
		$("<div>").css({"border-top":"1px solid #c7c7c7"}).appendTo(this.parent)
		this.wrapper = $('<div class="form-footer container">\
			<!--i class="icon-cut" style="margin-top: -23px; margin-bottom: 23px; \
				display: block; margin-left: 15px; color: #888;"></i-->\
			<div>\
				<div class="help-area"></div>\
			</div>\
			<div class="after-save row">\
				<div class="col-md-8">\
					<div class="form-comments">\
						<h5><i class="icon-comments"></i> '+wn._("Comments")+'</h5>\
					</div>\
				</div>\
				<div class="col-md-4">\
					<div class="form-tags">\
						<h5 style="display: inline-block"><i class="icon-tag"></i> '+wn._("Tags")+'</h5>\
						<span class="tag-area"></span><br>\
					</div><hr>\
					<div class="form-assignments" style="margin-bottom: 7px;">\
						<h5>\
							<i class="icon-flag"></i> '+wn._("Assigned To")+': \
							<button class="btn small btn-default pull-right"\
								style="margin-top:-7px;">'+wn._("Add")+'</button>\
						</h5>\
					</div><hr>\
					<div class="form-attachments">\
						<h5>\
							<i class="icon-paper-clip"></i> '+wn._("Attachments")+':\
							<button class="btn small btn-default pull-right"\
								style="margin-top:-7px;">'+wn._("Add")+'</button>\
						</h5>\
					</div>\
				</div>\
			</div>\
		</div>')
			.appendTo(this.parent);
		this.wrapper.find(".btn-save").click(function() {
			me.frm.save('Save', null, this);
		})
		
		this.help_area = this.wrapper.find(".help-area").get(0);
	},
	make_tags: function() {
		this.frm.tags = new wn.ui.TagEditor({
			parent: this.wrapper.find(".tag-area"),
			frm: this.frm,
		})
	},
	make_attachments: function() {
		this.frm.attachments = new wn.ui.form.Attachments({
			parent: this.wrapper.find(".form-attachments"), 
			frm: this.frm
		});
	},
	make_assignments: function() {
		this.frm.assign_to = new wn.ui.form.AssignTo({
			parent: this.wrapper.find(".form-assignments"),
			frm: this.frm
		});
	},
	make_comments: function() {
		this.frm.comments = new wn.ui.form.Comments({
			parent: this.wrapper.find(".form-comments"),
			frm: this.frm
		})
	},
	refresh: function() {
		if(this.frm.doc.__islocal) {
			this.parent.addClass("hide");
		} else {
			this.parent.removeClass("hide");
			this.frm.attachments.refresh();
			this.frm.comments.refresh();
			this.frm.assign_to.refresh();
			this.frm.tags.refresh();
		}
	},
});