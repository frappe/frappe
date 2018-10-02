<template>
	<div class="wall-container">
		<post-sidebar class="col-md-3" :user=user></post-sidebar>
		<div class="post-container">
			<div class="new_posts_count" @click="load_new_posts()" v-if='new_posts_count'>
				{{ new_posts_count + ' new post'}}
			</div>
			<div v-for="post in user_posts" :key="post.name">
				<post v-if="post.type == 'post' && !post.is_pinned" :post="post"></post>
				<event-card  v-else :event="post"></event-card>
			</div>
		</div>
		<div class="action-card-container col-md-4">
			<div class="text-muted text-center padding"><i class="fa fa-thumb-tack"></i> Pinned Posts </div>
			<div v-for="post in pinned_posts" :key="post.name">
				<post :post="post"></post>
			</div>
		</div>
	</div>

</template>
<script>
import Post from '../components/Post.vue';
import ActionCard from '../components/ActionCard.vue';
import EventCard from '../components/EventCard.vue';
import PostSidebar from '../components/PostSidebar.vue';

export default {
	components: {
		Post,
		ActionCard,
		EventCard,
		PostSidebar
	},
	data() {
		return {
			'posts': [],
			'new_posts_count': 0,
			'user': ''
		}
	},
	created() {
		this.get_posts()
		frappe.realtime.on('new_post', (post_name) => {
			this.new_posts_count += 1;
		})
	},
	computed: {
		pinned_posts() {
			return this.posts.filter((post) => post.is_pinned)
		},
		user_posts() {
			return this.posts.filter((post) => !post.is_pinned)
		}
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
				fields: ['name', 'content', 'owner', 'creation', 'type', 'liked_by', 'is_pinned'],
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