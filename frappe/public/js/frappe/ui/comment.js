/**
 * CommentArea: A small rich text editor with
 * support for @mentions and :emojis:
 * @example
 * let comment_area = new frappe.ui.CommentArea({
 *     parent: '.comment-area',
 *     mentions: ['john', 'mary', 'kate'],
 *     on_submit: (value) => save_to_database(value)
 * });
 */

frappe.ui.CommentArea = class CommentArea {

	constructor({ parent = null, mentions = [], on_submit = null, no_wrapper = false }) {
		this.parent = $(parent);
		this.mentions = mentions;
		this.on_submit = on_submit;
		this.no_wrapper = no_wrapper;

		this.make();

		// Load emojis initially from https://git.io/frappe-emoji
		frappe.chat.emoji();
		// All good.
	}

	make() {
		this.setup_dom();
		this.setup_editor();
		this.bind_events();
	}

	setup_dom() {
		const header = !this.no_wrapper ?
			`<div class="comment-input-header">
				<span class="small text-muted">${__("Add a comment")}</span>
				<button class="btn btn-default btn-comment btn-xs pull-right">
					${__("Comment")}
				</button>
			</div>` : '';

		const footer = !this.no_wrapper ?
			`<div class="text-muted small">
				${__("Ctrl+Enter to add comment")}
			</div>` : '';

		this.wrapper = $(`
			<div class="comment-input-wrapper">
				${ header }
				<div class="comment-input-container">
					<div class="comment-input"></div>
					${ footer }
				</div>
			</div>
		`);
		this.wrapper.appendTo(this.parent);
		this.input = this.parent.find('.comment-input');
		this.button = this.parent.find('.btn-comment');
	}

	setup_editor() {
		this.editor = frappe.ui.form.make_control({
			parent: this.input,
			df: {
				fieldtype: 'TextEditor',
				fieldname: 'editor',
				change: () => {
					console.log('change');
					this.set_state();
				},
			},
			render_input: true,
			only_input: true
		});
	}

	input_has_value() {
		const val = this.editor.get_value();

		if (val && val === '<p>&nbsp;</p>') return false;
		return val;
	}

	set_state() {
		if(this.input_has_value()) {
			this.button
				.removeClass('btn-default')
				.addClass('btn-primary');
		} else {
			this.button
				.removeClass('btn-primary')
				.addClass('btn-default');
		}
	}

	destroy() {

	}

	bind_events() {
		this.button.on('click', this.submit.bind(this));
	}

	val(value) {
		// Return html if no value specified
		if(value === undefined) {
			return this.editor.get_value();
		}
		// Set html if value is specified
		this.editor.set_value(value);
	}

	submit() {
		// Pass comment's value (html) to submit handler
		this.on_submit && this.on_submit(this.val());
	}
};

frappe.ui.ReviewArea = class ReviewArea extends frappe.ui.CommentArea {
	setup_dom() {
		const header = !this.no_wrapper ?
			`<div class="comment-input-header">
				<span class="text-muted">${__("Add your review")}</span>
				<button class="btn btn-default btn-comment btn-xs disabled pull-right">
					${__("Submit Review")}
				</button>
			</div>` : '';

		const footer = !this.no_wrapper ?
			`<div class="text-muted">
				${__("Ctrl+Enter to submit")}
			</div>` : '';

		const rating_area = !this.no_wrapper ?
			`<div class="rating-area text-muted">
				${ __("Your rating: ") }
				<i class='fa fa-fw fa-star-o star-icon' data-index=0></i>
				<i class='fa fa-fw fa-star-o star-icon' data-index=1></i>
				<i class='fa fa-fw fa-star-o star-icon' data-index=2></i>
				<i class='fa fa-fw fa-star-o star-icon' data-index=3></i>
				<i class='fa fa-fw fa-star-o star-icon' data-index=4></i>
			</div>` : '';

		this.wrapper = $(`
			<div class="comment-input-wrapper">
				${ header }
				<div class="comment-input-container">
					${ rating_area }
					<div class="comment-input-body margin-top">
						<input class="form-control review-subject" type="text"
							placeholder="${__('Subject')}"
							style="border-radius: 3px; border-color: #ebeff2">
						</input>
						<div class="form-control comment-input"></div>
						${ footer }
					</div>
				</div>
			</div>
		`);
		this.wrapper.appendTo(this.parent);
		this.input = this.parent.find('.comment-input');
		this.subject = this.parent.find('.review-subject');
		this.button = this.parent.find('.btn-comment');
		this.ratingArea = this.parent.find('.rating-area');

		this.rating = 0;
	}

	input_has_value() {
		return !(this.input.summernote('isEmpty') ||
			this.rating === 0 || !this.subject.val().length);
	}

	set_state() {
		if (this.rating === 0) {
			this.parent.find('.comment-input-body').hide();
		} else {
			this.parent.find('.comment-input-body').show();
		}

		if(this.input_has_value()) {
			this.button
				.removeClass('btn-default disabled')
				.addClass('btn-primary');
		} else {
			this.button
				.removeClass('btn-primary')
				.addClass('btn-default disabled');
		}
	}

	reset() {
		this.set_rating(0);
		this.subject.val('');
		this.input.summernote('code', '');
	}

	bind_events() {
		super.bind_events();
		this.ratingArea.on('click', '.star-icon', (e) => {
			let index = $(e.target).attr('data-index');
			this.set_rating(parseInt(index) + 1);
		})

		this.subject.on('change', () => {
			this.set_state();
		});

		this.set_state();
	}

	set_rating(rating) {
		this.ratingArea.find('.star-icon').each((i, icon) => {
			let star = $(icon);
			if(i < rating) {
				star.removeClass('fa-star-o');
				star.addClass('fa-star');
			} else {
				star.removeClass('fa-star');
				star.addClass('fa-star-o');
			}
		})

		this.rating = rating;
		this.set_state();
	}

	val(value) {
		if(value === undefined) {
			return {
				rating: this.rating,
				subject: this.subject.val(),
				content: this.input.summernote('code')
			}
		}
		// Set html if value is specified
		this.input.summernote('code', value);
	}
}
