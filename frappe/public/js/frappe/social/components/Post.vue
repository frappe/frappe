<template>
	<div class="post-card">
		<div class="post-body">
			<div class="pull-right text-muted" v-html="post_time"></div>
			<div class="user-avatar" v-html="user_avatar" @click="goto_profile(post.owner)"></div>
			<div class="user-name" @click="goto_profile(post.owner)">{{ user_name }}</div>
			<div class="content" v-html="post.content"></div>
		</div>
		<post-action
			:is_pinnable="is_pinnable"
			:is_pinned="post.is_pinned"
			:like_count="like_count"
			:reply_count="replies.length"
			:post_liked="post_liked"
			@toggle_reply="toggle_reply"
			@new_reply="create_new_reply"
			@toggle_like="toggle_like"
			@toggle_pin="toggle_pin"
		/>
		<post-reply
			class="post-reply"
			v-if="show_replies"
			:replies="replies"
		/>
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
	mounted() {
		this.$el.querySelectorAll('img').forEach((img) => {
			img.addEventListener('click', () => {
				this.$root.$emit('show_preview', img.src);
			})
		});
	},
	data() {
		return {
			user_avatar: frappe.avatar(this.post.owner, 'avatar-medium'),
			post_time: comment_when(this.post.creation),
			user_name: frappe.user_info(this.post.owner).fullname,
			reply_count: 0,
			replies: [],
			show_replies: false,
			is_pinnable: !this.post.reply_to && frappe.user_roles.includes('System Manager')
		}
	},
	computed: {
		like_count() {
			return this.post.liked_by ? this.post.liked_by.split('\n').length : 0;
		},
		post_liked() {
			return this.post.liked_by ? this.post.liked_by.includes(frappe.session.user) : false;
		}
	},
	created() {
		frappe.db.get_list('Post', {
			fields: ['name', 'content', 'owner', 'creation', 'liked_by', 'is_pinned', 'reply_to'],
			order_by: 'creation desc',
			filters: {
				reply_to: this.post.name
			}
		}).then(replies => {
			this.replies = replies;
		})
		frappe.realtime.on('new_post_reply' + this.post.name, (post) => {
			this.replies.push(post);
		})
		frappe.realtime.on('toggle_pin' + this.post.name, (is_pinned) => {
			this.post.is_pinned = cint(is_pinned);
		})
		frappe.realtime.on('update_liked_by' + this.post.name, this.update_liked_by)
	},
	methods: {
		goto_profile(user) {
			frappe.set_route('social', 'profile/' + user)
		},
		create_new_reply() {
			frappe.social.post_reply_dialog.set_value('reply_to', this.post.name);
			frappe.social.post_reply_dialog.show()
		},
		toggle_reply() {
			this.show_replies = !this.show_replies
		},
		update_liked_by(user) {
			const liked_by = this.post.liked_by ? this.post.liked_by.split('\n') : []
			const user_index = liked_by.indexOf(user)
			if (user_index > -1) {
				liked_by.splice(user_index, 1);
			} else {
				liked_by.push(user);
			}
			this.post.liked_by = liked_by.join('\n')
		},
		toggle_like() {
			frappe.xcall('frappe.social.doctype.post.post.toggle_like', {
				post_name: this.post.name,
			})
		},
		toggle_pin() {
			frappe.db.set_value('Post', this.post.name, 'is_pinned', cint(!this.post.is_pinned))
		}
	}
}

frappe.social.Post = Post;

export default Post;
</script>
