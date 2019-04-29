<template>
	<div class="flex flex-column">
		<a class="leaderboard-link"
			@click.prevent="go_to_user_list()">
			{{ __('Leaderboard') }}
		</a>
		<div class="links" v-if="frequently_visited_list.length">
			<div class="muted-title">
				{{ __('Frequently Visited Links') }}
			</div>
			<div class="flex flex-column">
				<a class="route-link"
					@click.prevent="goto_list(route_obj.route)"
					v-for="route_obj in frequently_visited_list"
					:key="route_obj.route">
					{{ get_label(route_obj.route) }}
				</a>
			</div>
		</div>
	</div>
</template>
<script>
export default {
	data() {
		return {
			frequently_visited_list: [],
		}
	},
	created() {
		this.set_frequently_visited_list()
	},
	methods: {
		goto_list(route) {
			frappe.set_route(route);
		},
		set_frequently_visited_list() {
			frappe.xcall('frappe.social.doctype.post.post.frequently_visited_links')
				.then(data => {
					this.frequently_visited_list = data;
				})
		},
		get_label(route) {
			return frappe.utils.get_route_label(route);
		},
		go_to_profile_page() {
			frappe.set_route('social', 'profile', frappe.session.user)
		},
		go_to_user_list() {
			frappe.set_route('social', 'users')
		}
	}
}
</script>
<style lang="less" scoped>
.route-link {
	margin: 0px 10px 10px 0;
	text-transform: capitalize;
}
.leaderboard-link {
	.route-link;
	margin-bottom: 15px;
}
.stats {
	min-height: 150px
}
.user-details {
	.user-avatar {
		/deep/.avatar-xl {
			height: 150px;
			width: 150px;
		}
	}
	.user_name {
		display: block;
		margin-top: 10px;
		font-size: 2rem;
		font-weight: 600
	}
}
</style>

