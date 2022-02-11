frappe.pages['whats-new-page'].on_page_load = function(wrapper) {
	var page = frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Whats New',
		single_column: true
	});
	new WhatsNew(page);
}

const host = "http://test-st.frappe.cloud";
class WhatsNew {
	constructor(page) {

		this.page = page;
		this.make_container();
		this.fetch_posts()
			.then(() => this.render_fetched_posts())

	}

	make_container() {
		this.$container = $(`<div class="main-wrapper frappe-card"></div>`)
			.appendTo(this.page.body);
	}


	fetch_posts() {
		return frappe.call('frappe.desk.page.whats_new_page.whats_new_page.get_whats_new_posts')
			.then(r => {
				this.new_posts = r.message;
			});
	}

	get_tags(tag_list) {
		let tag_color_map = {
			'Upcoming': 'blue',
			'Design': 'purple',
			'Enhancement': 'yellow',
			'Version Update': 'green'
		};


			let tags_html = tag_list.map(t => {
				if (t.tag &&  t.tag != null) {
					return `<span class="indicator-pill whitespace-nowrap ${tag_color_map[t.tag]}">${t.tag}</span>`
			} else {
				return ``
			}
		}).join('');

		console.log(tags_html)
		return tags_html;

	}

	get_post_media(post) {

		if (post.banner && post.banner != null) {
			const src = encodeURI(host + post.banner);
			return (`<img class='whats-new-post-media' src=${src} />`)
		} else {
			return ''
		}
	}

	get_day_and_date(posting_date) {
		const month_list = {
			0 : 'January',
			1 : 'February',
			2 : 'March',
			3 : 'April',
			4 : 'May',
			5 : 'June',
			6 : 'July',
			7 : 'August',
			8 : 'September',
			9 : 'October',
			10 : 'November',
			11 : 'December'
		}
		const [year, month, day] = posting_date.split("-");
		const formatted_date = new Date(year, month - 1, day);
		var final_date = '';

		[ month_list[formatted_date.getMonth()], formatted_date.getDate() + ',', formatted_date.getFullYear()].map(d => {
			final_date += d.toString() + ' ';
		});
		return final_date

	}

	render_fetched_posts() {
		const main_url = 'http://test-st.frappe.cloud';
		let html = this.new_posts.map(post => {
			const src = encodeURI(host + post.banner);
			console.log(post.tags);
			return `
				<div class="whats-new-post-wrapper">
					<div class="whats-new-post">
						<div class="whats-new-post-header row">
							<div class="whats-new-post-title col-md-9 col-sm-12">
								<h4 class="whats-new-post-title"><b>${post.name}</b></h4>
							</div>
							<div class="release-date-col col-md-3 col-sm-12">
								<p class="whats-new-post-date">${this.get_day_and_date(post.posting_date) || ''}</p>
							</div>
						</div>
						<div class="whats-new-post-tags">${this.get_tags(post.tags)}</div>
						<div class="whats-new-post-content">
							<div class="whats-new-post-description">${post.description || ''}</div>
							<div class="whats-new-post-media-wrapper">
								${this.get_post_media(post) || ''}
							</div>
							<div class=""></div>
						</div>
					</div>
				</div>
				<hr>
			`
			}).join('');
		this.$container.append(html);
	}

}