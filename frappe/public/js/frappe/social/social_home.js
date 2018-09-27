import Vue from 'vue/dist/vue.js';

// components
import Home from './Home.vue';
import EventEmitter from './event_emitter';
frappe.provide('frappe.social');

$.extend(frappe.route, EventEmitter.prototype);

frappe.social.Home = class SocialHome {
	constructor({ parent }) {
		this.$parent = $(parent);
		this.page = parent.page;
		this.setup_header();
		// this.make_sidebar();
		this.make_body();
		this.set_primary_action();
	}
	make_body() {
		this.$body = this.$parent.find('.layout-main-section');
		this.$page_container = $('<div class="social-container">').appendTo(this.$body);

		new Vue({
			el: '.social-container',
			render: h => h(Home)
		});
	}
	setup_header() {
		this.page.set_title(__('Social'));
	}
	set_primary_action() {
		this.page.set_primary_action(__('Post'), () => {
			frappe.social.post_dialog.show();
		});
	}
};

frappe.social.post_dialog = new frappe.ui.Dialog({
	title: __("Create A Post"),
	fields: [
		{fieldtype: "Text Editor", fieldname: "content", label: __("Content"), reqd: 1},
		{fieldtype: "Link", fieldname: "reply_to", label: __("Reply"), hidden: 1}
	]
});

frappe.social.post_dialog.set_primary_action(__('Post'), () => {
	const values = frappe.social.post_dialog.get_values();
	const post = frappe.model.get_new_doc('Post');
	post.content = values.content;
	post.reply_to = values.reply_to;
	frappe.db.insert(post).then(() => {
		frappe.social.post_dialog.clear();
		frappe.social.post_dialog.hide();
	});
});

frappe.social.post_reply_dialog = new frappe.ui.Dialog({
	title: __("Reply"),
	fields: [
		{fieldtype: "Text Editor", fieldname: "content", label: __("Content"), reqd: 1},
		{fieldtype: "Link", fieldname: "reply_to", label: __("Reply"), hidden: 1}
	]
});

frappe.social.post_reply_dialog.set_primary_action(__('Reply'), () => {
	const values = frappe.social.post_reply_dialog.get_values();
	const post = frappe.model.get_new_doc('Post');
	post.content = values.content;
	post.reply_to = values.reply_to;
	console.log(post);
	frappe.db.insert(post).then(() => {
		frappe.social.post_reply_dialog.clear();
		frappe.social.post_reply_dialog.hide();
	});
});