<template>
	<div>
		<div class="profile-head">
			<profile-banner :user_id="user_id"></profile-banner>
		</div>
		<div class="profile-container">
			<profile-sidebar
				:user_id="user_id"
				class="profile-sidebar"
			/>
			<div class="post-container">
				<div class="list-options">
					<div
						class="option"
						:class="{'bold': show_list === 'user_posts'}"
						@click="show_list = 'user_posts'">
						<span>Posts</span>
						<span>({{ user_posts_count }})</span>
					</div>
					<div
						class="option"
						:class="{'bold': show_list === 'liked_posts'}"
						@click="show_list = 'liked_posts'">
						<span>Likes</span>
						<span>({{ liked_posts_count }})</span>
					</div>
				</div>
				<post-loader :post_list_filter="post_list_filter"></post-loader>
			</div>
			<activity-sidebar class="activity-sidebar hidden-xs"/>
		</div>
	</div>
</template>
<script>
import PostLoader from '../components/PostLoader.vue';
import ProfileSidebar from '../components/ProfileSidebar.vue';
import ActivitySidebar from	'../components/ActivitySidebar.vue';
import ProfileBanner from '../components/ProfileBanner.vue';
export default {
	props: ['user_id'],
	components: {
		PostLoader,
		ProfileSidebar,
		ProfileBanner,
		ActivitySidebar
	},
	data() {
		return {
			show_list: 'user_posts',
			post_list_filter : null,
			user_posts_count: 0,
			liked_posts_count: 0,
		}
	},
	watch: {
		show_list() {
			if (this.show_list == 'user_posts') {
				this.post_list_filter = this.get_user_posts_filter();
			} else if (this.show_list == 'liked_posts') {
				this.post_list_filter = this.get_liked_posts_filter();
			}
		}
	},
	created() {
		this.post_list_filter = this.get_user_posts_filter();
		this.set_post_count()
	},
	methods: {
		get_user_posts_filter() {
			return {
				'owner': this.user_id
			}
		},
		get_liked_posts_filter() {
			return {
				'liked_by': ['like', '%' + this.user_id + '%']
			}
		},
		set_post_count() {
			frappe.db.count('Post', { filters: this.get_user_posts_filter() })
				.then(count => this.user_posts_count = count)

			frappe.db.count('Post', { filters: this.get_liked_posts_filter() })
				.then(count => this.liked_posts_count = count)
		}
	}
}
</script>
<style lang="less" scoped>
.profile-head {
	height: 190px;
}
.profile-sidebar {
	margin-top: 60px;
	flex: 20%;
}
.right-sidebar {
	margin-top: 5px;
}
.list-options {
	display: flex;
	.option {
		cursor: pointer;
		padding: 0px 10px 10px 0;
	}
}
</style>
