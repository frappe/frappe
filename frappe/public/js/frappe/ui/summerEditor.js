// setting default summernote codemirror configurations
$.summernote.options.codemirror = {
	lineNumbers: true,
	lineWrapping: true,
	smartIndent: true,
	foldGutter: true,
	indentWithTabs: true,
	indentUnit: 4,
	extraKeys: { 
		// code folding shortcut
		"Ctrl-Q": function(cm) {
			cm.foldCode(cm.getCursor());
		}
	},
	matchTags: { bothTags: true },
	gutters: ["CodeMirror-linenumbers", "CodeMirror-foldgutter"],
	mode: 'text/html',
	theme: 'monokai'
};

summerEditor = Class.extend({
	init: function(options) {
		this.keyMap = {};
		this.options = $.extend({}, this.default_options, options || {});
		if(this.options.editor) {
                        this.setup_editor(this.options.editor);
                } else if(this.options.parent) {
                        this.wrapper = $("<div></div>").appendTo(this.options.parent);
                        this.setup_editor(this.wrapper);
                }
        },
	setup_editor: function($wrapper) {
		$wrapper.summernote({
			height: 400,
			prettifyHtml: false,
			// manually setting toolbar buttons so we may add more in the future
			toolbar: [
				['style', ['style']],
				['font', ['bold', 'underline', 'clear']],
				['fontname', ['fontname']],
				['color', ['color']],
				['para', ['ul', 'ol', 'paragraph']],
				['table', ['table']],
				['insert', ['link', 'picture', 'video']],
				['view', ['fullscreen', 'codeview', 'help']],
			],
			callbacks: {
				onKeydown: this._keymap_handler.bind(this),
			}
		});
		var scope = this;
		$wrapper.on('summernote.codeview.toggled', function(e) {
			// forces autoformating upon toggling codeview
			var html = html_beautify(scope.get_value());
			scope.set_input(html); // first set it on summernote
			var note = $wrapper.data('summernote');
			var layout = note.layoutInfo;
			var codable = layout.codable;
			var cm = codable.data('cmEditor');
			// then set it in codemirror as it already has old content
			// by the time we get this event
			cm.getDoc().setValue(html);
		});
	},
	clean_html: function() {
		return this.wrapper.summernote('code');
	},
	set_input: function(html) {
		this.wrapper.summernote('code', html);
	},
	get_value: function() {
		return this.wrapper.summernote('code');
	},
	on_blur: function(fn) {
		this.wrapper.on('summernote.blur', fn);
	},
	on_keypress: function(keys, fn) {
		var key_groups = keys.split(" ");
		var scope = this;
		// stores shortcut callbacks
		$.each(key_groups, function(i, keys) {
			scope.keyMap[keys] = fn;
		});
	},
	_build_keycombo: function(e) {
		var keys = [];

		if (e.metaKey) { keys.push('CMD'); }
		if (e.ctrlKey && !e.altKey) { keys.push('CTRL'); }
		if (e.shiftKey) { keys.push('SHIFT'); }

		var keyName = String.fromCharCode(e.keyCode);
		if (keyName) { keys.push(keyName); }

		var keyCombo = keys.join('+');
		return keyCombo;
	},
	_keymap_handler: function(e) {
		var keyCombo = this._build_keycombo(e);

		//console.log("[up] shortcuts", keyCombo);
		var eventCallback = this.keyMap[keyCombo];
		if (eventCallback) {
			eventCallback();
			e.preventDefault();
			e.stopPropagation();
			return false;
		}

		// handle canceling frappe ctrl+b shortcut behaviour and
		// applying bolding instead
		if ( keyCombo == "CTRL+B" || keyCombo == "CMD+B" ) {
			this.wrapper.summernote('editor.bold');
			e.preventDefault();
			e.stopPropagation();
			return false;
		}
	}
});


