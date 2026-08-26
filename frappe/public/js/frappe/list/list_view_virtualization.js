/** List view virtualization — lazy-loaded for lists with 2000+ rows. */
export const list_view_virtualization = {
	// List view virtualization
	//
	// Goal: keep scroll smooth when a page loads 2000+ documents.
	//
	// How it works:
	// 1. DOM window — only render rows near the scroll position (~30 nodes, not 5000).
	// 2. Spacers — empty divs above/below fake the height of rows not in the DOM.
	// 3. Measured heights — read real row height from DOM instead of guessing forever.
	// 4. Desktop vs mobile — desktop rows share one height; mobile cards vary, so we cache each.
	// 5. checked_docnames Set — bulk selection works when selected rows are off-screen.
	// 6. requestAnimationFrame — at most one re-render per frame while scrolling.
	setup_virtualization_scroll_handler() {
		const $container = this.$result.parent(".result-container");
		if (!$container.length) {
			return;
		}

		const container = $container[0];

		// Re-entering the list with the same container — just re-enable, don't bind twice.
		if (this.virtualization_state.bound && this.virtualization_state.container === container) {
			this.virtualization_state.enabled = true;
			return;
		}

		this.teardown_virtualization_scroll_handler();
		this.virtualization_state.enabled = true;
		this.virtualization_state.bound = true;
		this.virtualization_state.container = container;

		// Scroll fires many times per second. Schedule one render on the next animation frame.
		// If a frame is already scheduled (this.virtualization_state.raf), skip — avoids jank.
		this.virtualization_state.scroll_handler = () => {
			if (!this.virtualization_state.enabled) {
				return;
			}
			if (this.virtualization_state.raf) {
				return;
			}
			this.virtualization_state.raf = window.requestAnimationFrame(() => {
				this.virtualization_state.raf = null;
				this.render_virtual_rows();
			});
		};

		$container.on("scroll.virtualization", this.virtualization_state.scroll_handler);

		// Debounced — wait until resize stops before recalculating row window.
		this.virtualization_state.resize_handler = frappe.utils.debounce(() => {
			if (!this.virtualization_state.enabled) {
				return;
			}

			const is_mobile = frappe.is_mobile();
			if (this.virtualization_state.last_is_mobile !== is_mobile) {
				// Switched between desktop and mobile — row heights work differently.
				this.sync_virtualization_viewport_mode();
			} else {
				// Window resized — forget cached heights and redraw rows.
				this.virtualization_state.measured_row_height = null;
				this.virtualization_state.start = -1;
				this.virtualization_state.end = -1;
				if (is_mobile) {
					this.virtualization_state.row_heights = {};
				}
			}

			this.render_virtual_rows(true);
		}, 300);

		$(window).on("resize.list-view-virtualization", this.virtualization_state.resize_handler);

		// Clean up listeners when user navigates away — prevents leaks and stale renders.
		$(this.page.wrapper)
			.off("hide.list-view-virtualization")
			.on("hide.list-view-virtualization", () => {
				this.teardown_virtualization_scroll_handler();
			});
	},

	teardown_virtualization_scroll_handler() {
		if (this.virtualization_state.raf) {
			window.cancelAnimationFrame(this.virtualization_state.raf);
		}

		const $container = this.virtualization_state.container
			? $(this.virtualization_state.container)
			: null;
		if ($container?.length && this.virtualization_state.scroll_handler) {
			$container.off("scroll.virtualization", this.virtualization_state.scroll_handler);
		}

		if (this.virtualization_state.resize_handler) {
			$(window).off(
				"resize.list-view-virtualization",
				this.virtualization_state.resize_handler
			);
		}

		$(this.page?.wrapper).off("hide.list-view-virtualization");

		this.virtualization_state.enabled = false;
		this.virtualization_state.bound = false;
		this.virtualization_state.start = -1;
		this.virtualization_state.end = -1;
		this.virtualization_state.raf = null;
		this.virtualization_state.measured_row_height = null;
		this.virtualization_state.row_heights = {};
		this.virtualization_state.row_height_prefix_sums = [];
		this.virtualization_state.row_height_prefix_total_rows = 0;
		this.virtualization_state.last_is_mobile = null;
		this.virtualization_state.container = null;
		this.virtualization_state.scroll_handler = null;
		this.virtualization_state.resize_handler = null;
	},

	get_virtual_row_height() {
		return (
			this.virtualization_state.measured_row_height || this.get_virtual_row_height_fallback()
		);
	},

	get_virtual_row_height_fallback() {
		if (frappe.is_mobile()) {
			return this.get_mobile_unmeasured_row_height_estimate();
		}
		return this.virtualization_row_height;
	},

	/** Mobile: average measured card height for rows we have not rendered yet. */
	get_mobile_unmeasured_row_height_estimate() {
		const heights = Object.values(this.virtualization_state.row_heights);
		if (heights.length) {
			return heights.reduce((sum, height) => sum + height, 0) / heights.length;
		}
		return 72;
	},

	get_virtualization_row_buffer() {
		// Keep more rows rendered off-screen so fast scrolls are less likely to hit
		// a blank gap. Touch flings outrun the window sooner, so mobile gets more.
		return frappe.is_mobile() ? 40 : this.virtualization_row_buffer;
	},

	uses_accumulated_row_heights() {
		return frappe.is_mobile();
	},

	sync_virtualization_viewport_mode() {
		const is_mobile = frappe.is_mobile();
		if (this.virtualization_state.last_is_mobile === is_mobile) {
			return;
		}

		this.virtualization_state.last_is_mobile = is_mobile;
		this.reset_virtual_row_height_cache();
	},

	reset_virtual_row_height_cache() {
		// Reset all derived height state so the next render recomputes with current viewport mode.
		this.virtualization_state.row_heights = {};
		this.virtualization_state.measured_row_height = null;
		this.invalidate_virtual_row_height_prefix_sums();
		this.virtualization_state.start = -1;
		this.virtualization_state.end = -1;
	},

	invalidate_virtual_row_height_prefix_sums() {
		this.virtualization_state.row_height_prefix_sums = [];
		this.virtualization_state.row_height_prefix_total_rows = 0;
	},

	ensure_virtual_row_height_prefix_sums(total_rows) {
		if (!this.uses_accumulated_row_heights()) {
			return;
		}

		const { row_height_prefix_sums, row_height_prefix_total_rows } = this.virtualization_state;
		if (
			row_height_prefix_sums.length === total_rows + 1 &&
			row_height_prefix_total_rows === total_rows
		) {
			return;
		}

		const prefix_sums = new Array(total_rows + 1);
		prefix_sums[0] = 0;
		for (let i = 0; i < total_rows; i++) {
			prefix_sums[i + 1] = prefix_sums[i] + this.get_estimated_row_height(i);
		}

		this.virtualization_state.row_height_prefix_sums = prefix_sums;
		this.virtualization_state.row_height_prefix_total_rows = total_rows;
	},

	get_virtual_prefix_sum(index) {
		const clamped_index = Math.max(0, Math.min(index, this.data.length));
		if (!this.uses_accumulated_row_heights()) {
			return clamped_index * this.get_virtual_row_height();
		}

		this.ensure_virtual_row_height_prefix_sums(this.data.length);
		return this.virtualization_state.row_height_prefix_sums[clamped_index] || 0;
	},

	get_virtual_spacer_height(from, to) {
		if (!this.uses_accumulated_row_heights()) {
			// Desktop: row count × single measured height.
			return (to - from) * this.get_virtual_row_height();
		}

		// Mobile: O(1) range sum over cached prefix totals.
		return this.get_virtual_prefix_sum(to) - this.get_virtual_prefix_sum(from);
	},

	get_estimated_row_height(index) {
		// Use cached height if we've rendered this row before; otherwise use the mobile/desktop guess.
		return (
			this.virtualization_state.row_heights[index] || this.get_virtual_row_height_fallback()
		);
	},

	find_virtual_start_index(scroll_top, row_buffer, total_rows) {
		if (!this.uses_accumulated_row_heights()) {
			const row_height = this.get_virtual_row_height();
			// Subtract buffer so we render a few rows above the viewport (no blank flash on fast scroll).
			return Math.max(0, Math.floor(scroll_top / row_height) - row_buffer);
		}

		if (scroll_top <= 0) {
			return 0;
		}

		// Binary search over prefix sums: find the last row whose top is within scroll_top.
		this.ensure_virtual_row_height_prefix_sums(total_rows);
		let low = 0;
		let high = total_rows - 1;
		let result = 0;

		while (low <= high) {
			const mid = Math.floor((low + high) / 2);
			if (this.get_virtual_prefix_sum(mid) <= scroll_top) {
				result = mid;
				low = mid + 1;
			} else {
				high = mid - 1;
			}
		}

		return Math.max(0, result - row_buffer);
	},

	/** Mobile: find how many rows from start fill the viewport plus bottom buffer. */
	find_virtual_end_index(start, viewport_height, row_buffer, total_rows) {
		if (!this.uses_accumulated_row_heights()) {
			const row_height = this.get_virtual_row_height();
			const visible_rows = Math.ceil(viewport_height / row_height) + row_buffer * 2;
			return Math.min(total_rows, start + visible_rows);
		}

		this.ensure_virtual_row_height_prefix_sums(total_rows);
		// Bottom buffer uses the same prefix sums as spacers, not a max-height guess.
		const buffer_end = Math.min(total_rows, start + row_buffer);
		const buffer_height =
			this.get_virtual_prefix_sum(buffer_end) - this.get_virtual_prefix_sum(start);
		const target_offset = this.get_virtual_prefix_sum(start) + viewport_height + buffer_height;

		let low = start + 1;
		let high = total_rows;
		let end = total_rows;

		while (low <= high) {
			const mid = Math.floor((low + high) / 2);
			if (this.get_virtual_prefix_sum(mid) >= target_offset) {
				end = mid;
				high = mid - 1;
			} else {
				low = mid + 1;
			}
		}

		return Math.max(start + 1, end);
	},

	finalize_virtual_rows() {
		if (!frappe.is_mobile()) {
			this.apply_column_widths();
		}
		this.set_rows_as_checked();
	},

	measure_virtual_row_height(start) {
		const $rows = this.$result.find('.list-row-container[data-virtual-row="1"]');
		if (!$rows.length) {
			return false;
		}

		let max_height = 0;
		let row_height_changed = false;
		$rows.each((i, el) => {
			const height = el.offsetHeight;
			if (!height) {
				return;
			}

			max_height = Math.max(max_height, height);
			// Save height by row index — mobile uses this for spacer math; desktop uses the max only.
			if (start !== undefined) {
				const row_index = start + i;
				if (this.virtualization_state.row_heights[row_index] !== height) {
					this.virtualization_state.row_heights[row_index] = height;
					row_height_changed = true;
				}
			}
		});

		if (row_height_changed) {
			// Measured heights drive prefix sums; drop cache so next range/index read is correct.
			this.invalidate_virtual_row_height_prefix_sums();
		}

		if (!max_height) {
			return false;
		}

		const prev = this.virtualization_state.measured_row_height;
		this.virtualization_state.measured_row_height = max_height;

		// Mobile cards vary in height — any per-row change invalidates start index and spacers.
		if (row_height_changed && this.uses_accumulated_row_heights()) {
			return true;
		}

		// First pass used a guess (44/72px). If real height differs, caller re-renders spacers once.
		const fallback = this.get_virtual_row_height_fallback();
		if (prev === null) {
			return Math.abs(fallback - max_height) > 1;
		}

		return Math.abs(prev - max_height) > 1;
	},

	render_virtual_rows(force = false, remeasure_attempt = 0) {
		if (!this.virtualization_state.enabled) {
			return;
		}

		const $container = this.$result.parent(".result-container");
		if (!$container.length) {
			return;
		}

		const total_rows = this.data.length;
		if (!total_rows) {
			$container.find(".list-virtual-spacer").remove();
			this.$result.find('.list-row-container[data-virtual-row="1"]').remove();
			return;
		}

		// Step 1: compute visible window from scroll position
		const row_buffer = this.get_virtualization_row_buffer();
		const scroll_top = $container.scrollTop() || 0;
		// clamped: an auto-height container reports its own content (spacers
		// included) as innerHeight, which would inflate the row window until
		// the whole list is in the DOM
		const viewport_height = Math.min($container.innerHeight() || 0, window.innerHeight);
		const start = this.find_virtual_start_index(scroll_top, row_buffer, total_rows);
		const end = this.find_virtual_end_index(start, viewport_height, row_buffer, total_rows);

		// Step 2: nothing to do if user scrolled inside the same window
		if (
			!force &&
			start === this.virtualization_state.start &&
			end === this.virtualization_state.end
		) {
			return;
		}

		this.virtualization_state.start = start;
		this.virtualization_state.end = end;

		// Step 3: tear down previous window
		$container.find(".list-virtual-spacer").remove();
		this.$result.find('.list-row-container[data-virtual-row="1"]').remove();

		// Steps 4–6: spacers + rows + spacers, built as one string and
		// inserted once — this runs on every window shift while scrolling
		const top_spacer_height = this.get_virtual_spacer_height(0, start);
		const bottom_spacer_height = this.get_virtual_spacer_height(end, total_rows);

		let window_html = "";
		if (top_spacer_height > 0) {
			window_html += `<div class="list-virtual-spacer" style="height:${top_spacer_height}px"></div>`;
		}
		for (let i = start; i < end; i++) {
			const doc = this.data[i];
			doc._idx = i;
			window_html += this.get_list_row_html(doc, { virtual: true });
		}
		if (bottom_spacer_height > 0) {
			window_html += `<div class="list-virtual-spacer" style="height:${bottom_spacer_height}px"></div>`;
		}
		this.$result.append(window_html);

		if (!frappe.is_mobile()) {
			this.apply_column_widths();
		}

		// Step 7: measure; retry once if spacers were sized with stale height estimates.
		if (this.measure_virtual_row_height(start) && remeasure_attempt < 2) {
			this.virtualization_state.start = -1;
			this.virtualization_state.end = -1;
			this.render_virtual_rows(true, remeasure_attempt + 1);
			return;
		}

		// Step 8: column widths + bulk checkbox state for visible rows
		this.finalize_virtual_rows();
	},
};
