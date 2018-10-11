<template>
	<div>
		<div class="profile-head">
			<profile-banner :user_id="user_id"></profile-banner>
		</div>
		<div class="profile-container">
			<profile-sidebar
				:user_id="user_id"
				v-on:change_list="switch_list($event)"
				class="profile-sidebar"
			/>
			<div class="post-container">
				<profile-nav @set_list="set_list"></profile-nav>
				<post :post="post" v-for="post in current_list" :key="post.name"/>
			</div>
			<div class="pinned-posts hidden-xs">
				<div v-for="post in pinned_posts" :key="post.name">
					<post :post="post"></post>
				</div>
			</div>
		</div>
	</div>
</template>
<script>
import Post from '../components/Post.vue';
import ProfileSidebar from '../components/ProfileSidebar.vue';
import ProfileBanner from '../components/ProfileBanner.vue';
import ProfileNav from '../components/ProfileNav.vue';
export default {
	components: {
		Post,
		ProfileSidebar,
		ProfileBanner,
		ProfileNav
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
		},
		set_list(list_name) {
			this.show_list = list_name
		}
	}
}
</script>
<style lang="less" scoped>
.profile-head {
	height: 200px;
}
.profile-sidebar {
	margin-top: 50px;
}
</style>
