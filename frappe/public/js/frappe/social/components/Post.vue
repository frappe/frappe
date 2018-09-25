<template>
	<div class="post-card">
		<div class="post-body">
			<div class="pull-right text-muted" v-html="post_time"></div>
			<div class="user-avatar" v-html="user_avatar"></div>
			<div class="user-name">{{ user_name }}</div>
			<div class="content" v-html="post.content"></div>
		</div>
		<post-action :comment_count="comment_count"></post-action>
	</div>
</template>
<script>
import PostAction from './PostAction.vue';
export default {
	props: ['post'],
	components: {
		PostAction
	},
	data() {
		return {
			user_avatar: frappe.avatar(this.post.owner, 'avatar-medium'),
			post_time: comment_when(this.post.creation),
			user_name: frappe.user_info(this.post.owner).fullname,
			show_comment: false,
			comment_count: 0,
			comments: null
		}
	},
	created() {

	},
	methods: {
	}
}
</script>
<style lang="less">
.post-card {
	margin-bottom: 20px;
	max-width: 500px;
	max-height: 500px;
	min-height: 70px;
	overflow: hidden;
	.post-body {
		padding: 10px 12px;
	}
	cursor: pointer;
	.user-name{
		font-weight: 900;
	}
	.user-avatar {
		float: left;
		margin-right: 10px;
		.avatar {
			width: 48px;
			height: 48px;
		}
		.avatar-frame, .standard-image {
			border-radius: 50%;
		}
	}
	.content {
		margin-left: 58px;
		font-size: 14px;
		img, iframe {
			border-radius: 5px;
			border: none;
		}
	}
}
</style>