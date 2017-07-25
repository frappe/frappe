/**
 * CommentArea: A small rich text editor with
 * support for @mentions and :emojis:
 * @example
 * let comment_area = new CommentArea();
 */

frappe.ui.CommentArea = class CommentArea {

	constructor({ parent = null }) {
		this.parent = $(parent);

		this.make();
	}

	make() {
		this.make_dom();
		this.setup_summernote();
	}

	make_dom() {
		this.parent.html(`
			<div class="form-control comment-input"></div>
			<div class="text-muted small">${__("Ctrl+Enter to add comment")}</div>
		`);
	}

	setup_summernote() {
		this.input.summernote({
			height: 100,
			toolbar: false,
			hint: {
				mentions: this.get_usernames_for_mentions(),
				match: /\B@(\w*)$/,
				search: function (keyword, callback) {
					callback($.grep(this.mentions, function (item) {
						return item.indexOf(keyword) == 0;
					}));
				},
				content: function (item) {
					return '@' + item;
				}
			},
			onChange: function() {
				console.log(this);
				if(me.input.summernote('isEmpty')) {
					me.comment_button
						.removeClass('btn-primary')
						.addClass('btn-default');
				} else {
					me.comment_button
						.removeClass('btn-default')
						.addClass('btn-primary');
				}
			},
			onKeydown: function(e) {
				var key = frappe.ui.keys.get_key(e);
				if(key === 'ctrl+enter') {
					me.comment_button.trigger("click");
				}
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
	}

	val(value) {
		if(value === undefined) {
			return
		}
	}
}