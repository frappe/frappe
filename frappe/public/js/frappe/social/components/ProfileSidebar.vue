<template>
	<div class="profile-sidebar flex flex-column">
		<div class="user-details">
			<h3>{{ user.fullname }}</h3>
			<p>{{ user.bio }}</p>
			<div class="location" v-if="user.location !== ''">
				<span class="text-muted"><i class="fa fa-map-marker">&nbsp;</i>{{ user.location }}</span>
			</div>
			<div class="interest" v-if="user.interest !== ''">
				<span class="text-muted"><i class="fa fa-gratipay">&nbsp;</i>{{ user.interest }}</span>
			</div>
		</div>
	</div>
</template>
<script>
export default {
	props: {
		'user_id': String,
	},
	data() {
		return {
			'user': frappe.user_info(this.user_id)
		}
	},
}
</script>

<style lang="less" scoped>
.profile-sidebar {
	padding: 10px 10px 0 0
}
.user-details {
	min-height: 150px;
	.location, .interest {
		margin-bottom: 10px;
	}
}
.stats {
	display: flex;
	.like_count, .post_count {
		padding: 10px 20px 10px 0;
		cursor: pointer;
	}
}
</style>
