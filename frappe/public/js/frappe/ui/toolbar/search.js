frappe.provide("frappe.search");

frappe.search.SearchDialog = class {
	constructor(opts) {
		$.extend(this, opts);
		this.make();
	}

	make() {
		this.search_dialog = new frappe.ui.Dialog({
			minimizable: true,
			size: "large",
		});
		this.set_header();
		this.$wrapper = $(this.search_dialog.$wrapper).addClass("search-dialog");
		this.$body = $(this.search_dialog.body);
		this.$input = this.$wrapper.find(".search-input");
		this.setup();
	}

	set_header() {
		this.search_dialog.header
			.addClass("search-header")
			.find(".title-section")
			.html(
				`<div class="input-group text-muted">
					<input type="text" class="form-control search-input">
				</div>
				<span class="search-icon">
					${frappe.utils.icon("search")}
				</span>`
			);
	}

	setup() {
		this.modal_state = 0;
		this.current_keyword = "";
		this.more_count = 20;
		this.full_lists = {};
		this.nav_lists = {};
		this.init_search_objects();
		this.bind_input();
		this.bind_events();
	}

	init_search_objects() {
		this.searches = {
			global_search: {
				input_placeholder: __("Search"),
				empty_state_text: __("Search for anything"),
				no_results_status: () => __("No Results found"),
				get_results: (keywords, callback) => {
					let start = 0,
						limit = 100;
					let results = frappe.search.utils.get_nav_results(keywords);
					frappe.search.utils.get_global_results(keywords, start, limit).then(
						(global_results) => {
							results = results.concat(global_results);
							callback(results, keywords);
						},
						(err) => {
							// eslint-disable-next-line no-console
							console.error(err);
						}
					);
				},
			},
			tags: {
				input_placeholder: __("Search"),
				empty_state_text: __("Search for anything"),
				no_results_status: (keyword) =>
					"<div>" + __("No documents found tagged with {0}", [keyword]) + "</div>",
				get_results: (keywords, callback) => {
					var results = frappe.search.utils.get_nav_results(keywords);
					frappe.tags.utils.get_tag_results(keywords).then(
						(global_results) => {
							results = results.concat(global_results);
							callback(results, keywords);
						},
						(err) => {
							// eslint-disable-next-line no-console
							console.error(err);
						}
					);
				},
			},
		};
	}

	update($r) {
		this.$wrapper.find(".loading-state").addClass("hide");
		this.$body.append($r);
		if (this.$body.find(".search-results").length > 1) {
			this.$body.find(".search-results").first().addClass("hide");
			$r.removeClass("hide");
			this.$body.find(".search-results").first().remove();
		} else {
			$r.removeClass("hide");
		}
	}

	put_placeholder(status_text) {
		var $placeholder = $(`<div class="row search-results hide">
			<div class="empty-state">
				<div class="text-center">
					<img src="/assets/frappe/images/ui-states/search-empty-state.svg"
						alt="Generic Empty State"
						class="null-state"
					>
					<div class="empty-state-text">${status_text}</div>
				</div>
			</div>
		</div>`);
		this.update($placeholder);
	}

	bind_input() {
		this.$input.on("input", (e) => {
			const $el = $(e.currentTarget);
			clearTimeout($el.data("timeout"));
			$el.data(
				"timeout",
				setTimeout(() => {
					if (this.$input.val() === this.current_keyword) return;
					let keywords = this.$input.val();
					if (keywords.length > 1) {
						this.get_results(keywords);
					} else {
						this.current_keyword = "";
						this.put_placeholder(this.search.empty_state_text);
					}
				}, 300)
			);
		});
	}

	bind_events() {
		// Sidebar
		this.$body.on("click", ".list-link", (e) => {
			const $link = $(e.currentTarget);
			this.$body.find(".search-sidebar").find(".list-link").removeClass("active selected");
			$link.addClass("active selected");
			const type = $link.attr("data-category");
			this.$body.find(".results-area").empty().html(this.full_lists[type]);
			this.$body.find(".module-section-link").first().focus();
		});

		// Summary more links
		this.$body.on("click", ".section-more", (e) => {
			const $section = $(e.currentTarget);
			const type = $section.attr("data-category");
			this.$body
				.find(".search-sidebar")
				.find('*[data-category="' + type + '"]')
				.trigger("click");
		});

		// Back-links (mobile-view)
		this.$body.on("click", ".all-results-link", () => {
			this.$body
				.find(".search-sidebar")
				.find('*[data-category="All Results"]')
				.trigger("click");
		});

		// Full list more links
		this.$body.on("click", ".list-more", (e) => {
			const $el = $(e.currentTarget);
			const type = $el.attr("data-category");
			const fetch_type = $el.attr("data-search");
			var current_count = this.$body.find(".result").length;
			if (fetch_type === "Global") {
				frappe.search.utils
					.get_global_results(this.current_keyword, current_count, this.more_count, type)
					.then(
						(doctype_results) => {
							doctype_results.length && this.add_more_results(doctype_results);
						},
						(err) => {
							// eslint-disable-next-line no-console
							console.error(err);
						}
					);
			} else {
				let results = this.nav_lists[type].slice(0, this.more_count);
				this.nav_lists[type].splice(0, this.more_count);
				this.add_more_results([{ title: type, results: results }]);
			}
		});

		// Switch to global search link
		this.$body.on("click", ".switch-to-global-search", () => {
			this.search = this.searches["global_search"];
			this.$input.attr("placeholder", this.search.input_placeholder);
			this.put_placeholder(this.search.empty_state_text);
			this.get_results(this.current_keyword);
		});
	}

	init_search(keywords, search_type) {
		this.search = this.searches[search_type];
		this.$input.attr("placeholder", this.search.input_placeholder);
		this.put_placeholder(this.search.empty_state_text);
		this.get_results(keywords);
		this.search_dialog.show();
		this.$input.val(keywords);
		setTimeout(() => this.$input.select(), 500);
	}

	get_results(keywords) {
		this.current_keyword = keywords;
		if (this.$body.find(".empty-state").length > 0) {
			this.put_placeholder(__("Searching ..."));
		} else {
			this.$wrapper.find(".loading-state").removeClass("hide");
		}

		if (this.current_keyword.charAt(0) === "#") {
			this.search = this.searches["tags"];
		} else {
			this.search = this.searches["global_search"];
		}

		this.search.get_results(keywords, this.parse_results.bind(this));
	}

	parse_results(result_sets, keyword) {
		result_sets = result_sets.filter(function (set) {
			return set.results.length > 0;
		});
		if (result_sets.length > 0) {
			this.render_data(result_sets);
		} else {
			this.put_placeholder(this.search.no_results_status(keyword));
		}
	}

	render_data(result_sets) {
		let $search_results = $(frappe.render_template("search")).addClass("hide");
		let $sidebar = $search_results.find(".search-sidebar").empty();
		let sidebar_item_html =
			'<li class="search-sidebar-item standard-sidebar-item list-link" data-category="{0}">' +
			'<a><span class="ellipsis">{1}</span></a></li>';

		this.modal_state = 0;
		this.full_lists = {
			"All Results": $('<div class="results-summary"></div>'),
		};
		this.nav_lists = {};

		result_sets.forEach((set) => {
			$sidebar.append($(__(sidebar_item_html, [set.title, __(set.title)])));
			this.add_section_to_summary(set.title, set.results);
			this.full_lists[set.title] = this.render_full_list(
				set.title,
				set.results,
				set.fetch_type
			);
		});

		if (result_sets.length > 1) {
			$sidebar.prepend($(__(sidebar_item_html, ["All Results", __("All Results")])));
		}

		this.update($search_results.clone());
		this.$body.find(".list-link").first().trigger("click");
	}

	render_full_list(type, results, fetch_type) {
		let max_length = 20;

		let $results_list = $(`<div class="results-summary">
			<div class="result-section full-list ${type}-section col-sm-12">
				<div class="result-title"> ${__(type)}</div>
				<div class="result-body">
				</div>
			</div>
		</div>`);

		results.slice(0, max_length).forEach((result) => {
			$results_list.find(".result-body").append(this.render_result(type, result));
		});

		if (results.length > 0) {
			if (fetch_type === "Nav") this.nav_lists[type] = results;

			if (results.length > max_length) {
				$(`<a class="list-more" data-search="${fetch_type}"
					data-category="${type}" data-count="${max_length}">
						${__("More")}
				</a>`).appendTo($results_list.find(".result-body"));
			}
		}
		return $results_list;
	}

	add_section_to_summary(type, results) {
		let section_length = 4;
		let more_html = "";
		let get_result_html = (result) => this.render_result(type, result);

		if (results.length > section_length) {
			more_html = `<div>
				<a class="section-more" data-category="${type}">${__("More")}</a>
			</div>`;
		}

		let $result_section = $(`<div class="col-sm-12 result-section" data-type="${type}">
			<div class="result-title">${__(type)}</div>
			<div class="result-body">
				${more_html}
			</div>
		</div>`).appendTo(this.full_lists["All Results"]);

		$result_section
			.find(".result-body")
			.prepend(results.slice(0, section_length).map(get_result_html));
	}

	get_link(result) {
		let link = "";
		if (result.route) {
			link = `href="/app/${result.route.join("/")}"`;
		} else if (result.data_path) {
			link = `data-path=${result.data_path}"`;
		}
		return link;
	}

	render_result(type, result) {
		let image_html = "";
		if (result.image !== undefined) {
			let avatar_html = frappe.get_avatar("avatar-medium", result.label, result.image);
			image_html = `<a ${this.get_link(result)}>
				<div class="result-image">
					${avatar_html}
				</div>
			</a>`;
		}

		let link_html = `<a ${this.get_link(result)} class="result-section-link">${
			result.label
		}</a>`;
		let title_html = !result.description
			? link_html
			: `<b>${link_html}</b><div class="description"> ${result.description} </div>`;

		let result_text = `<div class="result-text">
			${title_html}
		</div>`;

		let $result = $(`<div class="result ${type}-result">
			${image_html}
			${result_text}
			${result.subtypes || ""}
		</div>`);

		if (!result.description) {
			this.handle_result_click(result, $result);
		}

		return $result;
	}

	handle_result_click(result, $result) {
		if (result.route_options) {
			frappe.route_options = result.route_options;
		}
		$result.on("click", () => {
			// this.toggle_minimize();
			if (result.onclick) {
				result.onclick(result.match);
			} else {
				var previous_hash = window.location.hash;
				frappe.set_route(result.route);
				// hashchange didn't fire!
				if (window.location.hash == previous_hash) {
					frappe.router.route();
				}
			}
		});
	}

	add_more_results(results_set) {
		let more_results = $('<div class="more-results last"></div>');
		if (results_set[0].results) {
			results_set[0].results.forEach((result) => {
				more_results.append(this.render_result(results_set[0].title, result));
			});
		}
		this.$body.find(".list-more").before(more_results);

		if (results_set[0].results.length < this.more_count) {
			// hide more button and add a result count
			this.$body.find(".list-more").hide();
			let no_of_results = this.$body.find(".result").length;
			let no_of_results_cue = $(
				'<div class="results-status">' + no_of_results + " results found</div>"
			);
			this.$body.find(".more-results:last").append(no_of_results_cue);
		}
		this.$body.find(".more-results.last").slideDown(200, function () {});
	}
};
