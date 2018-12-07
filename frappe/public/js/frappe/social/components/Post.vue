<template>
	<div class="post-card">
		<div class="post-body" :class="{'pinned ': is_pinned}">
			<div class="pull-right flex">
				<div
					class="pin-option"
					v-if="is_pinned">
					Globally Pinned
				</div>
				<post-dropdown-menu
					class="post-dropdown-menu"
					v-if="options.length"
					:options="options"
				/>
			</div>
			<div class="user-avatar" v-html="user_avatar" @click="goto_profile(post.owner)"></div>
			<a class="user-name" @click="goto_profile(post.owner)">{{ user_name }}</a>
			<div class="text-muted" v-html="post_time"></div>
			<div ref="content" class="content" v-html="post.content"></div>
		</div>
		<post-action
			:liked_by="post.liked_by"
			:comment_count="comments.length"
			@toggle_comment="toggle_comment"
			@toggle_like="toggle_like"
		/>
		<post-comment
			v-if="show_comments"
			class="post-comments"
			:comments="comments"
			@create_comment="create_comment"
		/>
	</div>
</template>
<script>
import PostAction from './PostAction.vue';
import PostComment from './PostComment.vue';
import PostDropdownMenu from './PostDropdownMenu.vue';

export default {
	props: ['post'],
	components: {
		PostAction,
		PostComment,
		PostDropdownMenu
	},
	data() {
		return {
			user_avatar: frappe.avatar(this.post.owner, 'avatar-medium'),
			post_time: comment_when(this.post.creation),
			user_name: frappe.user_info(this.post.owner).fullname,
			comment_count: 0,
			comments: [],
			show_comments: false,
			is_globally_pinnable: frappe.user_roles.includes('System Manager') && frappe.social.is_home_page(),
			is_pinnable: false,
			is_user_post_owner: this.post.owner === frappe.session.user
		}
	},
	computed: {
		can_pin() {
			return this.is_globally_pinnable || this.is_pinnable
		},
		is_pinned() {
			return false && frappe.social.is_profile_page(this.post.owner)
				|| this.post.is_globally_pinned && frappe.social.is_home_page()
		},
		options() {
			const options = []
			if (this.can_pin) {
				if (this.is_pinned) {
					options.push({
						'label': __('Unpin'),
						'action': this.toggle_pin
					})
				} else {
					options.push({
						'label': __('Pin Globally'),
						'action': this.toggle_pin
					})
				}
			}
			if (this.is_user_post_owner) {
				options.push({
					'label': __('Delete'),
					'action': this.delete_post
				})
			}
			return options;
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
		frappe.realtime.on('update_liked_by' + this.post.name, this.update_liked_by)

		frappe.realtime.on('delete_post' + this.post.name, () => {
			this.$emit('delete-post')
		})

		this.$root.$on('user_image_updated', () => {
			this.user_avatar = frappe.avatar(this.post.owner, 'avatar-medium')
		})

	},
	mounted() {
		this.$refs['content'].querySelectorAll('img').forEach((img) => {
			img.addEventListener('click', () => {
				this.$root.$emit('show_preview', img.src);
			})
		});

		this.$refs['content'].querySelectorAll('a').forEach(link_element => {
			// to open link in new tab
			link_element.target = 'blank';
			this.generate_preview(link_element);
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
		toggle_pin() {
			if (this.is_globally_pinnable) {
				frappe.db.set_value('Post', this.post.name, 'is_globally_pinned', cint(!this.is_pinned))
					.then(res => this.post.is_globally_pinned = cint(res.message.is_globally_pinned))
			}
			if (this.is_pinnable) {
				frappe.db.set_value('Post', this.post.name, 'is_pinned', cint(!this.is_pinned))
					.then(res => this.post.is_pinned = cint(res.message.is_pinned))
			}
		},
		create_comment(content) {
			const comment = frappe.model.get_new_doc('Post Comment');
			comment.content = content
			comment.parent = this.post.name;
			frappe.db.insert(comment);
		},
		delete_post() {
			frappe.confirm(__("Are you sure you want to delete this post?"), () => {
				frappe.dom.freeze();
				frappe.xcall('frappe.social.doctype.post.post.delete_post', {
					'post_name': this.post.name
				}).then(frappe.dom.unfreeze)
			})
		},
		generate_preview(link_element) {
			// TODO: move the code to separate component
			frappe.xcall('frappe.social.doctype.post.post.get_link_info', {
				'url': link_element.href
			}).then(info => {
				const title = frappe.ellipsis(info['og:title'] || info['title'], 60)
				const description = frappe.ellipsis(info['og:description'] || info['description'], 280)
				const image = info['og:image'];
				const url = info['og:url'];

				if (title) {
					link_element.insertAdjacentHTML('afterend', `
						<a href="${url}" target="blank" class="preview-card" class="flex">
							<img src="${image}"/>
							<div class="flex-column">
								<h5>${title}</h5>
								<p class="text-muted">${description}</p>
							</div>
						</a>
					` );
				}
			})
			.catch(console.error)
		}
	}
}
</script>
<style lang="less" scoped>
.post-comments {
	padding: 15px 46px;
	padding-top: 0px;
	background: #F6F6F6;
}
</style>

