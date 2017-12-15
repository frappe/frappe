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
	}

	make() {
		this.setup_dom();
		this.setup_summernote();
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
					<div class="form-control comment-input"></div>
					${ footer }
				</div>
			</div>
		`);
		this.wrapper.appendTo(this.parent);
		this.input = this.parent.find('.comment-input');
		this.button = this.parent.find('.btn-comment');
	}

	setup_summernote() {
		const { input, button } = this;

		input.summernote({
			height: 100,
			toolbar: false,
			airMode: true,
			hint: {
				mentions: this.mentions,
				match: /\B([@:]\w*)/,
				search: function (keyword, callback) {
					let items = [];
					if (keyword.startsWith('@')) {
						keyword = keyword.substr(1);
						items = this.mentions;
					} else if (keyword.startsWith(':')) {
						items = frappe.ui.emoji_keywords
							.filter(k => k.startsWith(keyword))
							.slice(0, 7);
					}
					callback($.grep(items, function (item) {
						return item.indexOf(keyword) == 0;
					}));
				},
				template: function (item) {
					if (item.startsWith(':')) {
						return frappe.ui.get_emoji(item) + ' ' + item;
					} else {
						return item;
					}
				},
				content: function (item) {
					if(item.startsWith(':')) {
						return frappe.ui.get_emoji(item);
					} else {
						return '@' + item;
					}
				}
			},
			callbacks: {
				onChange: () => {
					if(input.summernote('isEmpty')) {
						button
							.removeClass('btn-primary')
							.addClass('btn-default');
					} else {
						button
							.removeClass('btn-default')
							.addClass('btn-primary');
					}
				},
				onKeydown: (e) => {
					var key = frappe.ui.keys.get_key(e);
					if(key === 'ctrl+enter') {
						e.preventDefault();
						this.submit();
					}
					e.stopPropagation();
				},
			},
			icons: {
				'align': 'fa fa-align',
				'alignCenter': 'fa fa-align-center',
				'alignJustify': 'fa fa-align-justify',
				'alignLeft': 'fa fa-align-left',
				'alignRight': 'fa fa-align-right',
				'indent': 'fa fa-indent',
				'outdent': 'fa fa-outdent',
				'arrowsAlt': 'fa fa-arrows-alt',
				'bold': 'fa fa-bold',
				'caret': 'caret',
				'circle': 'fa fa-circle',
				'close': 'fa fa-close',
				'code': 'fa fa-code',
				'eraser': 'fa fa-eraser',
				'font': 'fa fa-font',
				'frame': 'fa fa-frame',
				'italic': 'fa fa-italic',
				'link': 'fa fa-link',
				'unlink': 'fa fa-chain-broken',
				'magic': 'fa fa-magic',
				'menuCheck': 'fa fa-check',
				'minus': 'fa fa-minus',
				'orderedlist': 'fa fa-list-ol',
				'pencil': 'fa fa-pencil',
				'picture': 'fa fa-image',
				'question': 'fa fa-question',
				'redo': 'fa fa-redo',
				'square': 'fa fa-square',
				'strikethrough': 'fa fa-strikethrough',
				'subscript': 'fa fa-subscript',
				'superscript': 'fa fa-superscript',
				'table': 'fa fa-table',
				'textHeight': 'fa fa-text-height',
				'trash': 'fa fa-trash',
				'underline': 'fa fa-underline',
				'undo': 'fa fa-undo',
				'unorderedlist': 'fa fa-list-ul',
				'video': 'fa fa-video-camera'
			}
		});

		this.note_editor = this.wrapper.find('.note-editor');
		this.note_editor.css({
			'border': '1px solid #ebeff2',
			'border-radius': '3px',
			'padding': '10px',
			'margin-bottom': '10px',
			'min-height': '80px',
			'cursor': 'text'
		});
		this.note_editor.on('click', () => input.summernote('focus'));
	}

	destroy() {
		this.input.summernote('destroy');
	}

	bind_events() {
		this.button.on('click', this.submit.bind(this));
	}

	val(value) {
		// Return html if no value specified
		if(value === undefined) {
			return this.input.summernote('code');
		}
		// Set html if value is specified
		this.input.summernote('code', value);
	}

	submit() {
		// Pass comment's value (html) to submit handler
		this.on_submit && this.on_submit(this.val());
	}
};
