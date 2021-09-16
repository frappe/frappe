export default class Column {
	constructor(section, df) {
		if (!df) df = {};

		this.df = df;
		this.section = section;
		this.make();
		this.resize_all_columns();
	}

	make() {
		this.wrapper = $(`
			<div class="form-column">
				<form>
				</form>
			</div>
		`)
			.appendTo(this.section.body)
			.find("form")
			.on("submit", function () {
				return false;
			});

		if (this.df.label) {
			$(`
				<label class="control-label">
					${__(this.df.label)}
				</label>
			`)
				.appendTo(this.wrapper);
		}
	}

	resize_all_columns() {
		// distribute all columns equally
		let colspan = cint(12 / this.section.wrapper.find(".form-column").length);

		this.section.wrapper
			.find(".form-column")
			.removeClass()
			.addClass("form-column")
			.addClass("col-sm-" + colspan);

	}

	refresh() {
		this.section.refresh();
	}
}