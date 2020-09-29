<template>
	<div class="user-list-container">
		<ul class="list-unstyled user-list">
			<li class="user-card user-list-header text-medium">
				<span class="rank-column"></span>
				<span class="user-details text-muted">
					<input
						class="form-control"
						type="search"
						placeholder="Search User"
						v-model="filter_users_by"
					>
				</span>
				<span class="flex-40"></span>
				<span class="flex-20 text-muted">
					<select class="form-control" data-toggle="tooltip" title="Period" v-model="period">
						<option v-for="value in period_options" :key="value" :value="value">{{ value }}</option>
					</select>
				</span>
			</li>
			<li class="user-card user-list-header text-medium">
				<span class="rank-column">#</span>
				<span class="user-details text-muted">{{ __('User') }}</span>
				<span
					class="flex-20 text-muted"
					v-for="title in ['Energy Points', 'Review Points', 'Points Given']"
					:key="title"
				>{{ __(title) }}</span>
			</li>
			<li v-for="(user, index) in filtered_users" :key="user.name">
				<div class="user-card">
					<span class="user-details flex" @click="go_to_profile_page(user.name)">
						<span class="rank-column">{{ index + 1 }}</span>
						<span v-html="get_avatar(user.name)"></span>
						<span>
							{{ user.fullname }}
							<div
								class="text-muted text-medium"
								:class="{'italic': !user.bio}"
							>{{ frappe.ellipsis(user.bio, 100) || 'No Bio'}}</div>
						</span>
					</span>
					<span
						class="text-muted text-nowrap flex-20"
						v-for="key in ['energy_points', 'review_points', 'given_points']"
						:key="key"
						@click="toggle_log(user.name)"
					>{{ user[key] }}</span>
				</div>
			</li>
			<li class="user-card text-muted" v-if="!filtered_users.length">{{__('No user found')}}</li>
		</ul>
	</div>
</template>
<script>
export default {
	data() {
		return {
			users: [],
			filter_users_by: null,
			sort_users_by: 'energy_points',
			sort_order: 'desc',
			show_log_for: null,
			period_options: ['Lifetime', 'This Month', 'This Week', 'Today'],
			period: 'This Month'
		};
	},
	computed: {
		from_date() {
			if (this.period === 'This Month') {
				return frappe.datetime.month_start();
			}
			if (this.period === 'This Week') {
				return frappe.datetime.week_start();
			}
			if (this.period === 'Today') {
				return frappe.datetime.get_today();
			}
			return null;
		},
		filtered_users() {
			let filtered = this.users.slice();
			if (this.filter_users_by) {
				filtered = filtered.filter(user =>
					user.fullname
						.toLowerCase()
						.includes(this.filter_users_by.toLowerCase())
				);
			}

			if (this.sort_users_by) {
				filtered.sort((a, b) => {
					const value_a = a[this.sort_users_by];
					const value_b = b[this.sort_users_by];

					let return_value = 0;
					if (value_a > value_b) {
						return_value = 1;
					}

					if (value_a < value_b) {
						return_value = -1;
					}

					if (this.sort_order === 'desc') {
						return_value = -return_value;
					}

					return return_value;
				});
			}
			return filtered;
		}
	},
	watch: {
		period() {
			this.fetch_users_energy_points_and_update_users();
		}
	},
	mounted() {
		$('[data-toggle="tooltip"]').tooltip();
	},
	created() {
		const standard_users = ['Administrator', 'Guest', 'guest@example.com'];
		this.users = frappe.boot.user_info;
		// delete standard users from the list
		standard_users.forEach(user => delete this.users[user]);
		this.users = Object.values(this.users);
		this.fetch_users_energy_points_and_update_users();
		frappe.realtime.on('update_points', () => {
			this.fetch_users_energy_points_and_update_users();
		});
	},
	methods: {
		get_avatar(user) {
			return frappe.avatar(user, 'avatar-medium');
		},
		go_to_profile_page(user) {
			frappe.set_route('social', 'profile', user);
		},
		fetch_users_energy_points_and_update_users() {
			frappe
				.xcall(
					'frappe.social.doctype.energy_point_log.energy_point_log.get_user_energy_and_review_points',
					{
						from_date: this.from_date
					}
				)
				.then(data => {
					let users = this.users.slice();
					this.users = users.map(user => {
						const points = data[user.name] || {};
						user.energy_points = points.energy_points || 0;
						user.review_points = points.review_points || 0;
						user.given_points = points.given_points || 0;
						return user;
					});
				});
		},
		toggle_log(user) {
			frappe.set_route('List', 'Energy Point Log', {user:user});
		}
	}
};
</script>
<style lang="less" scoped>
@import 'frappe/public/less/common';
.user-list {
	border-left: 1px solid @border-color;
	border-right: 1px solid @border-color;
	.user-card {
		display: flex;
		cursor: pointer;
		padding: 12px 15px;
		border-bottom: 1px solid @border-color;
		.user-details {
			flex: 1;
			.italic {
				font-style: italic;
			}
		}
	}
}
.rank-column {
	flex: 0 0 30px;
	align-self: center;
	.text-muted
}
.flex-20 {
	flex: 0 0 20%;
	text-align: right;
	align-self: center;
}
.flex-40 {
	flex: 0 0 40%;
}
.user-list-header {
	background-color: @light-bg;
}
.search-bar {
	position: sticky;
	top: 0;
	background: white;
	height: 75px;
	text-align: center;
	div {
		margin: auto;
	}
	width: 100%;
	left: 0;
}
.energy-point-history {
	border-bottom: 1px solid @border-color;
	background-color: @light-bg;
}
</style>



