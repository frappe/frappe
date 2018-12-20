<template>
	<div class="profile-sidebar flex flex-column">
		<div class="user-details">
			<h3>{{ user.fullname }}</h3>
			<p>{{ user.bio }}</p>
			<div class="location" v-if="user.location">
				<span class="text-muted"><i class="fa fa-map-marker">&nbsp;</i>{{ user.location }}</span>
			</div>
			<div class="interest" v-if="user.interest">
				<span class="text-muted"><i class="fa fa-puzzle-piece">&nbsp;</i>{{ user.interest }}</span>
			</div>
			<a v-if="show_add_info_link" @click="go_to_user_settings">{{ __('Add your information') }}</a>
		</div>
		<a class="home-link" @click="go_to_home()"> ← {{ __('Back To Home') }}</a>
	</div>
</template>
<script>
export default {
	props: {
		'user_id': String,
	},
	data() {
		return {
			'user': frappe.user_info(this.user_id),
			'show_add_info_link': false
		}
	},
	created() {
		if (frappe.social.is_session_user_page() && this.is_info_missing()) {
			this.show_add_info_link = true;
		}
	},
	methods: {
		is_info_missing() {
			return !this.user.location || !this.user.interest || !this.user.bio;
		},
		go_to_home() {
			frappe.set_route('social', 'home');
		},
		go_to_user_settings() {
			frappe.set_route('Form', 'User', this.user_id).then(()=> {
				frappe.dom.scroll_to_section('More Information');
			})
		}
	}
}
</script>

<style lang="less" scoped>
.profile-sidebar {
	padding: 10px 10px 0 0
}
.user-details {
	min-height: 150px;
	.location, .interest {
		margin-bottom: 10px;
		i {
			width: 15px;
		}
	}
	.home-link {
		margin-top: 15px;
	}
}
</style>
