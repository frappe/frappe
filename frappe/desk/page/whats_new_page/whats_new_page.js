frappe.pages['whats-new-page'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Whats New',
		single_column: true
	});
	new WhatsNew(page);
}

const host = "https://test-st.frappe.cloud";
const month_list = {
	0 : 'Jan',
	1 : 'Feb',
	2 : 'Mar',
	3 : 'Apr',
	4 : 'May',
	5 : 'Jun',
	6 : 'Jul',
	7 : 'Aug',
	8 : 'Sep',
	9 : 'Oct',
	10 : 'Nov',
	11 : 'Dec'
}
class WhatsNew {
	constructor(page) {

		this.page = page;
		this.$header = `<div class="whats-new-header">What's New &#10024;</div>`;
		this.make_container();
		this.bind_click_events();
		this.fetch_posts()
			.then(() => this.render_fetched_posts())
	}

	make_container() {
		this.$container = $(`<div class="main-wrapper"></div>`)
			.appendTo(this.page.body);
	}

	fetch_posts() {
		return frappe.call('frappe.desk.page.whats_new_page.whats_new_page.get_whats_new_posts')
			.then(r => {
				this.new_posts = r.message[0];
				this.events = r.message[1];
			});
	}

	get_tags(tag_list) {
		let tag_color_map = {
			'Upcoming': 'upcoming',
			'Design': 'purple',
			'Enhancement': 'yellow',
			'Version Update': 'green'
		};

		if (!tag_list)
			return ``;

		let tags_html = tag_list.map(t => {
			if (t.tag &&  t.tag != null) {
				return `<span class="indicator-pill whitespace-nowrap ${tag_color_map[t.tag]}">${t.tag}</span>`
			} else {
				return ``
			}
		}).join('');

		return tags_html;
	}

	get_post_media(post) {
		if (post.banner && post.banner != null && post.post_type != 'Upcoming Event') {
			const src = encodeURI(host + post.banner);
			return (`
				<div class="whats-new-post-media-wrapper">
					<img class='whats-new-post-media' src=${src} />
				</div>
			`)
		} else {
			return ''
		}
	}

	get_day_and_date(dt) {
		const [year, month, day] = dt.split("-");
		const formatted_date = new Date(year, month - 1, day);
		var final_date = '';

		[ month_list[formatted_date.getMonth()], formatted_date.getDate() + ',', formatted_date.getFullYear()].map(d => {
			final_date += d.toString() + ' ';
		});
		return final_date
	}

	render_event_date(post) {

		if (post.event_date) {
			const event_date = post.event_date;
			const [year, month, day] = event_date.split("-");
			const formatted_date = new Date(year, month - 1, day);

			return `
				<div class="row1">
					<span class="cal-icon fa fa-calendar "></span>
				</div>
				<div class="row2">
					<span class="">${month_list[formatted_date.getMonth()]}</span>
				</div>
				<div class="row3">
					<span class="">${formatted_date.getDate()}</span>
				</div>
			`
		} else {
			return ``
		}
	}

	get_source_link(source_link) {
		if (!source_link) {
			return ``
		} else {
			return `
				<p class="post-source-link">To know more about this, <a href=${source_link} target="_blank">click here</a>.</p>
			`
		}
	}

	get_event_date_time(event) {
		if (!event.event_time) {
			return ``
		} else {
			const [hr, min, sec] = (event.event_time).split(":");
			var hour = parseInt(hr);
			if(hour > 12) {
				hour = hour - 12;
			}

			const am_pm = (hr >= 12) ? 'PM' : 'AM';
			return `
				<p class="event-time">Time: ${hour}:${min} ${am_pm} IST (GMT +5:30 hrs)</p>
			`
		}
	}

	bind_click_events() {
		$(this.$container).on("click", ".whats-new-event-cal-link", function(e){
			const event_date = $(this).data("event_date");
			const event_time = $(this).data("event_time");
			const event_title = $(this).data("event_title");

			frappe.call({
				method: "frappe.desk.page.whats_new_page.whats_new_page.add_whats_new_event_to_calendar",
				args: {
					date :event_date,
					time: event_time,
					title: event_title
				},
				freeze:true,
				callback: function(r) {
					if (r.message) {
						return;
					}
				}
			});
		});
	}

	get_posts_html(posts) {
		let posts_html = posts.map(post => {
			const src = encodeURI(host + post.banner);

			return `
				<div class="whats-new-post-wrapper">
					<div class="whats-new-post">
						<div class="whats-new-post-header row">
							<div class="whats-new-post-title col-md-9 col-sm-12">
								<p class="whats-new-post-title"><b>${post.name}</b></p>
							</div>
							<div class="release-date-col col-md-3 col-sm-12">
								<p class="whats-new-post-date">${this.get_day_and_date(post.posting_date) || ''}</p>
							</div>
						</div>
						<div class="whats-new-post-tags">${this.get_tags(post.tags)}</div>
						<div class="whats-new-post-content">
							<div class="whats-new-post-description">
								${post.description || ''}
								${this.get_source_link(post.source_link)}
							</div>
							${this.get_post_media(post) || ''}
						</div>
					</div>
				</div>
				<hr>
			`
		}).join('');

		return posts_html;
	}

	get_events_html(events) {
		let events_html = events.map(event => {
			return `
					<div class="whats-new-event-wrapper" >
						<div class="whats-new-event row">
							<div class="whats-new-event-calendar col-md-2">
								${this.render_event_date(event)}
							</div>
							<div class="whats-new-event-body col-md-10">
								<div class="row">
									<div class="col-md-9">
										<div class="whats-new-event-tags">
											<span class="indicator-pill whitespace-nowrap upcoming">Upcoming</span>
										</div>
									</div>
									<div class= "whats-new-event-cal-link col-md-3"
										data-event_date="${event.event_date}"
										data-event_time="${event.event_time}"
										data-event_title="${event.title}"
									>
										<a> + Add to calendar </a>
									</div>
								</div>

								<div class="whats-new-event-header">
									<p class="whats-new-event-title"><b>${event.name}</b></p>
								</div>
								<div class="whats-new-event-content">
									<div class="whats-new-event-description">
										${event.description || ''}
										${this.get_source_link(event.source_link)}
									</div>
									${this.get_event_date_time(event)}
								</div>
							</div>
						</div>
					</div>
				`
		}).join('')

		return events_html;
	}

	render_fetched_posts() {
		let events_html = `
			<div class="events-container">
				${this.get_events_html(this.events)}
			</div>`;

		let posts_html =`
			<div class="events-container">
				${this.get_posts_html(this.new_posts)}
			</div>`;

		let html = this.$header + events_html + `<div class="separator"></div>` + posts_html;
		this.$container.append(html);
	}
}