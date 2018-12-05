<template>
	<div>
		<post-skeleton v-for="index in 5" :key="index" v-if="loading_posts && !posts.length"/>
		<transition-group name="flip-list">
			<post
				:post="post"
				v-for="(post, index) in posts"
				:key="post.name"
				@delete-post="delete_post(index)"
			/>
		</transition-group>
		<div v-if="!loading_posts && !posts.length" class="no-post-message text-muted">
			{{ __('No posts yet') }}
		</div>
		<div
			v-show="loading_posts && posts.length"
			class="text-center padding">
			{{ __('Fetching posts...') }}
		</div>
		<div
			v-show="posts.length && !loading_posts && !more_posts_available"
			class="text-center padding">
			{{ __("That's all folks") }}
		</div>
	</div>
</template>
<script>
import Post from './Post.vue';
import PostSkeleton from './PostSkeleton.vue';

export default {
	props: ['post_list_filter'],
	components: {
		Post,
		PostSkeleton
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
		frappe.realtime.on('global_pin', () => {
			this.update_posts()
		})
	},
	watch: {
		post_list_filter(old_val, new_val) {
			if (JSON.stringify(old_val) !== JSON.stringify(new_val)){
				this.update_posts()
			}
		}
	},
	methods: {
		get_posts(filters, load_old) {
			return frappe.db.get_list('Post', {
				fields: ['name', 'content', 'owner', 'creation', 'liked_by', 'is_pinned', 'is_globally_pinned'],
				filters: filters,
				limit_start: load_old ? this.posts.length : 0,
				order_by: 'is_globally_pinned desc, creation desc',
			})
		},
		update_posts(load_old = false) {
			if (!this.post_list_filter) return
			this.loading_posts = true;

			const filters = Object.assign({}, this.post_list_filter);

			this.get_posts(filters, load_old).then((res) => {
				if (load_old) {
					if (!res.length) {
						this.more_posts_available = false;
					}
					this.posts = this.posts.concat(res);
				} else {
					this.posts = res;
				}
			}).finally(() => {
				this.loading_posts = false;
			});
		},
		handle_scroll: frappe.utils.debounce(function() {
			const screen_bottom = document.documentElement.scrollTop + window.innerHeight === document.documentElement.offsetHeight;
			if (screen_bottom && this.more_posts_available) {
				if (!this.loading_posts) {
					this.update_posts(true);
				}
			}
		}, 500),
		delete_post(index) {
			this.posts.splice(index, 1);
		},
	},
	destroyed() {
		window.removeEventListener('scroll', this.handle_scroll);
	}
}
</script>
<style lang="less" scoped>
.no-post-message {
	height: 200px;
	text-align: center;
	vertical-align: middle;
	line-height: 200px;
}
.flip-list-move, .flip-list-to {
	transition: transform 0.3s;
}
</style>
