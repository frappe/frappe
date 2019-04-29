<template>
	<div class="profile-sidebar flex flex-column">
		<div class="user-details">
			<h3>{{ user.fullname }}</h3>
			<p>{{ user.bio }}</p>
			<div class="location" v-if="user.location">
				<span class="text-muted">
					<i class="fa fa-map-marker">&nbsp;</i>
					{{ user.location }}
				</span>
			</div>
			<div class="interest" v-if="user.interest">
				<span class="text-muted">
					<i class="fa fa-puzzle-piece">&nbsp;</i>
					{{ user.interest }}
				</span>
			</div>
		</div>
		<a
			class="edit-profile-link"
			v-if="can_edit_profile"
			@click="edit_profile()"
		>{{ __('Edit Profile') }}</a>
	</div>
</template>
<script>
export default {
	props: {
		user_id: String
	},
	data() {
		return {
			user: frappe.user_info(this.user_id),
			can_edit_profile: frappe.social.is_session_user_page()
		};
	},
	methods: {
		edit_profile() {
			const edit_profile_dialog = new frappe.ui.Dialog({
				title: __('Edit Profile'),
				fields: [
					{
						fieldtype: 'Attach Image',
						fieldname: 'user_image',
						label: 'Profile Image',
						reqd: 1
					},
					{
						fieldtype: 'Data',
						fieldname: 'interest',
						label: 'Interests',
						reqd: 1
					},
					{
						fieldtype: 'Column Break'
					},
					{
						fieldtype: 'Attach Image',
						fieldname: 'banner_image',
						label: 'Banner Image',
						reqd: 1
					},
					{
						fieldtype: 'Data',
						fieldname: 'location',
						label: 'Location',
						reqd: 1
					},
					{
						fieldtype: 'Section Break',
						fieldname: 'Interest'
					},
					{
						fieldtype: 'Small Text',
						fieldname: 'bio',
						label: 'Bio',
						reqd: 1
					}
				],
				primary_action: values => {
					edit_profile_dialog.disable_primary_action();
					frappe
						.xcall('frappe.core.doctype.user.user.update_profile_info', {
							profile_info: values
						})
						.then(user => {
							user.image = user.user_image;
							let user_info = frappe.user_info(this.user_id);
							this.user = Object.assign(user_info, user);
							this.$root.$emit('user_image_updated');
							edit_profile_dialog.hide();
						})
						.finally(() => {
							edit_profile_dialog.enable_primary_action();
						});
				},
				primary_action_label: __('Save')
			});
			edit_profile_dialog.set_values({
				user_image: this.user.image,
				banner_image: this.user.banner_image,
				location: this.user.location,
				interest: this.user.interest,
				bio: this.user.bio
			});
			edit_profile_dialog.show();
		}
	}
};
</script>

<style lang="less" scoped>
.profile-sidebar {
	padding: 10px 10px 0 0;
}
.user-details {
	min-height: 150px;
	.location,
	.interest {
		margin-bottom: 10px;
		i {
			width: 15px;
		}
	}
}
.edit-profile-link {
	margin-top: 15px;
}
</style>
