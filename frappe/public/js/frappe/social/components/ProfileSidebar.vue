<template>
	<div class="profile-sidebar flex flex-column">
		<div :class="{'editable-image': is_own_profile}" @click="update_image" v-html="user_avatar"></div>
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
			'is_own_profile': this.user_id === frappe.session.user,
			'user_avatar': frappe.avatar(this.user_id, 'avatar-xl'),
			'user': frappe.user_info(this.user_id)
		}
	},
	created() {
		this.$root.$on('user_image_updated', () => {
			this.user_avatar = frappe.avatar(this.user_id, 'avatar-xl')
		})
	},
	methods: {
		update_image() {
			if (this.is_own_profile) {
				frappe.social.update_user_image.show()
			}
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
.editable-image {
	.avatar {
		cursor: pointer;
		&:hover {
			opacity: 0.5;
		}
	}
}
</style>
