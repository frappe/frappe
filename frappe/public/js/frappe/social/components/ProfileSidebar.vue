<template>
	<div class="profile-sidebar flex flex-column">
		<div :class="{'editable-image': is_own_profile}" @click="update_image" v-html="user_avatar"></div>
		<div class="user-details">
			<h3>{{ user.fullname }}</h3>
			<p class="text-muted">{{ user.bio }}</p>
			<p class="text-muted">{{ user.location }}</p>
			<h5>Interest</h5>
			<p class="text-muted">{{ user.interest }}</p>

			<div class="stats">
				<div class="post_count" @click="change_list('posts')">
					<h5 >Posts</h5>
					<p>{{ post_count }}</p>
				</div>
				<div class="like_count" @click="change_list('likes')">
					<h5 >Likes</h5>
					<p>{{ likes_count }}</p>
				</div>
			</div>
		</div>
	</div>
</template>
<script>
export default {
	props: {
		'user_id': String,
		'my_liked_posts': Array,
		'my_posts': Array
	},
	data() {
		return {
			'post_count': 0,
			'likes_count': 0,
			'is_own_profile': this.user_id === frappe.session.user,
			'user_avatar': frappe.avatar(this.user_id, 'avatar-xl')
		}
	},
	created() {

		frappe.db.count('Post', {
			'filters': {
				'owner': this.user_id
			}
		}).then(count => {
			this.post_count = count
		}),

		frappe.db.count('Post', {
			'filters': {
				liked_by: ['like', '%'+this.user_id+'%']
			}
		}).then(count => {
			this.likes_count = count
		})

		this.$root.$on('user_image_updated', () => {
			this.user_avatar = frappe.avatar(this.user_id, 'avatar-xl')
		})

	},
	methods: {
		change_list(name) {
			this.$emit('change_list', name)
		},
		update_image() {
			if (this.is_own_profile) {
				frappe.social.update_user_image.show()
			}
		}
	},
	computed: {
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
.stats {
	display: flex;
	.like_count, .post_count {
		padding: 10px 20px 10px 0;
		cursor: pointer;
	}
}
.editable-image {
	&:hover {
		opacity: 0.5;
	}
}
</style>
