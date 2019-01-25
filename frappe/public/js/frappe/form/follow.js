// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide("frappe.ui.form");

frappe.ui.form.Follow = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.followed = this.parent.find('.form-followed');
		this.anchor = this.parent.find(".anchor-document-follow");
		this.follow_span = this.parent.find(".anchor-document-follow > span");
		this.followed_by_label = this.parent.find(".followed-by-label");
	},
	refresh: function() {
		this.render_sidebar();
		this.followed_by();
	},
	render_sidebar: function() {
		var check_enable= this.frm.get_docinfo().check;
		var me= this;
		this.set_follow();
		if (frappe.session.user == "Administrator" || check_enable != 1){
			this.anchor.addClass("hidden");
		}else{
			this.anchor.on("click", function(){
				me.anchor.addClass("text-muted");
				if(me.follow_span.text() == "Follow"){
					frappe.call({
						method: 'frappe.desk.form.doc_subscription.add_subcription',
						args: {
							'doctype': cur_frm.doctype,
							'doc_name': cur_frm.doc.name,
							'user_email': frappe.session.user
						},
						callback: function(r) {
							if (r) {
								frappe.show_alert({
									message: __('You are now following this document. You will receive daily updates via email. You can change this in User Settings.'),
									indicator: 'orange'
								});
								me.anchor.removeClass("text-muted");
								me.follow_span.html(__("Unfollow"));
								me.followed_by_label.removeClass("hide");
								me.followed_by();
							}
						}
					});
				} else {
					frappe.call({
						method: 'frappe.desk.form.doc_subscription.unfollow',
						args: {
							'doctype': cur_frm.doctype,
							'doc_name': cur_frm.doc.name,
							'user_email': frappe.session.user
						},
						callback: function(r) {
							if(r){
								frappe.show_alert({message:__("You Unfollowed this document"), indicator:'red'});
								me.anchor.removeClass("text-muted");
								me.follow_span.html(__("Follow"));
								me.followed.empty();
								me.followed_by_label.addClass("hide");
							}
						}
					});
				}
			});
		}
	},
	set_follow: function(){
		var subs= this.frm.get_docinfo().check_follow;
		if(subs == 0){
			this.follow_span.html("Unfollow");
			this.followed.removeClass("hide");
		}else{
			this.follow_span.html("Follow");
			this.followed_by_label.addClass("hide");
			this.followed.empty();
		}
	},
	followed_by: function() {
		var me = this;
		if(this.follow_span.text() == "Unfollow"){
			me.followed_by_label.removeClass("hide");
			this.get_followed_user().then(user =>{
				$(user).appendTo(me.followed);
			});
		}
	},
	get_followed_user: function(){
		var html ='';
		return new Promise(resolve => {
			frappe.call({
				method: 'frappe.desk.form.doc_subscription.get_follow_users',
				args: {
					'doctype': cur_frm.doctype,
					'doc_name': cur_frm.doc.name,
				},
			}).then(r => {
				for (var d in r.message){
					html += frappe.avatar(r.message[d].user, "avatar-small");
				}
				resolve(html);
			});
		});
	},
});

