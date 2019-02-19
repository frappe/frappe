<template>
	<div ref="banner" class="banner" :style="background_style">
		<div
			class="user-avatar container"
			:class="{'editable-image': is_own_profile}"
			@click="update_image"
			v-html="user_avatar">
		</div>
	</div>
</template>
<script>
export default {
	props: ['user_id'],
	data() {
		return {
			is_own_profile: this.user_id === frappe.session.user,
			user_avatar: frappe.avatar(this.user_id, 'avatar-xl'),
			background_style: {
				'background': '#262626'
			}
		}
	},
	created() {
		this.$root.$on('user_image_updated', () => {
			this.user_avatar = frappe.avatar(this.user_id, 'avatar-xl')
		})
		const user_banner = frappe.user_info(this.user_id).banner_image;
		if (user_banner) {
			this.background_style = {
				'background-image': `url('${user_banner}')`
			}
		}
	},
	methods: {
		update_image() {
			if (this.is_own_profile) {
				frappe.social.update_user_image.show()
			}
		}
	},
}
</script>
<style lang="less" scoped>
.banner {
	top: 0;
	left: 0;
	width: 100%;
	height: 300px;
	z-index: 101;
	position: absolute;
	background-size: cover;
	background-position: center;
	background-repeat: no-repeat;
	.user-avatar {
		position: relative;
		/deep/ .avatar {
			top: 220px;
			left: 10px;
			width: 150px;
			height: 150px;
			border-radius: 4px;
			background: white;
			position: absolute !important;
		}
	}
	.editable-image {
		/deep/ .avatar {
			cursor: pointer;
			:hover {
				opacity: 0.9;
			}
		}
	}
}
</style>

