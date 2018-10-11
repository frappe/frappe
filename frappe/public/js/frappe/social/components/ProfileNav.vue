<template>
	<div class="profile-nav">
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
	</div>
</template>
<script>
export default {
	data() {
		return {
			liked_posts: [],
			user_posts: [],
			show_list: 'user_posts',
		}
	}
}
</script>
<style lang="less" scoped>
.profile-nav {
	background: white;
	z-index: 100;
	.list-options {
		flex: 45%;
		display: flex;
		.option {
			cursor: pointer;
			padding: 10px 10px 10px 0
		}
	}
}
</style>
