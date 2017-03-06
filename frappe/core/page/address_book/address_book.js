
frappe.AddressBook = Class.extend({
	init: function(parent) {
		this.page = frappe.ui.make_app_page({
			parent: parent,
			title: __("Address Book"),
			single_column: true
		});
		this.make();
		this.handleSliderNav();
	},

	make: function() {
		var me = this;
		this.get_address_and_contact_list();
		this.handleSliderNav();
	},

	handleSliderNav: function(data) {
		var me = this;
		$('.address-book-slider').sliderNav();
		$('.address-book .slider-content ul li ul li').click(function(e){
			e.preventDefault();
			var contact_card = $('#contact-card');
			//Get the name clicked on
			var contact_title = $(this).text();
			//Set the name
			$('#contact-card .panel-title').html(contact_title);

			var address = data.filter(function( obj ) {
				return obj.title == contact_title;
			});
			//show all rows
			$('.table-hover > tbody  > tr').show()
			//Set address and contact info
			var panel_body = $('#contact-card .panel-body')

			for (var key in address){
			    $('.card-name', panel_body).text(address[key].title);
				 $('.card-type', panel_body).text(address[key].type);
				$('.card-avatar', panel_body).html(frappe.avatar(address[key].title, 'avatar'));
				address_list = address[key].address_list
				if (!address_list[0]){
					$('.card-address', panel_body).html('');
				}
				for (a in address_list){
					$('.card-address', panel_body).html(address_list[a].display);
				}
				contact_list = address[key].contact_list
				if (!contact_list[0]){
					$('.card-phone', panel_body).text('');
					$('.card-mobile', panel_body).text('');
					$('.card-email', panel_body).text('');
				}
				for (c in contact_list){
					$('.card-phone', panel_body).text(contact_list[c].phone || '');
					$('.card-mobile', panel_body).text(contact_list[c].mobile_no || '');
					$('.card-email', panel_body).text('');
					if(contact_list[c].email_id){
						$('.card-email', panel_body).html(("<a href=mailto:"+contact_list[c].email_id+">"+contact_list[c].email_id+"</a>"));
					}
				}
			}
			//hide empty rows
			$('.table-hover > tbody  > tr').has('td:empty').hide()
		});	
	},
	get_address_and_contact_list: function (callback) {
		var me = this;
		frappe.call({
			method: "frappe.core.page.address_book.address_book.get_address_and_contact_list",
			callback: function (r) {
				if(r.message) {
					data = r.message;
				    contacts = {};
					for (d in data) {
						key = (data[d].title).charAt(0).toUpperCase()
						if (!(key in contacts)) {
							contacts[key] = new Array();
							contacts[key].push(data[d].title);
						}
						else {
							contacts[key].push(data[d].title);
						}
					}
					$(frappe.render_template("address_book", {'contacts': contacts, 'keys': Object.keys(contacts).sort()})).appendTo(me.page.main);

					me.handleSliderNav(data);

					$('.address-book .slider-content ul li ul li:first').trigger('click');
				}
			}
		})
	},
});

frappe.pages['address-book'].on_page_load = function(wrapper) {
	frappe.address_book = new frappe.AddressBook(wrapper);
}

$.fn.sliderNav = function(options) {
	var defaults = { items: ["A","B","C","D","E","F","G","H","I","J","K","L","M","N","O","P","Q","R","S","T","U","V","W","X","Y","Z"], debug: false, height: null, arrows: true};
	var opts = $.extend(defaults, options); var o = $.meta ? $.extend({}, opts, $$.data()) : opts; var slider = $(this); $(slider).addClass('slidernav');
	$(slider).append('<div class="slider-nav"><ul></ul></div>');
	for(var i in o.items) $('.slider-nav ul', slider).append("<li><a alt='#"+o.items[i]+"'>"+o.items[i]+"</a></li>");
	var height = $('.slider-nav', slider).height();
	if(o.height) height = o.height;
	$('.slider-content, .slider-nav', slider).css('height',height);
	if(o.debug) $(slider).append('<div id="debug">Scroll Offset: <span>0</span></div>');
	$('.slider-nav a', slider).mouseover(function(event){
		var target = $(this).attr('alt');
		var cOffset = $('.slider-content', slider).offset().top;
		var tOffset = $('.slider-content '+target, slider).offset().top;
		var height = $('.slider-nav', slider).height(); if(o.height) height = o.height;
		var pScroll = (tOffset - cOffset) - height/8;
		$('.slider-content li', slider).removeClass('selected');
		$(target).addClass('selected');
		$('.slider-content', slider).stop().animate({scrollTop: '+=' + pScroll + 'px'});
		if(o.debug) $('#debug span', slider).html(tOffset);
	});
	if(o.arrows){
		$(slider).prepend('<div class="slide-up end"><span class="arrow up"></span></div>');
		$(slider).append('<div class="slide-down"><span class="arrow down"></span></div>');
		$('.slide-down',slider).click(function(){
			$('.slider-content',slider).animate({scrollTop : "+="+height+"px"}, 500);
		});
		$('.slide-up',slider).click(function(){
			$('.slider-content',slider).animate({scrollTop : "-="+height+"px"}, 500);
		});
	}
}