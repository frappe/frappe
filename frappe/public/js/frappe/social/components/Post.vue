<template>
	<div class="post-card">
		<div class="post-body">
			<div
				class="text-muted pull-right"
				v-if="post.is_pinned || post.is_globally_pinned">
				{{ post.is_globally_pinned ? 'Globally ': ''}} Pinned
			</div>
			<div class="user-avatar" v-html="user_avatar" @click="goto_profile(post.owner)"></div>
			<div class="user-name" @click="goto_profile(post.owner)">{{ user_name }}</div>
			<div class="text-muted" v-html="post_time"></div>
			<div class="content" v-html="post.content"></div>
		</div>
		<post-action
			:is_pinnable="is_pinnable"
			:is_pinned="post.is_pinned"
			:liked_by="post.liked_by"
			:comment_count="comments.length"
			@toggle_comment="toggle_comment"
			@toggle_like="toggle_like"
			@toggle_pin="toggle_pin"
		/>
		<post-comment
			v-if="show_comments"
			class="post-comments"
			:comments="comments"
			@create_comment="create_comment">
		</post-comment>
	</div>
</template>
<script>
import PostAction from './PostAction.vue';
import PostComment from './PostComment.vue';

export default {
	props: ['post'],
	components: {
		PostAction,
		PostComment
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
			comment_count: 0,
			comments: [],
			show_comments: false,
			is_globally_pinnable: !this.post.comment_to && frappe.user_roles.includes('System Manager'),
			is_pinnable: !this.post.comment_to
				&& frappe.session.user === this.post.owner
				&& frappe.get_route()[2] === frappe.session.user
		}
	},
	created() {
		frappe.db.get_list('Post Comment', {
			fields: ['name', 'content', 'owner', 'creation'],
			order_by: 'creation desc',
			filters: {
				parent: this.post.name
			}
		}).then(comments => {
			this.comments = comments;
		})

		if (!this.post.liked_by) {
			this.$set(this.post, 'liked_by', '')
		}

		frappe.realtime.on('new_post_comment' + this.post.name, (comment) => {
			this.comments = [comment].concat(this.comments);
		})
		frappe.realtime.on('toggle_global_pin' + this.post.name, (is_globally_pinned) => {
			this.post.is_globally_pinned = cint(is_globally_pinned);
		})
		frappe.realtime.on('toggle_pin' + this.post.name, (is_pinned) => {
			this.post.is_pinned = cint(is_pinned);
		})
		frappe.realtime.on('update_liked_by' + this.post.name, this.update_liked_by)

		this.$root.$on('user_image_updated', () => {
			this.user_avatar = frappe.avatar(this.post.owner, 'avatar-medium')
		})

	},
	methods: {
		goto_profile(user) {
			frappe.set_route('social', 'profile/' + user)
		},
		toggle_comment() {
			this.show_comments = !this.show_comments
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
		},
		create_comment(content) {
			const comment = frappe.model.get_new_doc('Post Comment');
			comment.content = content
			comment.parent = this.post.name;
			frappe.db.insert(comment);
		}
	}
}
</script>
<style lang="less" scoped>
.post-comments {
	padding: 10px 46px;
	padding-top: 0px;
	background: #F6F6F6;
}
</style>

