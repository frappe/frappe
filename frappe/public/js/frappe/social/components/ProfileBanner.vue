<template>
	<div ref="banner" class="banner" :style="background_style">
		<div
			class="user-avatar container"
			v-html="user_avatar">
		</div>
	</div>
</template>
<script>
export default {
	props: ['user_id'],
	data() {
		return {
			user_avatar: frappe.avatar(this.user_id, 'avatar-xl'),
			user_banner: frappe.user_info(this.user_id).banner_image
		}
	},
	created() {
		this.$root.$on('user_image_updated', () => {
			this.user_avatar = frappe.avatar(this.user_id, 'avatar-xl')
			this.user_banner = frappe.user_info(this.user_id).banner_image
		})
	},
	computed: {
		background_style() {
			const style = {}
			if (this.user_banner) {
				style['background-image'] = `url('${this.user_banner}')`
			}
			return style;
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
	background-color: #262626;
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

