import Quill from 'quill';
import Mention from './quill-mention/quill.mention';

Quill.register('modules/mention', Mention, true);

frappe.ui.form.ControlComment = frappe.ui.form.ControlTextEditor.extend({
	make_wrapper() {
		this.comment_wrapper = !this.no_wrapper ? $(`
				<div class="comment-input-wrapper">
					<div class="comment-input-header">
					<span class="small text-muted">${__("Add a comment")}</span>
					<button class="btn btn-default btn-comment btn-xs pull-right">
						${__("Comment")}
					</button>
				</div>
				<div class="comment-input-container">
					<div class="frappe-control"></div>
					<div class="text-muted small">
						${__("Ctrl+Enter to add comment")}
					</div>
				</div>
			</div>
		`) : $('<div class="frappe-control"></div>');

		this.comment_wrapper.appendTo(this.parent);

		// wrapper should point to frappe-control
		this.$wrapper = !this.no_wrapper
			? this.comment_wrapper.find('.frappe-control')
			: this.comment_wrapper;

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
		if (strip_html(value).trim() != "") {
			this.button.removeClass('btn-default').addClass('btn-primary');
		} else {
			this.button.addClass('btn-default').removeClass('btn-primary');
		}
	},

	get_quill_options() {
		const options = this._super();
		return Object.assign(options, {
			theme: 'bubble',
			modules: Object.assign(options.modules, {
				mention: this.get_mention_options()
			})
		});
	},

	get_mention_options() {
		if (!(this.mentions && this.mentions.length)) {
			return null;
		}

		const at_values = this.mentions.slice();

		return {
			allowedChars: /^[A-Za-z0-9_]*$/,
			mentionDenotationChars: ["@"],
			isolateCharacter: true,
			source: function (searchTerm, renderList, mentionChar) {
				let values;

				if (mentionChar === "@") {
					values = at_values;
				}

				if (searchTerm.length === 0) {
					renderList(values, searchTerm);
				} else {
					const matches = [];
					for (let i = 0; i < values.length; i++) {
						if (~values[i].value.toLowerCase().indexOf(searchTerm.toLowerCase())) {
							matches.push(values[i]);
						}
					}
					renderList(matches, searchTerm);
				}
			},
		};
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

	clear() {
		this.quill.setText('');
	}
});
