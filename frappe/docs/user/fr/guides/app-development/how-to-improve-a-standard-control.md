Frappé has a couple of elegant and useful widgets, but some times we need to edit them to add small improvements. This small article will describe how to add new resources to the standard widgets.

Let me explain first our goal:

&gt; Add `many` alternative translations in `numerous records` and in a `lot of doctypes`

Look the highlighted sections in the __goal__, we have _many translations_ to add in _many records_ and in _many doctypes_, so, we heave a **many of work**, so we have a lot to do right?

The answer for this question is: _-Of course not! Because we know that if one element exists in many records and in many doctypes, this element is the `Control` or `Widget`_

So, what we need do, is improve your goal based on the `Control`, to reduce our quantity of work.

But, where will we find this magic element, the control? _-For now, we can look it in the JavaScript sources - let's look now at [Github](https://github.com/frappe/frappe/blob/develop/frappe/public/js/frappe/form/control.js#L13)_

&gt; Don't worry if you don't understand the code for now, our goal there is simplify our work.

Let's go ahead with the thought!

We know where we need to make the changes, but how will we dismember which are the controls that are affected by our feature and which aren't ?

We need to keep in mind, that `Control` are instance of `DocFields` and the `DocFields` have a field that is very important for us in this case, the field that will help us to dismember which are affected by our feature and which aren't is the field `options` in the `DocField`.

_-Wait!, we understood that the field `options` can help us, but, how will it help us?_ 

Good question, we will define a word to put in the `options` of the `DocFields` that we need to include the feature, this world will be **`Translatable`.**

&gt; If you forget how to customize the options of a field look [this article](https://kb.erpnext.com/kb/customize/creating-custom-link-field), it can refresh your knowledge.

Well, with the defined word in `options` of our selected `DocFields`, now is time to code:

_-At last, we think we would never stop talking!_

	frappe.ui.form.ControlData = frappe.ui.form.ControlData.$extend({
		make_input: function(){
			var options = this.df.options;
			if (!options || options!=="Translatable"){
				this._super();
				return;
			}
			var me = this;
			$('<div class="link-field" style="position: relative;">\
				<input type="text" class="input-with-feedback form-control">\
				<span class="dialog-btn">\
					<a class="btn-open no-decoration" title="' + __(" open="" translation")="" +="" '"="">\
					<i class="icon-globe"></i></a>\
				</span>\
			</div>').prependTo(this.input_area);
			this.$input_area = $(this.input_area);
			this.$input = this.$input_area.find('input');
			this.$btn = this.$input_area.find('.dialog-btn');
			this.set_input_attributes();
			this.$input.on("focus", function(){
				me.$btn.toggle(true);
			});
			this.$input.on("blur", function(){
				setTimeout(function(){ me.$btn.toggle(false) }, 500);
			});
			this.input = $this.input.get(0);
			this.has_input = true;
			var me = this;
			this.setup_button();
		},
		setup_button: function(){
			var me = this;
			if (this.only_input){
				this.$btn.remove();
				return;
			}
			this.$btn.on("click", function(){
				var value = me.get_value();
				var options = me.df.options;
				if (value &amp;&amp; options &amp;&amp; options==="Translatable"){
					this.open_dialog();
				}
			});
		},
		open_dialog: function(){
			var doc = this.doc;
			if (!doc.__unsaved){
				new frappe.ui.form.TranslationSelector({
					doc: doc,
					df: this.doc,
					text: this.value
				});
			}
		}
	});

_-Other letter soup, for my gosh!_

In fact, it IS a soup of letters, for a newbie, but we are not a beginner.

Let me explain what this code does;

 - At line 1 the code overrides the `ControlData` by one extended `Class` of itself.
 - The method `make_input` checks if the docfield is **`Translatable`** to make the new `Control` if not, it calls the *original* `make_input` using `_super()`
 - The method `setup_button` checks if the docfield is **`Translatable`** to enable it show a `dialog`
 - The method `open_dialog` invokes a new instance of the `TranslationSelector` that we will create in the code below.



<!-- markdown -->