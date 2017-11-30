frappe.ui.CheckList = class
{
	constructor (container, options)
	{
		this.$container = $(container)
		this.options    = options

		this.make()
	}

	make ( )
	{
		const $options  = this.options.map((option) => {
			const $dom  = $( // dom laga key, haisha. :)
				`<a href="javascript:void(0);" class="list-group-item" data-value="${option.value}">
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
			)
			$dom.click(function ( ) {
				$(this).toggleClass('active')

				const active = $(this).hasClass('active')
				const $input = $(this).find('input[type=checkbox]')
				$input.prop('checked', active)
			})
			$dom.css({ 'font-weight': 'bold', 'font-size': '12px' })

			return $dom
		})

		this.$checklist = $(`<div class="list-group"/>`)
		this.$checklist.css({ 'max-height': '400px', 'overflow-y': 'scroll' })
		this.$checklist.append($options)
		
		this.$container.append(this.$checklist)
	}

	val ( )
	{
		// Not the best way, but I have no time.
		const $options = this.$checklist.find('.list-group-item')
		var   values   = [ ]
		$options.each(i => {
			const $option = $($options[i])
			
			if ( $option.hasClass('active') ) {
				const value = $option.attr('data-value')
				values.push(value)
			}
		})

		return values
	}
}