frappe.pages["leaderboard"].on_page_load = function (wrapper) {
	frappe.leaderboard = new frappe.Leaderboard(wrapper);
};

frappe.Leaderboard = Class.extend({

	init: function (parent) {
		frappe.ui.make_app_page({
			parent: parent,
			title: "Leaderboard",
			single_column: false
		});
		this.parent = parent;
		this.page = this.parent.page;
		this.page.sidebar.html(`<ul class="module-sidebar-nav overlay-sidebar nav nav-pills nav-stacked"></ul>`);
		this.$sidebar_list = this.page.sidebar.find('ul');

		this.get_leaderboard_config();

	},

	get_leaderboard_config: function() {
		this.doctypes = [];
		this.filters = {};
		frappe.xcall('frappe.desk.page.leaderboard.leaderboard.get_leaderboard_config').then( config => {
			this.leaderboard_config = config;
			for (doctype in this.leaderboard_config) {
				this.doctypes.push(doctype);
				this.filters[doctype] = this.leaderboard_config[doctype].fields;
			}
			this.timespans = ["Week", "Month", "Quarter", "Year", "All Time"];

			// for saving current selected filters
			const _initial_doctype = frappe.get_route()[1] || this.doctypes[0];
			const _initial_timespan = this.timespans[0];
			const _initial_filter = this.filters[_initial_doctype];

			this.options = {
				selected_doctype: _initial_doctype,
				selected_filter: _initial_filter,
				selected_filter_item: _initial_filter[0],
				selected_timespan: _initial_timespan,
			};

			this.message = null;
			this.make();
		});
	},

	make: function () {

		this.$container = $(`<div class="leaderboard page-main-content">
			<div class="leaderboard-graph"></div>
			<div class="leaderboard-list"></div>
		</div>`).appendTo(this.page.main);

		this.$graph_area = this.$container.find(".leaderboard-graph");

		this.doctypes.map(doctype => {
			this.get_sidebar_item(doctype).appendTo(this.$sidebar_list);
		});

		this.setup_leaderboard_fields();

		this.render_selected_doctype();

		this.render_search_box();

		// now get leaderboard
		$(this.parent).bind('show', ()=> {
		//Get which leaderboard to show
			let doctype = frappe.get_route()[1];
			this.show_leaderboard(doctype);
		});

	},

	setup_leaderboard_fields() {
		this.company_select = this.page.add_field({
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_default("company"),
			reqd: 1,
			change: (e) => {
				this.options.selected_company = e.currentTarget.value;
				this.make_request();
			}
		});
		this.timespan_select = this.page.add_select(__("Timespan"),
			this.timespans.map(d => {
				return {"label": __(d), value: d };
			})
		);

		this.type_select = this.page.add_select(__("Type"),
			this.options.selected_filter.map(d => {
				return {"label": __(frappe.model.unscrub(d)), value: d };
			})
		);

		this.timespan_select.on("change", (e) => {
			this.options.selected_timespan = e.currentTarget.value;
			this.make_request();
		});

		this.type_select.on("change", (e) => {
			this.options.selected_filter_item = e.currentTarget.value;
			this.make_request();
		});
	},

	render_selected_doctype() {

		this.$sidebar_list.on("click", "li", (e)=> {
			let $li = $(e.currentTarget);
			let doctype = $li.find("span").attr("doctype-value");

			this.options.selected_company = frappe.defaults.get_default("company");
			this.options.selected_doctype = doctype;
			this.options.selected_filter = this.filters[doctype];
			this.options.selected_filter_item = this.filters[doctype][0];

			this.type_select.empty().add_options(
				this.options.selected_filter.map(d => {
					return {"label": __(frappe.model.unscrub(d)), value: d };
				})
			);

			if (this.options.selected_doctype === "Energy Point Log") {
				$(this.parent).find("[data-original-title=Company]").hide();
			} else {
				$(this.parent).find("[data-original-title=Company]").show();
			}

			this.$sidebar_list.find("li").removeClass("active");
			$li.addClass("active");

			frappe.set_route("leaderboard", this.options.selected_doctype);
			this.make_request();
		});
	},

	render_search_box() {

		this.$search_box =
			$(`<div class="leaderboard-search col-md-3">
				<input type="text" placeholder="Search" class="form-control leaderboard-search-input input-sm">
			</div>`);

		$(this.parent).find(".page-form").append(this.$search_box);
	},

	setup_search(list_items) {
		let $search_input = this.$search_box.find(".leaderboard-search-input");

		this.$search_box.on("keyup", ()=> {
			let text_filter = $search_input.val().toLowerCase();
			text_filter = text_filter.replace(/^\s+|\s+$/g, '');
			for (var i = 0; i < list_items.length; i++) {
				let text = list_items.eq(i).find(".list-id").text().trim().toLowerCase();

				if (text.includes(text_filter)) {
					list_items.eq(i).css("display", "");
				} else {
					list_items.eq(i).css("display", "none");
				}
			}
		});
	},

	show_leaderboard(doctype) {

		if (this.doctypes.includes(doctype)) {
			this.options.selected_doctype = doctype;
			this.$sidebar_list.find(`[doctype-value = "${this.options.selected_doctype}"]`).trigger("click");
		}

		this.$search_box.find(".leaderboard-search-input").val("");
		frappe.set_route("leaderboard", this.options.selected_doctype);
	},

	make_request: function () {

		frappe.model.with_doctype(this.options.selected_doctype, ()=> {
			this.get_leaderboard(this.get_leaderboard_data);
		});
	},

	get_leaderboard: function (notify) {
		if (!this.options.selected_company) {
			frappe.throw(__("Please select Company"));
		}

		frappe.call({
			method: "frappe.desk.page.leaderboard.leaderboard.get_leaderboards",
			args: {
				leaderboard_config: this.leaderboard_config,
				doctype: this.options.selected_doctype,
				timespan: this.options.selected_timespan,
				company: this.options.selected_company,
				field: this.options.selected_filter_item,
			},
			callback: (r) => {
				let results = r.message || [];

				let graph_items = results.slice(0, 10);

				this.$graph_area.show().empty();
				let args = {
					data: {
						datasets: [
							{
								values: graph_items.map(d => d.value)
							}
						],
						labels: graph_items.map(d => d.name)
					},
					colors: ["light-green"],
					format_tooltip_x: d => d[this.options.selected_filter_item],
					type: "bar",
					height: 140
				};
				new frappe.Chart(".leaderboard-graph", args);

				notify(this, r);
			}
		});
	},

	get_leaderboard_data: function (me, res) {
		if (res && res.message.length) {
			me.message = null;
			me.$container.find(".leaderboard-list").html(me.render_list_view(res.message));
			me.setup_search($(me.parent).find('.list-item-container'));
		} else {
			me.$graph_area.hide();
			me.message = __("No items found.");
			me.$container.find(".leaderboard-list").html(me.render_list_view());
		}
	},

	render_list_view: function (items = []) {

		var html =
			`${this.render_message()}
			<div class="result" style="${this.message ? "display: none;" : ""}">
				${this.render_result(items)}
			</div>`;

		return $(html);
	},

	render_result: function (items) {

		var html =
			`${this.render_list_header()}
			${this.render_list_result(items)}`;
		return html;
	},

	render_list_header: function () {
		const _selected_filter = this.options.selected_filter
			.map(i => frappe.model.unscrub(i));
		const fields = ["rank", "name", this.options.selected_filter_item];
		const filters = fields.map(filter => {
			const col = frappe.model.unscrub(filter);
			return (
				`<div class="leaderboard-item list-item_content ellipsis text-muted list-item__content--flex-2
					header-btn-base ${filter}
					${(col && _selected_filter.indexOf(col) !== -1) ? "text-right" : ""}">
					<span class="list-col-title ellipsis">
						${col}
					</span>
				</div>`
			);
		}).join("");

		const html =
			`<div class="list-headers">
				<div class="list-item list-item--head" data-list-renderer="List">${filters}</div>
			</div>`;
		return html;
	},

	render_list_result: function (items) {

		let _html = items.map((item, index) => {
			const $value = $(this.get_item_html(item, index+1));
			const $item_container = $(`<div class="list-item-container">`).append($value);
			return $item_container[0].outerHTML;
		}).join("");

		let html =
			`<div class="result-list">
				<div class="list-items">
					${_html}
				</div>
			</div>`;

		return html;
	},

	render_message: function () {

		let html =
			`<div class="no-result text-center" style="${this.message ? "" : "display: none;"}">
				<div class="msg-box no-border">
					<p>No Item found</p>
				</div>
			</div>`;

		return html;
	},

	get_item_html: function (item, index) {
		const company = this.options.selected_company;
		const currency = frappe.get_doc(":Company", company).default_currency;
		const fields = ["rank", "name", "value"];

		const html =
			`<div class="list-item">
			${
			fields.map(col => {
				let val = col === "rank"? index: item[col];
				let link = this.options.selected_doctype === "Energy Point Log"
					? `#user-profile/${item["name"]}`
					: `#Form/${this.options.selected_doctype}/${item["name"]}`;
				if (col == "name") {
					val = this.options.selected_doctype === "Energy Point Log"
					? frappe.user.full_name(val)
					: val;
					var formatted_value = `<a class="grey list-id ellipsis"
						href="${link}"> ${val} </a>`
				} else {
					var value = this.options.selected_doctype !== "Energy Point Log" &&
						this.options.selected_filter_item.indexOf("qty") == -1 &&
						col !== "rank"
						?  format_currency(val, currency)
						: val;
					var formatted_value = `<span class="text-muted ellipsis">${value}</span>`;
				}

				return (
					`<div class="list-item_content ellipsis list-item__content--flex-2 ${col}
						${(col == "value") ? "text-right" : ""}">
						${formatted_value}
					</div>`);
			}).join("")
			}
			</div>`;

		return html;
	},

	get_sidebar_item: function(item) {
		return $(`<li class="strong module-sidebar-item">
			<a class="module-link">
			<span doctype-value="${item}">${ __(item) }</span></a>
		</li>`);
	}
});
