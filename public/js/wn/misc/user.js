// misc user functions

wn.user_info = function(uid) {
	var def = {
		'fullname':uid, 
		'image': 'lib/images/ui/no_img_m.gif'
	}
	if(!wn.boot.user_info) return def
	if(!wn.boot.user_info[uid]) return def
	if(!wn.boot.user_info[uid].fullname)
		wn.boot.user_info[uid].fullname = uid;
	if(!wn.boot.user_info[uid].image)
		wn.boot.user_info[uid].image = def.image;
	return wn.boot.user_info[uid];
}

wn.provide('wn.user');

$.extend(wn.user, {
	name: (wn.boot ? wn.boot.profile.name : 'Guest'),
	has_role: function(rl) {
		if(typeof rl=='string') 
			rl = [rl];
		for(var i in rl) {
			if((wn.boot ? wn.boot.profile.roles : ['Guest']).indexOf(rl[i])!=-1)
				return true;
		}
	},
	is_report_manager: function() {
		return wn.user.has_role(['Administrator', 'System Manager', 'Report Manager']);
	}
})

// wn.session_alive is true if user shows mouse movement in 30 seconds

wn.session_alive = true;
$(document).bind('mousemove', function() {
	wn.session_alive = true;
	if(wn.session_alive_timeout) 
		clearTimeout(wn.session_alive_timeout);
	wn.session_alive_timeout = setTimeout('wn.session_alive=false;', 30000);
})