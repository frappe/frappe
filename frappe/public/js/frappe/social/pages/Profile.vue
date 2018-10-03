<template>
	<div>
		<profile-sidebar :user_id="user_id" class="col-md-3"></profile-sidebar>
		<div class="col-md-5 post-container">
			<div v-for="post in my_posts" :key="post.name">
				<post :post="post"></post>
			</div>
		</div>
	</div>
</template>
<script>
import Post from '../components/Post.vue'
import ProfileSidebar from '../components/ProfileSidebar.vue'

export default {
	components: {
		Post,
		ProfileSidebar
	},
	data() {
		return {
			user_id: '',
			my_posts: []
		}
	},
	created() {
		this.user_id = frappe.get_route()[2];
		this.set_user_posts();
		frappe.route.on('change', () => {
			this.user_id = frappe.get_route()[2];
			this.set_user_posts()
		});
	},
	methods: {
		set_user_posts() {
			frappe.db.get_list('Post', {
				filters: {
					owner: this.user_id,
				},
				fields: ['name', 'content', 'owner', 'creation', 'liked_by', 'is_pinned'],
				order_by: 'creation desc',
			}).then((posts) => {
				this.my_posts = posts;
			})
		}
	}
}
</script>
<style lang="less" scoped>
.post-container {
	padding: 10px;
}
</style>

