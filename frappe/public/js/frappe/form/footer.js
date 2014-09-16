// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.form.Footer = Class.extend({
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
		this.wrapper = $('<div class="form-footer container">\
			<div class="after-save row">\
				<div class="col-md-8">\
					<div class="form-comments">\
					</div>\
				</div>\
				<div class="col-md-4">\
					<div class="form-tags">\
						<div style="height: 30px;"></div>\
						<h5 style="display: inline-block"><i class="icon-tag"></i> '+__("Tags")+'</h5>\
						<span class="tag-area"></span><br>\
					</div><br><br>\
					<div class="form-assignments" style="margin-bottom: 7px;">\
						<h5>\
							<i class="icon-flag"></i> '+__("Assigned To")+': \
							<button class="btn small btn-default pull-right"\
								style="margin-top:-7px;">'+__("Add")+'</button>\
						</h5>\
					</div><br><br>\
					<div class="form-attachments">\
						<h5>\
							<i class="icon-paper-clip"></i> '+__("Attachments")+':\
							<button class="btn small btn-default pull-right"\
								style="margin-top:-7px;">'+__("Add")+'</button>\
						</h5>\
					</div>\
				</div>\
			</div>\
			<div class="pull-right" style="padding: 7px; background-color: #eee; border-radius: 4px;">\
				<a onclick="scroll(0,0)"><i class="icon-chevron-up text-muted"></i></a></div>\
		</div>')
			.appendTo(this.parent);
		this.wrapper.find(".btn-save").click(function() {
			me.frm.save('Save', null, this);
		})

	},
	make_tags: function() {
		if (this.frm.meta.issingle) {
			this.wrapper.find(".form-tags").toggle(false);
			return;
		}

		this.frm.tags = new frappe.ui.TagEditor({
			parent: this.wrapper.find(".tag-area"),
			frm: this.frm,
		})
	},
	make_attachments: function() {
		this.frm.attachments = new frappe.ui.form.Attachments({
			parent: this.wrapper.find(".form-attachments"),
			frm: this.frm
		});
	},
	make_assignments: function() {
		this.frm.assign_to = new frappe.ui.form.AssignTo({
			parent: this.wrapper.find(".form-assignments"),
			frm: this.frm
		});
	},
	make_comments: function() {
		this.frm.comments = new frappe.ui.form.Comments({
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
			this.frm.tags && this.frm.tags.refresh();
		}
	},
});
