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
				<div class="list-options">
					<div
						class="option"
						:class="{'bold': show_list === 'user_posts'}"
						@click="show_list = 'user_posts'">
						<span>Posts</span>
						<span>({{ user_posts.length }})</span>
					</div>
					<div
						class="option"
						:class="{'bold': show_list === 'liked_posts'}"
						@click="show_list = 'liked_posts'">
						<span>Likes</span>
						<span>({{ liked_posts.length }})</span>
					</div>
				</div>
				<post :post="post" v-for="post in current_list" :key="post.name"/>
			</div>
			<div class="pinned-posts hidden-xs">
				<div class="muted-title padding"><i class="fa fa-thumb-tack">&nbsp;</i> Pinned Posts </div>
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
export default {
	props: ['user_id'],
	components: {
		Post,
		ProfileSidebar,
		ProfileBanner
	},
	data() {
		return {
			show_list: 'user_posts',
			user_posts: [],
			liked_posts: [],
		}
	},
	computed: {
		pinned_posts() {
			return this.user_posts.filter(post => post.is_pinned)
		},
		other_posts() {
			return this.user_posts.filter(post => !post.is_pinned)
		},
		current_list() {
			if(this.show_list == 'user_posts') {
				return this.other_posts;
			} else {
				return this.liked_posts;
			}
		}
	},
	created() {
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
.pinned-posts {
	margin-top: 5px;
}
.list-options {
	display: flex;
	.option {
		cursor: pointer;
		padding: 10px 10px 10px 0
	}
}
</style>
