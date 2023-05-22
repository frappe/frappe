export default class GridPagination {
	constructor(opts) {
		$.extend(this, opts);
		this.setup_pagination();
	}

	setup_pagination() {
		this.page_length = 50;
		this.page_index = 1;
		this.total_pages = Math.ceil(this.grid.data.length / this.page_length);

		this.render_pagination();
	}

	render_pagination() {
		if (this.grid.data.length <= this.page_length) {
			this.wrapper.find(".grid-pagination").html("");
		} else {
			let $pagination_template = this.get_pagination_html();
			this.wrapper.find(".grid-pagination").html($pagination_template);
			this.prev_page_button = this.wrapper.find(".prev-page");
			this.next_page_button = this.wrapper.find(".next-page");
			this.$page_number = this.wrapper.find(".current-page-number");
			this.$total_pages = this.wrapper.find(".total-page-number");
			this.first_page_button = this.wrapper.find(".first-page");
			this.last_page_button = this.wrapper.find(".last-page");

			this.bind_pagination_events();
		}
	}

	bind_pagination_events() {
		this.prev_page_button.on("click", () => {
			this.render_prev_page();
		});

		this.next_page_button.on("click", () => {
			this.render_next_page();
		});

		this.first_page_button.on("click", () => {
			this.go_to_page(1);
		});

		this.last_page_button.on("click", () => {
			this.go_to_page(this.total_pages);
		});

		this.$page_number.on("keyup", (e) => {
			e.currentTarget.style.width = (e.currentTarget.value.length + 1) * 8 + "px";
		});

		this.$page_number.on("keydown", (e) => {
			e = e ? e : window.event;
			var charCode = e.which ? e.which : e.keyCode;
			let arrow = { up: 38, down: 40 };

			switch (charCode) {
				case arrow.up:
					this.inc_dec_number(true);
					break;
				case arrow.down:
					this.inc_dec_number(false);
					break;
			}

			// only allow numbers from 0-9 and up, down, left, right arrow keys
			if (
				charCode > 31 &&
				(charCode < 48 || charCode > 57) &&
				![37, 38, 39, 40].includes(charCode)
			) {
				return false;
			}
			return true;
		});

		this.$page_number.on("focusout", (e) => {
			if (this.page_index == e.currentTarget.value) return;
			this.page_index = e.currentTarget.value;

			if (this.page_index < 1) {
				this.page_index = 1;
			} else if (this.page_index > this.total_pages) {
				this.page_index = this.total_pages;
			}

			this.go_to_page();
		});
	}

	inc_dec_number(increment) {
		let new_value = parseInt(this.$page_number.val());
		increment ? new_value++ : new_value--;

		if (new_value < 1 || new_value > this.total_pages) return;

		this.$page_number.val(new_value);
	}

	update_page_numbers() {
		let total_pages = Math.ceil(this.grid.data.length / this.page_length);
		if (this.total_pages !== total_pages) {
			this.total_pages = total_pages;
			this.render_pagination();
		}
	}

	check_page_number() {
		if (this.page_index > this.total_pages && this.page_index > 1) {
			this.go_to_page(this.page_index - 1);
		}
	}

	get_pagination_html() {
		let page_text_html = `<div class="page-text">
				<input class="current-page-number page-number" type="text" value="${__(this.page_index)}"/>
				<span>${__("of")}</span>
				<span class="total-page-number page-number"> ${__(this.total_pages)} </span>
			</div>`;

		return $(`<button class="btn btn-secondary btn-xs first-page"">
				<span>${__("First")}</span>
			</button>
			<button class="btn btn-secondary btn-xs prev-page">${frappe.utils.icon("left", "xs")}</button>
			${page_text_html}
			<button class="btn btn-secondary btn-xs next-page">${frappe.utils.icon("right", "xs")}</button>
			<button class="btn btn-secondary btn-xs last-page">
				<span>${__("Last")}</span>
			</button>`);
	}

	render_next_page() {
		if (this.page_index * this.page_length < this.grid.data.length) {
			this.page_index++;
			this.go_to_page();
		}
	}

	render_prev_page() {
		if (this.page_index > 1) {
			this.page_index--;
			this.go_to_page();
		}
	}

	go_to_page(index, from_refresh) {
		if (!index) {
			index = this.page_index;
		} else {
			this.page_index = index;
		}
		let $rows = $(this.grid.parent).find(".rows").empty();
		this.grid.render_result_rows($rows, true);
		if (this.$page_number) {
			this.$page_number.val(index);
			this.$page_number.css("width", (index.toString().length + 1) * 8 + "px");
		}

		this.update_page_numbers();
		if (!from_refresh) {
			this.grid.scroll_to_top();
		}
	}

	go_to_last_page_to_add_row() {
		let total_pages = this.total_pages;
		let page_length = this.page_length;
		if (this.grid.data.length == page_length * total_pages) {
			this.go_to_page(total_pages + 1);
			frappe.utils.scroll_to(this.wrapper);
		} else if (this.page_index == this.total_pages) {
			return;
		} else {
			this.go_to_page(total_pages);
		}
	}

	get_result_length() {
		return this.grid.data.length < this.page_index * this.page_length
			? this.grid.data.length
			: this.page_index * this.page_length;
	}
}
