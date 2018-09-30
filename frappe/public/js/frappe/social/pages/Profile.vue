<template>
	<div>
		<div v-html="user_avatar"></div>
		<div v-for="post in posts" :key="post.name">
			<post :post="post"></post>
		</div>
	</div>
</template>
<script>
import Post from '../components/Post.vue'
export default {
	components: {
		Post
	},
	data() {
		return {
			user_avatar: frappe.avatar(frappe.session.user, 'avatar-xl')
		}
	},
	created() {

	}
}
</script>
<style>

</style>
