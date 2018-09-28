frappe.ui.form.ControlComment = frappe.ui.form.ControlTextEditor.extend({
    make_wrapper() {
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

		this.comment_wrapper = $(`
			<div class="comment-input-wrapper">
				${ header }
				<div class="comment-input-container">
					<div class="frappe-control"></div>
					${ footer }
				</div>
			</div>
		`);
        this.comment_wrapper.appendTo(this.parent);

        // wrapper should point to frappe-control
        this.$wrapper = this.comment_wrapper.find('.frappe-control');
        this.wrapper = this.$wrapper;

        this.button = this.comment_wrapper.find('.btn-comment');
    },

    bind_events() {
        this._super();

        this.button.click(() => {
            this.submit();
        });

        this.$wrapper.on('keydown', e => {
            const key = frappe.ui.keys.get_key(e);
            if (key === 'ctrl+enter') {
                e.preventDefault();
                this.submit();
            }
        });

        this.quill.on('text-change', frappe.utils.debounce(() => {
            this.update_state();
        }, 300));
    },

    submit() {
        this.on_submit && this.on_submit(this.get_value());
    },

    update_state() {
        const value = this.get_value();
        if (strip_html(value)) {
            this.button.removeClass('btn-default').addClass('btn-primary');
        } else {
            this.button.addClass('btn-default').removeClass('btn-primary');
        }
    },

    get_quill_options() {
        const options = this._super();
        options.theme = 'bubble';
		return options;
    },

    get_toolbar_options() {
		return [
			['bold', 'italic', 'underline'],
			['blockquote', 'code-block'],
			['link', 'image'],
			[{ 'list': 'ordered' }, { 'list': 'bullet' }],
			['clean']
		];
	},
})