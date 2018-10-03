<template>
	<div class="profile-sidebar flex flex-column">
		<div v-html="user_avatar"></div>
		<div class="user-details">
			<h3>{{ user.fullname }}</h3>
			<p class="text-muted">{{ user.bio }}</p>
		</div>
		<div class="stats">
			<div class="muted-title">
				Posts
			</div>
			<div class="text-large">
				{{ post_count }}
			</div>
		</div>
	</div>
</template>
<script>
export default {
	props: ['user_id'],
	data() {
		return {
			'post_count': 0
		}
	},
	created() {
		frappe.db.count('Post', {
			'filters': {
				'owner': this.user_id
			}
		}).then(count => {
			console.log(count);
			this.post_count = count
		})
	},
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
.user-details {
	min-height: 150px
}
</style>