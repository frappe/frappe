<template>
	<div class="profile-sidebar flex flex-column">
		<div v-html="user_avatar"></div>
		<div>
			<h3>{{ user.fullname }}</h3>
			<p class="text-muted">{{ user.bio }}</p>
		</div>
	</div>
</template>
<script>
export default {
	props: ['user_id'],
	computed: {
		user_avatar() {
			return frappe.avatar(this.user_id, 'avatar-xl')
		},
		user() {
			return frappe.user_info(this.user_id)
		}
	}
}
</script>
<style lang="less" scoped>
.profile-sidebar {
	padding-top: 10px
}
</style>