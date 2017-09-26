frappe.ui.Capture = class
{
	constructor (options = { })
	{
		this.options = Object.assign({}, frappe.ui.Capture.DEFAULT_OPTIONS, options);
		this.dialog = new frappe.ui.Dialog();
		this.template = 
		`
			<div class="text-center">
				<div class="img-thumbnail" style="border: none;">
					<div id="frappe-capture"/>
				</div>
			</div>

			<div id="frappe-capture-btn-toolbar" style="padding-top: 15px; padding-bottom: 15px;">
				<div class="text-center">
					<div id="frappe-capture-btn-toolbar-snap">
						<a id="frappe-capture-btn-snap">
							<i class="fa fa-fw fa-2x fa-circle-o"/>
						</a>
					</div>
					<div class="btn-group" id="frappe-capture-btn-toolbar-knap">
						<button class="btn btn-default" id="frappe-capture-btn-discard">
							<i class="fa fa-fw fa-arrow-left"/>
						</button>
						<button class="btn btn-default" id="frappe-capture-btn-accept">
							<i class="fa fa-fw fa-arrow-right"/>
						</button>
					</div>
				</div>
			</div>
		`;
		$(this.dialog.body).append(this.template);

		this.$btnBarSnap = $(this.dialog.body).find('#frappe-capture-btn-toolbar-snap');
		this.$btnBarKnap = $(this.dialog.body).find('#frappe-capture-btn-toolbar-knap');
		this.$btnBarKnap.hide();

		Webcam.set(this.options);
	}

	open ( )
	{
		this.dialog.show();

		Webcam.attach('#frappe-capture');
	}

	freeze ( )
	{
		this.$btnBarSnap.hide();
		this.$btnBarKnap.show();
		
		Webcam.freeze();
	}

	unfreeze ( )
	{
		this.$btnBarSnap.show();
		this.$btnBarKnap.hide();

		Webcam.unfreeze();
	}

	click (callback) 
	{
		$(this.dialog.body).find('#frappe-capture-btn-snap').click(() => {
			this.freeze();

			$(this.dialog.body).find('#frappe-capture-btn-discard').click(() => {
				this.unfreeze();
			});

			$(this.dialog.body).find('#frappe-capture-btn-accept').click(() => {
				Webcam.snap((data) => {
					callback(data);
				});

				this.hide();
			});
		});
	}

	hide ( )
	{
		Webcam.reset();

		$(this.dialog.$wrapper).remove();
	}
};
frappe.ui.Capture.DEFAULT_OPTIONS = 
{
	width: 480, height: 320, flip_horiz: true
};