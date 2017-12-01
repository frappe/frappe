frappe.ui.CheckList = class
{
	constructor (container, data, options)
	{
		this.$container = $(container);
		this.data       = data;
		this.options    = Object.assign({ }, frappe.ui.CheckList.OPTIONS, options);

		this.make();
	}

	make ( )
	{
		const $options  = $(this.data.map((option) => {
			const $dom  = $( // dom laga key, haisha. :)
				`<a href="javascript:void(0);" class="list-group-item checklist-item" data-value="${option.value}">
					<div class="row">
						<div class="col-xs-1">
							<input type="checkbox">
						</div>
						<div class="col-xs-10">
							${option.label ? option.label : option.value}
						</div>
					</div>
					   
				 </a>
				`
			);
			$dom.click(function ( ) {
				$(this).toggleClass('active');

				const active = $(this).hasClass('active');
				const $input = $(this).find('input[type=checkbox]');
				$input.prop('checked', active);
			});
			$dom.css({ 'font-weight': 'bold', 'font-size': '12px' });

			return $dom;
		})).map(function ( ) { return this.toArray(); }); // convert array of $ objects to $ object

		this.$panel     = $(`
			<div class="panel panel-default">
				<div class="panel-body"/>
			</div>
		`);
		this.$panel.css({ 'font-size': '12px' });
		
		this.$checklist = $(`<div class="list-group"/>`);
		this.$checklist.css({ 'max-height': '400px', 'overflow-y': 'scroll' });
		this.$checklist.append($options);
		
		const $checks   = $options.find('input[type=checkbox]');
		
		this.$panel.append(this.$checklist);

		if ( this.options.has_checkall )
		{
			this.$checkall = $(`
				<div class="row">
					<div class="col-xs-1">
						<input type="checkbox"/>
					</div>
					<div class="col-xs-10">
						${__("Select All")}
					</div>
				</div>
			`);
			const $input = this.$checkall.find('input');
			$input.on('change', function ( ) {
				const checked = $(this).prop('checked');
				if ( checked ) {
					$options.addClass('active');
				} else {
					$options.removeClass('active');
				}

				$checks.prop('checked', checked);
			});

			this.$panel.find('.panel-body').append(this.$checkall);
		}

		this.$container.append(this.$panel);
	}

	val ( )
	{
		// Not the best way, but I have no time.
		const $options = this.$checklist.find('.checklist-item');
		var   values   = [ ];
		$options.each(i => {
			const $option = $($options[i]);
			
			if ( $option.hasClass('active') ) {
				const value = $option.attr('data-value');
				values.push(value);
			}
		});

		return values;
	}
};
frappe.ui.CheckList.OPTIONS = 
{
	has_checkall: true
}