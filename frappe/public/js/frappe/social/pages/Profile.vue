<template>
	<div class="profile-container">
		<profile-sidebar
			:user_id="user_id"
			v-on:change_list="switch_list($event)"
			class="profile-sidebar"
		/>
		<div class="post-container">
			<div class="flex padding">
				<div class="padding cursor-pointer" @click="show_list = 'user_posts'">
					<span>Posts</span>
					<span class="text-muted" >{{ user_posts.length }}</span>
				</div>
				<div class="padding cursor-pointer" @click="show_list = 'liked_posts'">
					<span>Likes</span>
					<span class="text-muted">{{ liked_posts.length }}</span>
				</div>
			</div>
			<post :post="post" v-for="post in current_list" :key="post.name"/>
		</div>
		<div class="pinned-posts hidden-xs">
			<div class="muted-title padding"><i class="fa fa-thumb-tack">&nbsp;</i> Your Pinned Posts</div>
			<div v-for="post in pinned_posts" :key="post.name">
				<post :post="post"></post>
			</div>
		</div>
	</div>
</template>
<script>
import Post from '../components/Post.vue';
import ProfileSidebar from '../components/ProfileSidebar.vue';
export default {
	components: {
		Post,
		ProfileSidebar
	},
	data() {
		return {
			user_id: '',
			show_list: 'user_posts',
			user_posts: [],
			liked_posts: [],
		}
	},
	computed: {
		pinned_posts() {
			return this.user_posts.filter(post => post.is_pinned)
		},
		current_list() {
			if(this.show_list == 'user_posts') {
				return this.user_posts;
			} else {
				return this.liked_posts;
			}
		}
	},
	created() {
		this.user_id = frappe.get_route()[2];
		this.get_user_posts().then(posts => {
			this.user_posts = posts
		})
		this.get_liked_posts().then(posts => {
			this.liked_posts = posts
		})
	},
	methods: {
		get_user_posts() {
			return frappe.db.get_list('Post', {
				'filters': {
					'owner': this.user_id
				},
				fields: ['*']
			})
		},
		get_liked_posts() {
			return frappe.db.get_list('Post', {
				'filters': {
					'liked_by': ['like', '%' + this.user_id + '%']
				},
				fields: ['*']
			})
		}
	}
}
</script>