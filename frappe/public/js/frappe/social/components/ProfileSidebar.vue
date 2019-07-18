<template>
	<div class="profile-sidebar flex flex-column">
		<div class="user-details">
			<h3>{{ user.fullname }}</h3>
			<p><a @click="view_energy_point_list(user)" class="text-muted">
				{{ __("Energy Points") }}: {{ energy_points }}</a></p>
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
		<a
			class="edit-profile-link"
			v-if="can_edit_user"
			@click="edit_user()"
		>{{ __('User Settings') }}</a>

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
			can_edit_profile: frappe.social.is_session_user_page(),
			can_edit_user: frappe.session.user === this.user_id,
			energy_points: 0
		};
	},
	mounted() {
		frappe.xcall('frappe.social.doctype.energy_point_log.energy_point_log.get_user_energy_and_review_points', {user: this.user_id}).then(r => {
			this.energy_points = r[this.user_id].energy_points;
		});
	},
	methods: {
		edit_user() {
			frappe.set_route('Form', 'User', this.user_id);
		},
		edit_profile() {
			const edit_profile_dialog = new frappe.ui.Dialog({
				title: __('Edit Profile'),
				fields: [
					{
						fieldtype: 'Attach Image',
						fieldname: 'user_image',
						label: 'Profile Image',
					},
					{
						fieldtype: 'Data',
						fieldname: 'interest',
						label: 'Interests',
					},
					{
						fieldtype: 'Column Break'
					},
					{
						fieldtype: 'Attach Image',
						fieldname: 'banner_image',
						label: 'Banner Image',
					},
					{
						fieldtype: 'Data',
						fieldname: 'location',
						label: 'Location',
					},
					{
						fieldtype: 'Section Break',
						fieldname: 'Interest'
					},
					{
						fieldtype: 'Small Text',
						fieldname: 'bio',
						label: 'Bio',
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
		},
		view_energy_point_list(user) {
			frappe.set_route('List', 'Energy Point Log', {user:user.name});
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
