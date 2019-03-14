frappe.ui.form.ControlRating  = frappe.ui.form.ControlInt.extend({
	make_input() {
		this._super();
		const star_template = `
		<div>
			<i class="fa fa-fw fa-star-o star-icon" data-idx=1></i>
			<i class="fa fa-fw fa-star-o star-icon" data-idx=2></i>
			<i class="fa fa-fw fa-star-o star-icon" data-idx=3></i>
			<i class="fa fa-fw fa-star-o star-icon" data-idx=4></i>
			<i class="fa fa-fw fa-star-o star-icon" data-idx=5></i>
		</div>
		`;
		
		this.$input_wrapper.html(star_template);

		this.$input_wrapper.find('i').hover((ev) => {
			const el = $(ev.currentTarget);
			var star_value = el.data('idx');
			el.parent().children('i.fa').each( function(e){
				if (e < star_value) {
					$(this).addClass('fa-star');
					$(this).removeClass('fa-star-o');
				} else {
					$(this).addClass('fa-star-o');
					$(this).removeClass('fa-star');
				}
			});	
		}, (ev) => {
			const el = $(ev.currentTarget);
			el.parent().children('i.fa').each( function(e) {
				$(this).addClass('fa-star-o');
				$(this).removeClass('fa-star');
			});
		});

		this.$input_wrapper.find('i').click((ev) => {
			const el = $(ev.currentTarget);
			var star_value = el.data('idx');
			el.parent().children('i.fa').each( function(e) {
				if (e < star_value){
					$(this).css('color', 'green');
				} else {
					$(this).css('color', '');
				}
				
			});
		});
	},
	set_formatted_input(value) { 
		console.log(value)
	}
});