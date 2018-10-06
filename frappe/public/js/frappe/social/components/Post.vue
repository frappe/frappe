<template>
	<div class="post-card">
		<div class="post-body">
			<div class="pull-right text-muted" v-html="post_time"></div>
			<div class="user-avatar" v-html="user_avatar" @click="goto_profile(post.owner)"></div>
			<div class="user-name text-muted" @click="goto_profile(post.owner)">{{ user_name }}</div>
			<div class="content" v-html="post.content"></div>
		</div>
		<post-action
			:is_globally_pinnable="is_globally_pinnable"
			:is_pinnable="is_pinnable"
			:is_globally_pinned="post.is_globally_pinned"
			:is_pinned="post.is_pinned"
			:liked_by="post.liked_by"
			:reply_count="replies.length"
			@toggle_reply="toggle_reply"
			@new_reply="create_new_reply"
			@toggle_like="toggle_like"
			@toggle_global_pin="toggle_global_pin"
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
			is_globally_pinnable: !this.post.reply_to && frappe.user_roles.includes('System Manager'),
			is_pinnable: !this.post.reply_to && this.post.owner === frappe.session.user

		}
	},
	created() {
		frappe.db.get_list('Post', {
			fields: ['name', 'content', 'owner', 'creation', 'liked_by', 'is_globally_pinned', 'is_pinned', 'reply_to'],
			order_by: 'creation desc',
			filters: {
				reply_to: this.post.name
			}
		}).then(replies => {
			this.replies = replies;
		})

		if (!this.post.liked_by) {
			this.$set(this.post, 'liked_by', '')
		}

		frappe.realtime.on('new_post_reply' + this.post.name, (post) => {
			this.replies.push(post);
		})
		frappe.realtime.on('toggle_global_pin' + this.post.name, (is_globally_pinned) => {
			this.post.is_globally_pinned = cint(is_globally_pinned);
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
		update_liked_by(liked_by) {
			this.post.liked_by = liked_by;
		},
		toggle_like() {
			frappe.xcall('frappe.social.doctype.post.post.toggle_like', {
				post_name: this.post.name,
			})
		},
		toggle_global_pin() {
			frappe.db.set_value('Post', this.post.name, 'is_globally_pinned', cint(!this.post.is_globally_pinned))
		},
		toggle_pin() {
			frappe.db.set_value('Post', this.post.name, 'is_pinned', cint(!this.post.is_pinned))
		}
	}
}

frappe.social.Post = Post;

export default Post;
</script>
