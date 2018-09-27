<template>
	<div class="wall-container">
		<div class="new_posts_count" @click="load_new_posts()" v-if='new_posts_count'>
			{{ new_posts_count + ' new post'}}
		</div>
		<div v-for="post in posts" :key="post.name">
			<post :post="post"></post>
		</div>
	</div>
</template>
<script>
import Post from '../components/Post.vue';
export default {
	components: {
		Post
	},
	data() {
		return {
			'posts': [],
			'new_posts_count': 0
		}
	},
	created() {
		this.get_posts()
		frappe.realtime.on('new_post', (post_name) => {
			this.new_posts_count += 1;
		})
	},
	methods: {
		get_posts(load_only_new_posts = true) {
			const filters = {
				'reply_to': ''
			};
			if (load_only_new_posts && this.posts[0]) {
				filters.creation = ['>', this.posts[0].creation]
			}
			frappe.db.get_list('Post', {
				fields: ['name', 'content', 'owner', 'creation'],
				filters: filters,
				order_by: 'creation desc'
			}).then((res) => {
				if (load_only_new_posts) {
					this.posts = res.concat(this.posts);
				} else {
					this.posts = res;
				}
			});
		},
		load_new_posts() {
			this.get_posts(true) // TODO: make efficient
			this.new_posts_count = 0;
		}
	}
};
</script>

<style lang='less' scoped>
.wall-container {
	display: flex;
	flex-direction: column;
	padding-top: 10px;
	width: 500px;
	font-size: 14px;
	margin: 0;
	.new_posts_count {
		cursor: pointer;
		text-align: center;
	}
}
</style>