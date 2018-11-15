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
		frappe.require('/assets/js/frappe-vue.min.js', () => {
			new Vue({
				el: this.$social_container[0],
				render: h => h(Home)
			});
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
		frappe.social.post_dialog.disable_primary_action();
		const post = frappe.model.get_new_doc('Post');
		post.content = values.content;
		frappe.db.insert(post).then(() => {
			frappe.social.post_dialog.clear();
			frappe.social.post_dialog.hide();
		}).finally(() => {
			frappe.social.post_dialog.enable_primary_action();
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
		const user = frappe.session.user;
		frappe.db.set_value('User', user, 'user_image', values.image)
			.then((resp) => {
				frappe.boot.user_info[user].image = resp.message.user_image;
				frappe.app_updates.trigger('user_image_updated');
				frappe.social.update_user_image.clear();
				frappe.social.update_user_image.hide();
			})
			.fail((err) => {
				frappe.msgprint(err);
			});
	}
});

frappe.social.is_home_page = () => {
	return frappe.get_route()[0] === 'social' && frappe.get_route()[1] === 'home';
};

frappe.social.is_profile_page = (user) => {
	return frappe.get_route()[0] === 'social'
		&& frappe.get_route()[1] === 'profile'
		&& (user ? frappe.get_route()[2] === user : true);
};

frappe.social.is_session_user_page = () => {
	return frappe.social.is_profile_page() && frappe.get_route()[2] === frappe.session.user;
};

frappe.provide('frappe.app_updates');

frappe.utils.make_event_emitter(frappe.app_updates);
