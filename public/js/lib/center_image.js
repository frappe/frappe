/**
 * bl-jquery-image-center jQuery Plugin 
 *
 * @copyright Boxlight Media Ltd. 2012
 * @license MIT License
 * @description Centers an image by moving, cropping and filling spaces inside it's parent container. Call 
 * this on a set of images to have them fill their parent whilst maintaining aspect ratio
 * @author Robert Cambridge
 *
 * Usage: See documentation at http://boxlight.github.com/bl-jquery-image-center
 */
$.fn.centerImage = function(method, callback) {
  callback = callback || function() {};
  var els = this;
  var remaining = $(this).length;
  method = method == 'inside';

  // execute this on an individual image element once it's loaded
  var fn = function(img) {
    var $img = $(img);
    var $div = $img.parent();
    // parent CSS should be in stylesheet, but to reinforce:
    $div.css({
      overflow: 'hidden',
    });

    // temporarily set the image size naturally so we can get the aspect ratio
    $img.css({
      'position':   'static',
      'width':      'auto',
      'height':     'auto',
      'max-width':  '100%',
      'max-height': '100%'
    });

    // now resize
    var div = { w: $div.width(), h: $div.height(), r: $div.width() / $div.height() };
    var img = { w: $img.width(), h: $img.height(), r: $img.width() / $img.height() };
	var width  = Math.round((div.r > img.r) ^ method ? '100%' : div.h / img.h * img.w);
	var height = Math.round((div.r < img.r) ^ method ? '100%' : div.w / img.w * img.h);

	if(width) width++;
	if(height) height++;

    $img.css({
      'max-width':  'none',
      'max-height': 'none',
      'width': width,
      'height': height,
    });

    // now center - but portrait images need to be centered slightly above halfway (33%)
    var div = { w: $div.width(), h: $div.height() };
    var img = { w: $img.width(), h: $img.height() };

	var left = Math.round((div.w - img.w) / 2);
	var top = Math.round((div.h - img.h) / 3);

    $img.css({
      'margin-left': left,
      'margin-top':  top
    });

    callbackWrapped(img)
  };

  var callbackWrapped = function(img) {
    remaining--;
    callback.apply(els, [ img, remaining ]);
  };

  // iterate through elements
  return els.each(function(i) {
    if (this.complete || this.readyState === 'complete') {
      // loaded already? run fn
      // when binding, we can tell whether image loaded or not.
      // not if it's already failed though :(
      (function(el) {
        // use setTimeout to prevent browser locking up
        setTimeout(function() { fn(el) }, 10);
      })(this);
    } else {
      // not loaded? bind to load
      (function(el) {
        $(el)
          .one('load', function() {
            // use setTimeout to prevent browser locking up
            setTimeout(function() {
              fn(el);
            }, 10);
          })
          .one('error', function() {
            // the image did not load
            callbackWrapped(el)
          })
        .end();

        // IE9 won't always trigger the load event. fix it.
        if (navigator.userAgent.indexOf("Trident/5") >= 0) {
          el.src = el.src;
        }
      })(this);
    }
  });
};
// Alias functions which often better describe the use case
$.fn.imageCenterResize = function(callback) {
  return $(this).centerImage('inside', callback);
};
$.fn.imageCropFill = function(callback) {
  return $(this).centerImage('outside', callback);
};
