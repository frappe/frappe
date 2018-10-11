<template>
	<div class="profile-sidebar flex flex-column">
		<div class="user-details">
			<h3>{{ user.fullname }}</h3>
			<p class="text-muted">{{ user.bio }}</p>
			<p class="text-muted">{{ user.location }}</p>
			<h5>Interest</h5>
			<p class="text-muted">{{ user.interest }}</p>
		</div>
	</div>
</template>
<script>
export default {
	props: {
		'user_id': String,
	},
	data() {
		return {
			'user': frappe.user_info(this.user_id)
		}
	},
}
</script>

<style lang="less" scoped>
.profile-sidebar {
	padding-top: 10px
}
.user-details {
	min-height: 150px
}
.stats {
	display: flex;
	.like_count, .post_count {
		padding: 10px 20px 10px 0;
		cursor: pointer;
	}
}
</style>
