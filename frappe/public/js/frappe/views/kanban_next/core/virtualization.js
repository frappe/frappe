/**
 * Per-column vertical virtualizer — variable-height, measured.
 *
 * Keeps a per-index height cache (seeded with an estimate, corrected after
 * measuring) + a prefix-sum array for O(log n) offset<->index lookups, so the
 * core renders only the visible window ± overscan.
 */
export class ColumnVirtualizer {
	constructor(count, estimate = 84, overscan = 5) {
		this.estimate = estimate;
		this.overscan = overscan;
		this.heights = [];
		this.prefix = [0];
		this.setCount(count);
	}

	/** Resize the model, preserving already-measured heights. */
	setCount(count) {
		const old = this.heights;
		this.heights = new Array(count);
		for (let i = 0; i < count; i++) this.heights[i] = old[i] ?? this.estimate;
		this.rebuild();
	}

	get count() {
		return this.heights.length;
	}

	get totalHeight() {
		return this.prefix[this.prefix.length - 1] ?? 0;
	}

	/** Record a measured height. Returns true if it changed the layout. */
	measure(index, height) {
		if (index < 0 || index >= this.heights.length) return false;
		if (this.heights[index] === height) return false;
		this.heights[index] = height;
		return true;
	}

	rebuild() {
		const n = this.heights.length;
		this.prefix = new Array(n + 1);
		this.prefix[0] = 0;
		for (let i = 0; i < n; i++) this.prefix[i + 1] = this.prefix[i] + this.heights[i];
	}

	offsetOf(index) {
		return this.prefix[Math.max(0, Math.min(index, this.heights.length))] ?? 0;
	}

	/** Visible window for a given scroll position + viewport height. */
	range(scrollTop, viewport) {
		const n = this.heights.length;
		if (n === 0) return { start: 0, end: 0, padTop: 0, padBottom: 0 };

		let start = this.indexAt(scrollTop);
		let end = this.indexAt(scrollTop + viewport) + 1;
		start = Math.max(0, start - this.overscan);
		end = Math.min(n, end + this.overscan);

		return {
			start,
			end,
			padTop: this.prefix[start],
			padBottom: this.totalHeight - this.prefix[end],
		};
	}

	/** Largest index i where prefix[i] <= offset. */
	indexAt(offset) {
		let lo = 0;
		let hi = this.heights.length;
		while (lo < hi) {
			const mid = (lo + hi) >> 1;
			if (this.prefix[mid + 1] <= offset) lo = mid + 1;
			else hi = mid;
		}
		return Math.min(lo, Math.max(0, this.heights.length - 1));
	}
}
