wn.ui.form.InfoBar = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.refresh();
	},
	refresh: function() {
		var me = this;
		this.appframe.clear_infobar();
		if(this.frm.doc.__islocal)
			return;

		this.appframe.add_infobar(
			wn.user.full_name(this.frm.doc.modified_by) + " / " + comment_when(this.frm.doc.modified), function() {
			msgprint("Created By: " + wn.user.full_name(me.frm.doc.owner) + "<br>" +
				"Created On: " + dateutil.str_to_user(me.frm.doc.creation) + "<br>" +
				"Last Modified By: " + wn.user.full_name(me.frm.doc.modified_by) + "<br>" +
				"Last Modifed On: " + dateutil.str_to_user(me.frm.doc.modified), "History");
		})
		this.make_links();
		this.make_side_icons();
	},
	make_links: function() {
		
		var me = this,
			docinfo = wn.model.docinfo[this.frm.doctype][this.frm.docname],
			comments = docinfo.comments.length,
			attachments = keys(docinfo.attachments).length,
			assignments = docinfo.assignments.length;
			
		var $li1 = this.appframe.add_infobar(
			  (comments ? '<i class="icon-comments" style="font-size: 120%; color: orange"></i> ' : '')
			+ '<span class="comment-text">' + comments + " " 
			+ (comments===1 ? wn._("Comment") : wn._("Comments")) + '</span>',
			function() {
				$('html, body').animate({
					scrollTop: $(me.frm.wrapper).find(".form-comments").offset().top
				}, 2000);
			});
			
		if(comments) {
			$li1.addClass("bold");
			var last = docinfo.comments[0];
			$li1.find(".comment-text")
				.popover({
					title: "Last Comment",
					content: last.comment 
						+ '<p class="text-muted small">By '
						+ wn.user_info(last.comment_by).fullname 
						+ " / " + comment_when(last.creation)
						+ '</p>',
					trigger:"hover",
					html: true
				});
		}
			

		var $li2 = this.appframe.add_infobar(attachments + " " + (attachments===1 ? 
			wn._("Attachment") : wn._("Attachments")),
			function() {
				$('html, body').animate({
					scrollTop: $(me.frm.wrapper).find(".form-attachments").offset().top
				}, 2000);
			});
		attachments > 0 && $li2.addClass("bold");
		
		var $li3 = this.appframe.add_infobar(assignments + " " + (assignments===1 ? 
			wn._("Assignment") : wn._("Assignments")),
			function() {
				$('html, body').animate({
					scrollTop: $(me.frm.wrapper).find(".form-assignments").offset().top
				}, 2000);
			})
		assignments > 0 && $li3.addClass("bold");
		
	},
	make_side_icons: function() {
		var me = this;
		this.appframe.$w.find(".form-icon").remove();

		if(!this.frm.meta.issingle) {
			$('<i class="icon-arrow-right pull-right form-icon" title="Next Record"></i>')
				.click(function() {
					me.go_prev_next(false);
				})
				.appendTo(this.appframe.$w.find(".info-bar"));		

			$('<i class="icon-arrow-left pull-right form-icon" title="Previous Record"></i>')
				.click(function() {
					me.go_prev_next(true);
				})
				.appendTo(this.appframe.$w.find(".info-bar"));		
		}

		if(!me.frm.meta.allow_print) {
			$('<i class="icon-print pull-right form-icon" title="Print"></i>')
				.click(function() {
					me.frm.print_doc();
				})
				.appendTo(this.appframe.$w.find(".info-bar"));
		}
		
		if(!me.frm.meta.allow_email) {
			$('<i class="icon-envelope pull-right form-icon" title="Email"></i>')
				.click(function() {
					me.frm.email_doc();
				})
				.appendTo(this.appframe.$w.find(".info-bar"));		
		}
		
	},
	go_prev_next: function(prev) {
		var me = this;
		wn.call({
			method: "webnotes.widgets.form.utils.get_next",
			args: {
				doctype: me.frm.doctype,
				name: me.frm.docname,
				prev: prev ? 1 : 0
			},
			callback: function(r) {
				if(r.message)
					wn.set_route("Form", me.frm.doctype, r.message);
			}
		});
	},
})