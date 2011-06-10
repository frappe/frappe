// element transforms

wn.fx = {
	
	// append a "working" like image next to the element
	set_working: function(ele) {
		if(ele.loading_img) { 
			wn.show(ele.loading_img);
		} else {
			ele.disabled = 1;
			ele.loading_img = wn.add(ele.parentNode,'img','',{
				marginLeft:'4px',
				marginBottom:'-2px',
				display:'inline'
			});
			ele.loading_img.src = wn.assets.button_loading;
		}
	}, 
	
	done_working: function(ele) {
		ele.disabled = 0;
		if(ele.loading_img) { $dh(ele.loading_img) };
	}
}

// bc
$item_set_working = wn.fx.set_working;
$item_done_working = wn.fx.done_working;