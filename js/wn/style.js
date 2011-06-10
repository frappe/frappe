// sets special style

wn.style = {
	gradient: function(ele, from, to) {
		// gradient
		var no_gradient=0;

		if(isIE)no_gradient=1;
		if(isFF && ffversion < 3.6)no_gradient=1;

		if(no_gradient) {
			var rgb_from = get_rgb(from.substr(1)); var rgb_to = get_rgb(to.substr(1));
			$y(ele, {backgroundColor: '#' 
				+ d2h(rgb_to[0] + (rgb_from[0]-rgb_to[0])/2) 
				+ d2h(rgb_to[1] + (rgb_from[1]-rgb_to[1])/2)
				+ d2h(rgb_to[2] + (rgb_from[2]-rgb_to[2])/2)});
		} else {
			$y(ele, {background: '-webkit-gradient(linear, left top, left bottom, from('+from+'), to('+to+'))'});
			$y(ele, {background: '-moz-linear-gradient(top, '+from+', '+to+')'});		
		}
	},
	
	border_radius: function(ele, r, corners) {
		if(corners) { 
			var cl = ['top-left', 'top-right', 'bottom-right' , 'bottom-left'];
			for(var i=0; i<4; i++) {
				if(corners[i]) {
					$(ele).css('-moz-border-radius-'+cl[i].replace('-',''),r).css('-webkit-'+cl[i]+'-border-radius',r);
				}
			}
		} else {
			$(ele).css('-moz-border-radius',r).css('-webkit-border-radius',r).css('border-radius',r); 
		}
	},
	
	box_shadow: function(ele, r) { 
		$(ele).css('-moz-box-shadow',r).css('-webkit-box-shadow',r).css('box-shadow',r); 
	},

	// set opacity (0-100)
	opacity: function(ele, ieop) {
		var op = ieop / 100;
		if (ele.filters) { // internet explorer
			try { 
				ele.filters.item("DXImageTransform.Microsoft.Alpha").opacity = ieop;
			} catch (e) { 
				ele.style.filter = 'progid:DXImageTransform.Microsoft.Alpha(opacity='+ieop+')';
			}
		} else  { // other browsers 
			ele.style.opacity = op; 
		}
	}	
}

//bc
$gr = wn.style.gradient;
$br = wn.style.border_radius;
$br = wn.style.box_shadow;
$op = wn.style.opacity;
