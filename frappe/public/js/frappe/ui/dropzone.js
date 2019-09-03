// DropZone
frappe.ui.DropZone = class 
{
	constructor (selector, options) {
		this.options    = Object.assign({ }, frappe.ui.DropZone.OPTIONS, options);
		this.$container = $(selector);
		this.$wrapper   = $(frappe.ui.DropZone.TEMPLATE);

		this.make();
	}

	make ( ) {
		const me        = this;
		const $dropzone = this.$wrapper.find('.panel-body');
		const $title    = $dropzone.find('.dropzone-title');
		$title.html(this.options.title);

		$dropzone.on('dragover', function (e) {
			e.preventDefault();

			$title.html(__('Drop'));
		});
		$dropzone.on('dragleave', function (e) {
			e.preventDefault();

			$title.html(me.options.title);
		});
		$dropzone.on('drop', function (e) {
			e.preventDefault();

			const files = e.originalEvent.dataTransfer.files;
			me.options.drop(files);

			$title.html(me.options.title);
		});

		this.$container.html(this.$wrapper);
	}
};
frappe.ui.DropZone.TEMPLATE =
`
<div class="panel panel-default"
	style="
		border: none !important;
		box-shadow: none !important;
		margin-bottom: 0 !important
	">
	<div class="panel-body">
		<div class="dropzone-title text-muted text-center">
		</div>
	</div>
</div>
`;
frappe.ui.DropZone.OPTIONS  = 
{
	title: __('Drop Here')
};
