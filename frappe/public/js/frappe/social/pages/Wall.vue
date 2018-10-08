<template>
	<div class="wall-container">
		<post-sidebar class="post-sidebar hidden-xs" :user=user></post-sidebar>
		<div class="post-container">
			<div class="new_posts_count" @click="load_new_posts()" v-if='new_posts_count'>
				{{ new_posts_count + ' new post'}}
			</div>
			<div v-for="post in user_posts" :key="post.name">
				<post v-if="post.type == 'post' && !post.is_pinned" :post="post"></post>
				<event-card  v-else :event="post"></event-card>
			</div>
			<div v-show="loading_old_posts" class="text-center padding">Loading old posts</div>
			<div v-show="!more_posts_available" class="text-center padding">That's all folks</div>
		</div>
		<div class="action-card-container hidden-xs">
			<div class="muted-title padding"><i class="fa fa-thumb-tack">&nbsp;</i> Pinned Posts </div>
			<div v-for="post in pinned_posts" :key="post.name">
				<post :post="post"></post>
			</div>
		</div>
	</div>
</template>
<script>
import Post from '../components/Post.vue';
import EventCard from '../components/EventCard.vue';
import PostSidebar from '../components/PostSidebar.vue';

export default {
	components: {
		Post,
		EventCard,
		PostSidebar
	},
	data() {
		return {
			'posts': [],
			'new_posts_count': 0,
			'user': '',
			'more_posts_available': true,
			'loading_old_posts': false,
		}
	},
	created() {
		this.get_posts()
		frappe.realtime.on('new_post', (post_name) => {
			this.new_posts_count += 1;
		})
		window.addEventListener('scroll', this.handleScroll);
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
		get_posts(load_new=false, load_old=false) {
			const filters = {
				'reply_to': ''
			};
			if (load_new && this.posts[0]) {
				filters.creation = ['>', this.posts[0].creation]
			} else if (load_old && this.posts.length) {
				const lastpost = [...this.posts].pop()
				filters.creation = ['<', lastpost.creation]
			}
			frappe.db.get_list('Post', {
				fields: ['name', 'content', 'owner', 'creation', 'type', 'liked_by', 'is_pinned'],
				filters: filters,
				order_by: 'creation desc',
			}).then((res) => {
				if (load_new) {
					this.posts = res.concat(this.posts);
				} else if (load_old) {
					if (!res.length) {
						this.more_posts_available = false;
					}
					this.loading_old_posts = false;
					this.posts = this.posts.concat(res);
				} else {
					this.posts = res;
				}
			});
		},
		load_new_posts() {
			this.get_posts(true)
			this.new_posts_count = 0;
		},
		handleScroll: frappe.utils.debounce(function() {
			const screen_bottom = document.documentElement.scrollTop + window.innerHeight === document.documentElement.offsetHeight;
			if (screen_bottom && this.more_posts_available) {
				if (this.more_posts_available && !this.loading_old_posts) {
					this.loading_old_posts = true;
					this.get_posts(false, true);
				}
			}
		}, 500)
	},
	destroyed() {
		window.removeEventListener('scroll', this.handleScroll);
	}
};
</script>