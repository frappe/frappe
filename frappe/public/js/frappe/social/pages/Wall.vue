<template>
	<div class="wall-container">
		<post-sidebar class="post-sidebar hidden-xs"></post-sidebar>
		<div class="post-container">
			<div
				class="new_posts_count"
				@click="load_new_posts"
				v-show='new_posts_count'>
				{{ new_posts_count + ' new post'}}
			</div>
			<post-loader :post_list_filter="{}"></post-loader>
		</div>
		<activity-sidebar class="activity-sidebar hidden-xs"/>
	</div>
</template>
<script>
import PostLoader from '../components/PostLoader.vue';
import PostSidebar from '../components/PostSidebar.vue';
import ActivitySidebar from '../components/ActivitySidebar.vue';

export default {
	components: {
		PostLoader,
		PostSidebar,
		ActivitySidebar
	},
	data() {
		return {
			'posts': [],
			'events': [],
			'new_posts_count': 0,
		}
	},
	created() {
		frappe.realtime.on('new_post', (post_owner) => {
			if (post_owner === frappe.session.user) {
				this.load_new_posts()
			} else {
				this.new_posts_count += 1;
			}
		})
	},
	methods: {
		load_new_posts() {
			this.$emit('load_new_posts');
			this.new_posts_count = 0;
		}
	}
};
</script>
