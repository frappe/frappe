<template>
	<div>
		<profile-sidebar 
			:user_id="user_id" 
			v-on:change_list="switch_list($event)"
			class="col-md-3">	
		</profile-sidebar>

	
		<div class="post-container col-md-5">
			<div v-if="current_list === 'posts'">
				<h3>{{current_list}}</h3>	
				<div v-for="post in get_posts" :key="post.name" > 
					<post v-if="!post.is_pinned" :post="post"></post>
				</div>
			</div>
			<div v-else-if="current_list === 'likes'">
				<h3>{{current_list}}</h3>	
				<div v-for="post in get_liked_posts" :key="post.name" >
					<post v-if="!post.is_pinned" :post="post"></post>
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
			posts: [],
			current_list: 'posts'
			
		}
	},
	created() {
		this.user_id = frappe.get_route()[2];
		this.set_user_posts();
	},
	computed: {
		pinned_posts() {
		 	return this.posts.filter((post) => post.is_pinned&&post.owner===this.user_id)
		},
		get_posts(){
			return this.posts.filter((post) => post.owner === this.user_id)
		}, 
		get_liked_posts(){
			return this.posts.filter((post) => post.liked_by.includes(this.user_id))
		}
		
	},
	methods: {
		set_user_posts() {
			frappe.db.get_list('Post', {
				fields: ['name', 'content', 'owner', 'creation', 'liked_by', 'is_pinned'],
				order_by: 'creation desc',
			}).then((posts) => {
				this.posts = posts;
			})
		},
		switch_list(name){
			this.current_list = name;
		},
	}
}
</script>
<<<<<<< HEAD
=======
<style lang="less" scoped>
.post-container {
	padding: 10px;
	h3 {	
		text-align: center;
		text-transform: capitalize;
	}

}

</style>

>>>>>>> profile: likes, post and pinned post
