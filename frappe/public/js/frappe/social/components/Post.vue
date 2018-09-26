<template>
	<div class="post-card">
		<div class="post-body">
			<div class="pull-right text-muted" v-html="post_time"></div>
			<div class="user-avatar" v-html="user_avatar"></div>
			<div class="user-name">{{ user_name }}</div>
			<div class="content" v-html="post.content"></div>
		</div>
		<post-action :reply_count="reply_count" @reply="toggle_reply" @new_reply="create_new_reply"></post-action>
		<post-reply class="post-reply" v-if="show_replies" :replies="replies"></post-reply>
	</div>
</template>
<script>
import PostReply from './PostReply.vue';
import PostAction from './PostAction.vue';

frappe.provide('frappe.social');

const Post = {
	props: ['post'],
	components: {
		PostAction,
		PostReply
	},
	data() {
		return {
			user_avatar: frappe.avatar(this.post.owner, 'avatar-medium'),
			post_time: comment_when(this.post.creation),
			user_name: frappe.user_info(this.post.owner).fullname,
			reply_count: 0,
			replies: [{
				content: 'hello',
				name: 'asdfasdf'
			}],
			show_replies: false
		}
	},
	created() {
		frappe.db.get_list('Post', {
			fields: ['name', 'content', 'owner', 'creation'],
			order_by: 'creation desc',
			filters: {
				reply_to: this.post.name
			}
		}).then(replies => {
			this.replies = replies;
		})
		frappe.realtime.on('new_post_reply', (post) => {
			if (post.reply_to === this.post.name) {
				this.reply_count += 1;
			}
		})
	},
	methods: {
		create_new_reply: () => {
			frappe.social.post_reply_dialog.show()
		},
		toggle_reply: () => {
			this.show_repies = !this.show_replies
		}
	}
}

frappe.social.Post = Post;

export default Post;
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
	.post-reply {
		margin-left: 10px;
	}
}
</style>