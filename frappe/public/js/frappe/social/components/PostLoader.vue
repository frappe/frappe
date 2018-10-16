<template>
	<div>
		<post :post="post" v-for="post in posts" :key="post.name"></post>
		<div v-if="!loading_posts && !posts.length" class="no-post text-center text-muted">
			No Posts Yet !
		</div>
		<div v-show="loading_posts" class="text-center padding">Loading posts...</div>
		<div v-show="posts.length && !more_posts_available" class="text-center padding">That's all folks</div>
	</div>
</template>
<script>
import Post from './Post.vue';

export default {
	props: ['post_list_filter'],
	components: {
		Post
	},
	data() {
		return {
			posts: [],
			more_posts_available: true,
			loading_posts: false,
			load_new: false
		}
	},
	created() {
		window.addEventListener('scroll', this.handle_scroll);
		this.update_posts();
		this.$parent.$on('load_new_posts', () => {
			this.update_posts()
		})
	},
	watch: {
		post_list_filter() {
			this.update_posts()
		}
	},
	methods: {
		get_posts(filters) {
			return frappe.db.get_list('Post', {
				fields: ['name', 'content', 'owner', 'creation', 'liked_by', 'is_pinned', 'is_globally_pinned'],
				filters: filters,
				order_by: 'creation desc',
			})
		},
		update_posts(load_new=false, load_old=false) {
			if (!this.post_list_filter) return

			const filters = Object.assign({}, this.post_list_filter);

			if (load_new && this.posts[0]) {
				filters.creation = ['>', this.posts[0].creation]
			} else if (load_old && this.posts.length) {
				const lastpost = [...this.posts].pop()
				filters.creation = ['<', lastpost.creation]
				this.loading_posts = true;
			}

			this.get_posts(filters).then((res) => {
				if (load_new) {
					this.posts = res.concat(this.posts);
				} else if (load_old) {
					if (!res.length) {
						this.more_posts_available = false;
					}
					this.posts = this.posts.concat(res);
				} else {
					this.posts = res;
				}
				this.loading_posts = false;
			});
		},
		handle_scroll: frappe.utils.debounce(function() {
			const screen_bottom = document.documentElement.scrollTop + window.innerHeight === document.documentElement.offsetHeight;
			if (screen_bottom && this.more_posts_available) {
				if (this.more_posts_available && !this.loading_posts) {
					this.loading_posts = true;
					this.update_posts(false, true);
				}
			}
		}, 500),
	},
	destroyed() {
		window.removeEventListener('scroll', this.handle_scroll);
	}
}
</script>

