import Vue from 'vue/dist/vue.js';

// components
import Home from './Home.vue';
frappe.provide('frappe.social');

frappe.social.Home = class SocialHome {
	constructor({ parent }) {
		this.$parent = $(parent);
		this.page = parent.page;
		this.setup_header();
		this.make_body();
		this.set_primary_action();
	}
	make_body() {
		this.$social_container = this.$parent.find('.layout-main');

		new Vue({
			el: this.$social_container[0],
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
	title: __('Create Post'),
	fields: [
		{
			fieldtype: "Text Editor",
			fieldname: "content",
			label: __("Content"),
			reqd: 1
		}
	],
	primary_action_label: __('Post'),
	primary_action: (values) => {
		const post = frappe.model.get_new_doc('Post');
		post.content = values.content;
		frappe.db.insert(post).then(() => {
			frappe.social.post_dialog.clear();
			frappe.social.post_dialog.hide();
		});
	}
});

frappe.social.update_user_image = new frappe.ui.Dialog({
	title: __("User Image"),
	fields: [
		{
			fieldtype: "Attach Image",
			fieldname: "image",
			label: __("Image"),
			reqd: 1,
			default: frappe.user.image()
		},
	],
	primary_action_label: __('Set Image'),
	primary_action: (values) => {
		frappe.db.set_value('User', frappe.session.user, 'user_image', values.image)
			.then((resp) => {
				frappe.boot.user_info[frappe.session.user].image = resp.message.user_image;
				frappe.app_updates.trigger('user_image_updated');
				frappe.social.update_user_image.clear();
				frappe.social.update_user_image.hide();
			})
			.fail((err) => {
				frappe.msgprint(err);
			});
	}
});

frappe.provide('frappe.app_updates');

frappe.utils.make_event_emitter(frappe.app_updates);