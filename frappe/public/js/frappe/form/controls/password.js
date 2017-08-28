frappe.ui.form.ControlPassword = frappe.ui.form.ControlData.extend({
	input_type: "password",
	make: function() {
		this._super();
	},
	make_input: function() {
		var me = this;
		this._super();
		this.$input.parent().append($('<span class="password-strength-indicator indicator"></span>'));
		this.$wrapper.find('.control-input-wrapper').append($('<p class="password-strength-message text-muted small hidden"></p>'));

		this.indicator = this.$wrapper.find('.password-strength-indicator');
		this.message = this.$wrapper.find('.help-box');

		this.$input.on('input', () => {
			var $this = $(this);
			clearTimeout($this.data('timeout'));
			$this.data('timeout', setTimeout(() => {
				var txt = me.$input.val();
				me.get_password_strength(txt);
			}), 300);
		});
	},
	get_password_strength: function(value) {
		var me = this;
		frappe.call({
			type: 'GET',
			method: 'frappe.core.doctype.user.user.test_password_strength',
			args: {
				new_password: value || ''
			},
			callback: function(r) {
				if (r.message && r.message.entropy) {
					var score = r.message.score,
						feedback = r.message.feedback;

					feedback.crack_time_display = r.message.crack_time_display;

					var indicators = ['grey', 'red', 'orange', 'yellow', 'green'];
					me.set_strength_indicator(indicators[score]);

				}
			}

		});
	},
	set_strength_indicator: function(color) {
		var message = __("Include symbols, numbers and capital letters in the password");
		this.indicator.removeClass().addClass('password-strength-indicator indicator ' + color);
		this.message.html(message).removeClass('hidden');
	}
});
