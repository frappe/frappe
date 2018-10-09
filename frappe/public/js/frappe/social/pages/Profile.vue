<template>
	<div>
		<profile-sidebar 
			:user_id="user_id" 
			v-on:change_list="switch_list($event)"
			class="col-md-3">	
		</profile-sidebar>

		<div class="post-container col-md-5">
			<div v-if="current_list === 'posts'">
				<h3>{{ current_list }}</h3>	
				<div v-for="post in get_posts" :key="post.name" > 
					<post v-if="is_own_pinned(post)" :post="post"></post>
				</div>
			</div>
			<div v-else-if="current_list === 'likes'">
				<h3>{{ current_list }}</h3>	
				<div v-for="post in get_liked_posts" :key="post.name" >
					<post v-if="is_own_pinned(post)" :post="post"></post>
				</div>
			</div>	
		</div>
		<div class="action-card-container col-md-4 hidden-xs">
			<div class="muted-title padding"><i class="fa fa-thumb-tack">&nbsp;</i> Your Pinned Posts </div>
			<div v-for="post in pinned_posts" :key="post.name">
				<post :post="post"></post>
			</div>
		</div>
		<div class="pinned-posts"></div>
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
			current_list: 'posts',
			profile_data: {}
		}
	},
	created() {
		this.user_id = frappe.get_route()[2];
		this.get_profile_data();
	},
	computed: {
		get_posts() {
			return this.profile_data.user_posts
		}, 
		pinned_posts() {
			const posts = this.profile_data.user_posts || [];
			return posts.filter((post) => post.is_pinned && post.owner === this.user_id)
		},
		get_liked_posts(){
			return this.profile_data.liked_posts
		}
		
	},
	methods: {
		get_profile_data() {
			frappe.xcall('frappe.social.doctype.post.post.set_profile_data', {
				post_user: this.user_id
			}).then(posts_obj => {
				this.profile_data = posts_obj;
			})
		},
		is_own_pinned(post) {
			return !(post.is_pinned && post.owner === this.user_id);
		},	
		switch_list(name) {
			this.current_list = name;	
		}				

	}
}
</script>
<style lang="less" scoped>
.post-container {
	padding: 10px;
	h3 {	
		text-align: center;
		text-transform: capitalize;
	}

}

</style>

