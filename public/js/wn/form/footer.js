// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd.
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
		this.wrapper = $('<div class="form-footer row">\
			<!--i class="icon-cut" style="margin-top: -23px; margin-bottom: 23px; \
				display: block; margin-left: 15px; color: #888;"></i-->\
			<div class="col-md-12">\
				<div class="save-area">\
					<button class="btn btn-save btn-primary">\
						<i class="icon-save"></i> Save</button>\
				</div>\
				<div class="help-area"></div>\
			</div>\
			<div class="after-save">\
				<div class="col-md-8">\
					<div class="form-tags">\
						<h4 style="display: inline-block"><i class="icon-tag"></i> Tags</h4>\
						<span class="tag-area"></span><br>\
					</div><hr>\
					<div class="form-comments">\
						<h4><i class="icon-comments"></i> Comments</h4>\
					</div>\
				</div>\
				<div class="col-md-4">\
					<div class="form-assignments" style="margin-bottom: 7px;">\
						<h4>\
							<i class="icon-ok-sign"></i> Assigned To: \
							<button class="btn btn-small btn-default pull-right"\
								style="margin-top:-7px;">Add</button>\
						</h4>\
					</div><hr>\
					<div class="form-attachments">\
						<h4>\
							<i class="icon-paper-clip"></i> Attachments:\
							<button class="btn btn-small btn-default pull-right"\
								style="margin-top:-7px;">Add</button>\
						</h4>\
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
	show_save: function() {
		this.wrapper.find(".save-area").toggle(true);
	},
	hide_save: function() {
		this.wrapper.find(".save-area").toggle(false);
	},
	refresh: function() {
		this.toggle_save();
		if(this.frm.doc.__islocal) {
			this.wrapper.find(".after-save").toggle(false);
		} else {
			this.wrapper.find(".after-save").toggle(true);
			this.frm.attachments.refresh();
			this.frm.comments.refresh();
			this.frm.assign_to.refresh();
			this.frm.tags.refresh();
		}
	},
	toggle_save: function() {
		if(this.frm_head && this.appframe.toolbar
			&& this.appframe.buttons.Save && !this.save_disabled
			&& (this.fields && this.fields.length > 7)) {
			this.show_save();
		} else {
			this.hide_save();
		}
	}
});