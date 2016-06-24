/*
 * blueimp Gallery JS
 * https://github.com/blueimp/Gallery
 *
 * Copyright 2013, Sebastian Tschan
 * https://blueimp.net
 *
 * Swipe implementation based on
 * https://github.com/bradbirdsall/Swipe
 *
 * Licensed under the MIT license:
 * http://www.opensource.org/licenses/MIT
 */

/* global define, window, document, DocumentTouch */

;(function (factory) {
  'use strict'
  if (typeof define === 'function' && define.amd) {
    // Register as an anonymous AMD module:
    define(['./blueimp-helper'], factory)
  } else {
    // Browser globals:
    window.blueimp = window.blueimp || {}
    window.blueimp.Gallery = factory(
      window.blueimp.helper || window.jQuery
    )
  }
}(function ($) {
  'use strict'

  function Gallery (list, options) {
    if (document.body.style.maxHeight === undefined) {
      // document.body.style.maxHeight is undefined on IE6 and lower
      return null
    }
    if (!this || this.options !== Gallery.prototype.options) {
      // Called as function instead of as constructor,
      // so we simply return a new instance:
      return new Gallery(list, options)
    }
    if (!list || !list.length) {
      this.console.log(
        'blueimp Gallery: No or empty list provided as first argument.',
        list
      )
      return
    }
    this.list = list
    this.num = list.length
    this.initOptions(options)
    this.initialize()
  }

  $.extend(Gallery.prototype, {
    options: {
      // The Id, element or querySelector of the gallery widget:
      container: '#blueimp-gallery',
      // The tag name, Id, element or querySelector of the slides container:
      slidesContainer: 'div',
      // The tag name, Id, element or querySelector of the title element:
      titleElement: 'h3',
      // The class to add when the gallery is visible:
      displayClass: 'blueimp-gallery-display',
      // The class to add when the gallery controls are visible:
      controlsClass: 'blueimp-gallery-controls',
      // The class to add when the gallery only displays one element:
      singleClass: 'blueimp-gallery-single',
      // The class to add when the left edge has been reached:
      leftEdgeClass: 'blueimp-gallery-left',
      // The class to add when the right edge has been reached:
      rightEdgeClass: 'blueimp-gallery-right',
      // The class to add when the automatic slideshow is active:
      playingClass: 'blueimp-gallery-playing',
      // The class for all slides:
      slideClass: 'slide',
      // The slide class for loading elements:
      slideLoadingClass: 'slide-loading',
      // The slide class for elements that failed to load:
      slideErrorClass: 'slide-error',
      // The class for the content element loaded into each slide:
      slideContentClass: 'slide-content',
      // The class for the "toggle" control:
      toggleClass: 'toggle',
      // The class for the "prev" control:
      prevClass: 'prev',
      // The class for the "next" control:
      nextClass: 'next',
      // The class for the "close" control:
      closeClass: 'close',
      // The class for the "play-pause" toggle control:
      playPauseClass: 'play-pause',
      // The list object property (or data attribute) with the object type:
      typeProperty: 'type',
      // The list object property (or data attribute) with the object title:
      titleProperty: 'title',
      // The list object property (or data attribute) with the object URL:
      urlProperty: 'href',
      // The list object property (or data attribute) with the object srcset URL(s):
      srcsetProperty: 'urlset',
      // The gallery listens for transitionend events before triggering the
      // opened and closed events, unless the following option is set to false:
      displayTransition: true,
      // Defines if the gallery slides are cleared from the gallery modal,
      // or reused for the next gallery initialization:
      clearSlides: true,
      // Defines if images should be stretched to fill the available space,
      // while maintaining their aspect ratio (will only be enabled for browsers
      // supporting background-size="contain", which excludes IE < 9).
      // Set to "cover", to make images cover all available space (requires
      // support for background-size="cover", which excludes IE < 9):
      stretchImages: false,
      // Toggle the controls on pressing the Return key:
      toggleControlsOnReturn: true,
      // Toggle the controls on slide click:
      toggleControlsOnSlideClick: true,
      // Toggle the automatic slideshow interval on pressing the Space key:
      toggleSlideshowOnSpace: true,
      // Navigate the gallery by pressing left and right on the keyboard:
      enableKeyboardNavigation: true,
      // Close the gallery on pressing the Esc key:
      closeOnEscape: true,
      // Close the gallery when clicking on an empty slide area:
      closeOnSlideClick: true,
      // Close the gallery by swiping up or down:
      closeOnSwipeUpOrDown: true,
      // Emulate touch events on mouse-pointer devices such as desktop browsers:
      emulateTouchEvents: true,
      // Stop touch events from bubbling up to ancestor elements of the Gallery:
      stopTouchEventsPropagation: false,
      // Hide the page scrollbars:
      hidePageScrollbars: true,
      // Stops any touches on the container from scrolling the page:
      disableScroll: true,
      // Carousel mode (shortcut for carousel specific options):
      carousel: false,
      // Allow continuous navigation, moving from last to first
      // and from first to last slide:
      continuous: true,
      // Remove elements outside of the preload range from the DOM:
      unloadElements: true,
      // Start with the automatic slideshow:
      startSlideshow: false,
      // Delay in milliseconds between slides for the automatic slideshow:
      slideshowInterval: 5000,
      // The starting index as integer.
      // Can also be an object of the given list,
      // or an equal object with the same url property:
      index: 0,
      // The number of elements to load around the current index:
      preloadRange: 2,
      // The transition speed between slide changes in milliseconds:
      transitionSpeed: 400,
      // The transition speed for automatic slide changes, set to an integer
      // greater 0 to override the default transition speed:
      slideshowTransitionSpeed: undefined,
      // The event object for which the default action will be canceled
      // on Gallery initialization (e.g. the click event to open the Gallery):
      event: undefined,
      // Callback function executed when the Gallery is initialized.
      // Is called with the gallery instance as "this" object:
      onopen: undefined,
      // Callback function executed when the Gallery has been initialized
      // and the initialization transition has been completed.
      // Is called with the gallery instance as "this" object:
      onopened: undefined,
      // Callback function executed on slide change.
      // Is called with the gallery instance as "this" object and the
      // current index and slide as arguments:
      onslide: undefined,
      // Callback function executed after the slide change transition.
      // Is called with the gallery instance as "this" object and the
      // current index and slide as arguments:
      onslideend: undefined,
      // Callback function executed on slide content load.
      // Is called with the gallery instance as "this" object and the
      // slide index and slide element as arguments:
      onslidecomplete: undefined,
      // Callback function executed when the Gallery is about to be closed.
      // Is called with the gallery instance as "this" object:
      onclose: undefined,
      // Callback function executed when the Gallery has been closed
      // and the closing transition has been completed.
      // Is called with the gallery instance as "this" object:
      onclosed: undefined
    },

    carouselOptions: {
      hidePageScrollbars: false,
      toggleControlsOnReturn: false,
      toggleSlideshowOnSpace: false,
      enableKeyboardNavigation: false,
      closeOnEscape: false,
      closeOnSlideClick: false,
      closeOnSwipeUpOrDown: false,
      disableScroll: false,
      startSlideshow: true
    },

    console: window.console && typeof window.console.log === 'function'
      ? window.console
      : {log: function () {}},

    // Detect touch, transition, transform and background-size support:
    support: (function (element) {
      var support = {
        touch: window.ontouchstart !== undefined ||
          (window.DocumentTouch && document instanceof DocumentTouch)
      }
      var transitions = {
        webkitTransition: {
          end: 'webkitTransitionEnd',
          prefix: '-webkit-'
        },
        MozTransition: {
          end: 'transitionend',
          prefix: '-moz-'
        },
        OTransition: {
          end: 'otransitionend',
          prefix: '-o-'
        },
        transition: {
          end: 'transitionend',
          prefix: ''
        }
      }
      var prop
      for (prop in transitions) {
        if (transitions.hasOwnProperty(prop) &&
          element.style[prop] !== undefined) {
          support.transition = transitions[prop]
          support.transition.name = prop
          break
        }
      }
      function elementTests () {
        var transition = support.transition
        var prop
        var translateZ
        document.body.appendChild(element)
        if (transition) {
          prop = transition.name.slice(0, -9) + 'ransform'
          if (element.style[prop] !== undefined) {
            element.style[prop] = 'translateZ(0)'
            translateZ = window.getComputedStyle(element)
              .getPropertyValue(transition.prefix + 'transform')
            support.transform = {
              prefix: transition.prefix,
              name: prop,
              translate: true,
              translateZ: !!translateZ && translateZ !== 'none'
            }
          }
        }
        if (element.style.backgroundSize !== undefined) {
          support.backgroundSize = {}
          element.style.backgroundSize = 'contain'
          support.backgroundSize.contain = window
            .getComputedStyle(element)
            .getPropertyValue('background-size') === 'contain'
          element.style.backgroundSize = 'cover'
          support.backgroundSize.cover = window
            .getComputedStyle(element)
            .getPropertyValue('background-size') === 'cover'
        }
        document.body.removeChild(element)
      }
      if (document.body) {
        elementTests()
      } else {
        $(document).on('DOMContentLoaded', elementTests)
      }
      return support
    // Test element, has to be standard HTML and must not be hidden
    // for the CSS3 tests using window.getComputedStyle to be applicable:
    }(document.createElement('div'))),

    requestAnimationFrame: window.requestAnimationFrame ||
      window.webkitRequestAnimationFrame ||
      window.mozRequestAnimationFrame,

    initialize: function () {
      this.initStartIndex()
      if (this.initWidget() === false) {
        return false
      }
      this.initEventListeners()
      // Load the slide at the given index:
      this.onslide(this.index)
      // Manually trigger the slideend event for the initial slide:
      this.ontransitionend()
      // Start the automatic slideshow if applicable:
      if (this.options.startSlideshow) {
        this.play()
      }
    },

    slide: function (to, speed) {
      window.clearTimeout(this.timeout)
      var index = this.index
      var direction
      var naturalDirection
      var diff
      if (index === to || this.num === 1) {
        return
      }
      if (!speed) {
        speed = this.options.transitionSpeed
      }
      if (this.support.transform) {
        if (!this.options.continuous) {
          to = this.circle(to)
        }
        // 1: backward, -1: forward:
        direction = Math.abs(index - to) / (index - to)
        // Get the actual position of the slide:
        if (this.options.continuous) {
          naturalDirection = direction
          direction = -this.positions[this.circle(to)] / this.slideWidth
          // If going forward but to < index, use to = slides.length + to
          // If going backward but to > index, use to = -slides.length + to
          if (direction !== naturalDirection) {
            to = -direction * this.num + to
          }
        }
        diff = Math.abs(index - to) - 1
        // Move all the slides between index and to in the right direction:
        while (diff) {
          diff -= 1
          this.move(
            this.circle((to > index ? to : index) - diff - 1),
            this.slideWidth * direction,
            0
          )
        }
        to = this.circle(to)
        this.move(index, this.slideWidth * direction, speed)
        this.move(to, 0, speed)
        if (this.options.continuous) {
          this.move(
            this.circle(to - direction),
            -(this.slideWidth * direction),
            0
          )
        }
      } else {
        to = this.circle(to)
        this.animate(index * -this.slideWidth, to * -this.slideWidth, speed)
      }
      this.onslide(to)
    },

    getIndex: function () {
      return this.index
    },

    getNumber: function () {
      return this.num
    },

    prev: function () {
      if (this.options.continuous || this.index) {
        this.slide(this.index - 1)
      }
    },

    next: function () {
      if (this.options.continuous || this.index < this.num - 1) {
        this.slide(this.index + 1)
      }
    },

    nextSlides: function() {
      // next set of images
      this.next()
    },

    prevSlides: function() {
      // prev set of images
      this.prev()
    },

    play: function (time) {
      var that = this
      window.clearTimeout(this.timeout)
      this.interval = time || this.options.slideshowInterval
      if (this.elements[this.index] > 1) {
        this.timeout = this.setTimeout(
          (!this.requestAnimationFrame && this.slide) || function (to, speed) {
            that.animationFrameId = that.requestAnimationFrame.call(
              window,
              function () {
                that.slide(to, speed)
              }
            )
          },
          [this.index + 1, this.options.slideshowTransitionSpeed],
          this.interval
        )
      }
      this.container.addClass(this.options.playingClass)
    },

    pause: function () {
      window.clearTimeout(this.timeout)
      this.interval = null
      this.container.removeClass(this.options.playingClass)
    },

    add: function (list) {
      var i
      if (!list.concat) {
        // Make a real array out of the list to add:
        list = Array.prototype.slice.call(list)
      }
      if (!this.list.concat) {
        // Make a real array out of the Gallery list:
        this.list = Array.prototype.slice.call(this.list)
      }
      this.list = this.list.concat(list)
      this.num = this.list.length
      if (this.num > 2 && this.options.continuous === null) {
        this.options.continuous = true
        this.container.removeClass(this.options.leftEdgeClass)
      }
      this.container
        .removeClass(this.options.rightEdgeClass)
        .removeClass(this.options.singleClass)
      for (i = this.num - list.length; i < this.num; i += 1) {
        this.addSlide(i)
        this.positionSlide(i)
      }
      this.positions.length = this.num
      this.initSlides(true)
    },

    resetSlides: function () {
      this.slidesContainer.empty()
      this.unloadAllSlides()
      this.slides = []
    },

    handleClose: function () {
      var options = this.options
      this.destroyEventListeners()
      // Cancel the slideshow:
      this.pause()
      this.container[0].style.display = 'none'
      this.container
        .removeClass(options.displayClass)
        .removeClass(options.singleClass)
        .removeClass(options.leftEdgeClass)
        .removeClass(options.rightEdgeClass)
      if (options.hidePageScrollbars) {
        document.body.style.overflow = this.bodyOverflowStyle
      }
      if (this.options.clearSlides) {
        this.resetSlides()
      }
      if (this.options.onclosed) {
        this.options.onclosed.call(this)
      }
    },

    close: function () {
      var that = this
      function closeHandler (event) {
        if (event.target === that.container[0]) {
          that.container.off(
            that.support.transition.end,
            closeHandler
          )
          that.handleClose()
        }
      }
      if (this.options.onclose) {
        this.options.onclose.call(this)
      }
      if (this.support.transition && this.options.displayTransition) {
        this.container.on(
          this.support.transition.end,
          closeHandler
        )
        this.container.removeClass(this.options.displayClass)
      } else {
        this.handleClose()
      }
    },

    circle: function (index) {
      // Always return a number inside of the slides index range:
      return (this.num + (index % this.num)) % this.num
    },

    move: function (index, dist, speed) {
      this.translateX(index, dist, speed)
      this.positions[index] = dist
    },

    translate: function (index, x, y, speed) {
      var style = this.slides[index].style
      var transition = this.support.transition
      var transform = this.support.transform
      style[transition.name + 'Duration'] = speed + 'ms'
      style[transform.name] = 'translate(' + x + 'px, ' + y + 'px)' +
      (transform.translateZ ? ' translateZ(0)' : '')
    },

    translateX: function (index, x, speed) {
      this.translate(index, x, 0, speed)
    },

    translateY: function (index, y, speed) {
      this.translate(index, 0, y, speed)
    },

    animate: function (from, to, speed) {
      if (!speed) {
        this.slidesContainer[0].style.left = to + 'px'
        return
      }
      var that = this
      var start = new Date().getTime()
      var timer = window.setInterval(function () {
        var timeElap = new Date().getTime() - start
        if (timeElap > speed) {
          that.slidesContainer[0].style.left = to + 'px'
          that.ontransitionend()
          window.clearInterval(timer)
          return
        }
        that.slidesContainer[0].style.left = (((to - from) *
          (Math.floor((timeElap / speed) * 100) / 100)) +
          from) + 'px'
      }, 4)
    },

    preventDefault: function (event) {
      if (event.preventDefault) {
        event.preventDefault()
      } else {
        event.returnValue = false
      }
    },

    stopPropagation: function (event) {
      if (event.stopPropagation) {
        event.stopPropagation()
      } else {
        event.cancelBubble = true
      }
    },

    onresize: function () {
      this.initSlides(true)
    },

    onmousedown: function (event) {
      // Trigger on clicks of the left mouse button only
      // and exclude video elements:
      if (event.which && event.which === 1 &&
        event.target.nodeName !== 'VIDEO') {
        // Preventing the default mousedown action is required
        // to make touch emulation work with Firefox:
        event.preventDefault()
        ;(event.originalEvent || event).touches = [{
          pageX: event.pageX,
          pageY: event.pageY
        }]
        this.ontouchstart(event)
      }
    },

    onmousemove: function (event) {
      if (this.touchStart) {
        (event.originalEvent || event).touches = [{
          pageX: event.pageX,
          pageY: event.pageY
        }]
        this.ontouchmove(event)
      }
    },

    onmouseup: function (event) {
      if (this.touchStart) {
        this.ontouchend(event)
        delete this.touchStart
      }
    },

    onmouseout: function (event) {
      if (this.touchStart) {
        var target = event.target
        var related = event.relatedTarget
        if (!related || (related !== target &&
          !$.contains(target, related))) {
          this.onmouseup(event)
        }
      }
    },

    ontouchstart: function (event) {
      if (this.options.stopTouchEventsPropagation) {
        this.stopPropagation(event)
      }
      // jQuery doesn't copy touch event properties by default,
      // so we have to access the originalEvent object:
      var touches = (event.originalEvent || event).touches[0]
      this.touchStart = {
        // Remember the initial touch coordinates:
        x: touches.pageX,
        y: touches.pageY,
        // Store the time to determine touch duration:
        time: Date.now()
      }
      // Helper variable to detect scroll movement:
      this.isScrolling = undefined
      // Reset delta values:
      this.touchDelta = {}
    },

    ontouchmove: function (event) {
      if (this.options.stopTouchEventsPropagation) {
        this.stopPropagation(event)
      }
      // jQuery doesn't copy touch event properties by default,
      // so we have to access the originalEvent object:
      var touches = (event.originalEvent || event).touches[0]
      var scale = (event.originalEvent || event).scale
      var index = this.index
      var touchDeltaX
      var indices
      // Ensure this is a one touch swipe and not, e.g. a pinch:
      if (touches.length > 1 || (scale && scale !== 1)) {
        return
      }
      if (this.options.disableScroll) {
        event.preventDefault()
      }
      // Measure change in x and y coordinates:
      this.touchDelta = {
        x: touches.pageX - this.touchStart.x,
        y: touches.pageY - this.touchStart.y
      }
      touchDeltaX = this.touchDelta.x
      // Detect if this is a vertical scroll movement (run only once per touch):
      if (this.isScrolling === undefined) {
        this.isScrolling = this.isScrolling ||
        Math.abs(touchDeltaX) < Math.abs(this.touchDelta.y)
      }
      if (!this.isScrolling) {
        // Always prevent horizontal scroll:
        event.preventDefault()
        // Stop the slideshow:
        window.clearTimeout(this.timeout)
        if (this.options.continuous) {
          indices = [
            this.circle(index + 1),
            index,
            this.circle(index - 1)
          ]
        } else {
          // Increase resistance if first slide and sliding left
          // or last slide and sliding right:
          this.touchDelta.x = touchDeltaX =
            touchDeltaX /
            (
            ((!index && touchDeltaX > 0) ||
            (index === this.num - 1 && touchDeltaX < 0))
              ? (Math.abs(touchDeltaX) / this.slideWidth + 1)
              : 1
          )
          indices = [index]
          if (index) {
            indices.push(index - 1)
          }
          if (index < this.num - 1) {
            indices.unshift(index + 1)
          }
        }
        while (indices.length) {
          index = indices.pop()
          this.translateX(index, touchDeltaX + this.positions[index], 0)
        }
      } else if (this.options.closeOnSwipeUpOrDown) {
        this.translateY(index, this.touchDelta.y + this.positions[index], 0)
      }
    },

    ontouchend: function (event) {
      if (this.options.stopTouchEventsPropagation) {
        this.stopPropagation(event)
      }
      var index = this.index
      var speed = this.options.transitionSpeed
      var slideWidth = this.slideWidth
      var isShortDuration = Number(Date.now() - this.touchStart.time) < 250
      // Determine if slide attempt triggers next/prev slide:
      var isValidSlide =
      (isShortDuration && Math.abs(this.touchDelta.x) > 20) ||
        Math.abs(this.touchDelta.x) > slideWidth / 2
      // Determine if slide attempt is past start or end:
      var isPastBounds = (!index && this.touchDelta.x > 0) ||
        (index === this.num - 1 && this.touchDelta.x < 0)
      var isValidClose = !isValidSlide && this.options.closeOnSwipeUpOrDown &&
        ((isShortDuration && Math.abs(this.touchDelta.y) > 20) ||
        Math.abs(this.touchDelta.y) > this.slideHeight / 2)
      var direction
      var indexForward
      var indexBackward
      var distanceForward
      var distanceBackward
      if (this.options.continuous) {
        isPastBounds = false
      }
      // Determine direction of swipe (true: right, false: left):
      direction = this.touchDelta.x < 0 ? -1 : 1
      if (!this.isScrolling) {
        if (isValidSlide && !isPastBounds) {
          indexForward = index + direction
          indexBackward = index - direction
          distanceForward = slideWidth * direction
          distanceBackward = -slideWidth * direction
          if (this.options.continuous) {
            this.move(this.circle(indexForward), distanceForward, 0)
            this.move(this.circle(index - 2 * direction), distanceBackward, 0)
          } else if (indexForward >= 0 &&
            indexForward < this.num) {
            this.move(indexForward, distanceForward, 0)
          }
          this.move(index, this.positions[index] + distanceForward, speed)
          this.move(
            this.circle(indexBackward),
            this.positions[this.circle(indexBackward)] + distanceForward,
            speed
          )
          index = this.circle(indexBackward)
          this.onslide(index)
        } else {
          // Move back into position
          if (this.options.continuous) {
            this.move(this.circle(index - 1), -slideWidth, speed)
            this.move(index, 0, speed)
            this.move(this.circle(index + 1), slideWidth, speed)
          } else {
            if (index) {
              this.move(index - 1, -slideWidth, speed)
            }
            this.move(index, 0, speed)
            if (index < this.num - 1) {
              this.move(index + 1, slideWidth, speed)
            }
          }
        }
      } else {
        if (isValidClose) {
          this.close()
        } else {
          // Move back into position
          this.translateY(index, 0, speed)
        }
      }
    },

    ontouchcancel: function (event) {
      if (this.touchStart) {
        this.ontouchend(event)
        delete this.touchStart
      }
    },

    ontransitionend: function (event) {
      var slide = this.slides[this.index]
      if (!event || slide === event.target) {
        if (this.interval) {
          this.play()
        }
        this.setTimeout(
          this.options.onslideend,
          [this.index, slide]
        )
      }
    },

    oncomplete: function (event) {
      var target = event.target || event.srcElement
      var parent = target && target.parentNode
      var index
      if (!target || !parent) {
        return
      }
      index = this.getNodeIndex(parent)
      $(parent).removeClass(this.options.slideLoadingClass)
      if (event.type === 'error') {
        $(parent).addClass(this.options.slideErrorClass)
        this.elements[index] = 3 // Fail
      } else {
        this.elements[index] = 2 // Done
      }
      // Fix for IE7's lack of support for percentage max-height:
      if (target.clientHeight > this.container[0].clientHeight) {
        target.style.maxHeight = this.container[0].clientHeight
      }
      if (this.interval && this.slides[this.index] === parent) {
        this.play()
      }
      this.setTimeout(
        this.options.onslidecomplete,
        [index, parent]
      )
    },

    onload: function (event) {
      this.oncomplete(event)
    },

    onerror: function (event) {
      this.oncomplete(event)
    },

    onkeydown: function (event) {
      switch (event.which || event.keyCode) {
        case 13: // Return
          if (this.options.toggleControlsOnReturn) {
            this.preventDefault(event)
            this.toggleControls()
          }
          break
        case 27: // Esc
          if (this.options.closeOnEscape) {
            this.close()
            // prevent Esc from closing other things
            event.stopImmediatePropagation()
          }
          break
        case 32: // Space
          if (this.options.toggleSlideshowOnSpace) {
            this.preventDefault(event)
            this.toggleSlideshow()
          }
          break
        case 37: // Left
          if (this.options.enableKeyboardNavigation) {
            this.preventDefault(event)
            this.prev()
          }
          break
        case 38: // Up
          if (this.options.enableKeyboardNavigation) {
            this.preventDefault(event)
            this.nextSlides()
          }
          break
        case 39: // Right
          if (this.options.enableKeyboardNavigation) {
            this.preventDefault(event)
            this.next()
          }
          break
        case 40: // Down
          if (this.options.enableKeyboardNavigation) {
            this.preventDefault(event)
            this.prevSlides()
          }
          break
      }
    },

    handleClick: function (event) {
      var options = this.options
      var target = event.target || event.srcElement
      var parent = target.parentNode
      function isTarget (className) {
        return $(target).hasClass(className) ||
        $(parent).hasClass(className)
      }
      if (isTarget(options.toggleClass)) {
        // Click on "toggle" control
        this.preventDefault(event)
        this.toggleControls()
      } else if (isTarget(options.prevClass)) {
        // Click on "prev" control
        this.preventDefault(event)
        this.prev()
      } else if (isTarget(options.nextClass)) {
        // Click on "next" control
        this.preventDefault(event)
        this.next()
      } else if (isTarget(options.closeClass)) {
        // Click on "close" control
        this.preventDefault(event)
        this.close()
      } else if (isTarget(options.playPauseClass)) {
        // Click on "play-pause" control
        this.preventDefault(event)
        this.toggleSlideshow()
      } else if (parent === this.slidesContainer[0]) {
        // Click on slide background
        if (options.closeOnSlideClick) {
          this.preventDefault(event)
          this.close()
        } else if (options.toggleControlsOnSlideClick) {
          this.preventDefault(event)
          this.toggleControls()
        }
      } else if (parent.parentNode &&
        parent.parentNode === this.slidesContainer[0]) {
        // Click on displayed element
        if (options.toggleControlsOnSlideClick) {
          this.preventDefault(event)
          this.toggleControls()
        }
      }
    },

    onclick: function (event) {
      if (this.options.emulateTouchEvents &&
        this.touchDelta && (Math.abs(this.touchDelta.x) > 20 ||
        Math.abs(this.touchDelta.y) > 20)) {
        delete this.touchDelta
        return
      }
      return this.handleClick(event)
    },

    updateEdgeClasses: function (index) {
      if (!index) {
        this.container.addClass(this.options.leftEdgeClass)
      } else {
        this.container.removeClass(this.options.leftEdgeClass)
      }
      if (index === this.num - 1) {
        this.container.addClass(this.options.rightEdgeClass)
      } else {
        this.container.removeClass(this.options.rightEdgeClass)
      }
    },

    handleSlide: function (index) {
      if (!this.options.continuous) {
        this.updateEdgeClasses(index)
      }
      this.loadElements(index)
      if (this.options.unloadElements) {
        this.unloadElements(index)
      }
      this.setTitle(index)
    },

    onslide: function (index) {
      this.index = index
      this.handleSlide(index)
      this.setTimeout(this.options.onslide, [index, this.slides[index]])
    },

    setTitle: function (index) {
      var text = this.slides[index].firstChild.title
      var titleElement = this.titleElement
      if (titleElement.length) {
        this.titleElement.empty()
        if (text) {
          titleElement[0].appendChild(document.createTextNode(text))
        }
      }
    },

    setTimeout: function (func, args, wait) {
      var that = this
      return func && window.setTimeout(function () {
        func.apply(that, args || [])
      }, wait || 0)
    },

    imageFactory: function (obj, callback) {
      var that = this
      var img = this.imagePrototype.cloneNode(false)
      var url = obj
      var backgroundSize = this.options.stretchImages
      var called
      var element
      var title
      function callbackWrapper (event) {
        if (!called) {
          event = {
            type: event.type,
            target: element
          }
          if (!element.parentNode) {
            // Fix for IE7 firing the load event for
            // cached images before the element could
            // be added to the DOM:
            return that.setTimeout(callbackWrapper, [event])
          }
          called = true
          $(img).off('load error', callbackWrapper)
          if (backgroundSize) {
            if (event.type === 'load') {
              element.style.background = 'url("' + url +
                '") center no-repeat'
              element.style.backgroundSize = backgroundSize
            }
          }
          callback(event)
        }
      }
      if (typeof url !== 'string') {
        url = this.getItemProperty(obj, this.options.urlProperty)
        title = this.getItemProperty(obj, this.options.titleProperty)
      }
      if (backgroundSize === true) {
        backgroundSize = 'contain'
      }
      backgroundSize = this.support.backgroundSize &&
        this.support.backgroundSize[backgroundSize] && backgroundSize
      if (backgroundSize) {
        element = this.elementPrototype.cloneNode(false)
      } else {
        element = img
        img.draggable = false
      }
      if (title) {
        element.title = title
      }
      $(img).on('load error', callbackWrapper)
      img.src = url
      return element
    },

    createElement: function (obj, callback) {
      var type = obj && this.getItemProperty(obj, this.options.typeProperty)
      var factory = (type && this[type.split('/')[0] + 'Factory']) ||
        this.imageFactory
      var element = obj && factory.call(this, obj, callback)
      var srcset = this.getItemProperty(obj, this.options.srcsetProperty)
      if (!element) {
        element = this.elementPrototype.cloneNode(false)
        this.setTimeout(callback, [{
          type: 'error',
          target: element
        }])
      }
      if (srcset) {
        element.setAttribute('srcset', srcset)
      }
      $(element).addClass(this.options.slideContentClass)
      return element
    },

    loadElement: function (index) {
      if (!this.elements[index]) {
        if (this.slides[index].firstChild) {
          this.elements[index] = $(this.slides[index])
            .hasClass(this.options.slideErrorClass) ? 3 : 2
        } else {
          this.elements[index] = 1 // Loading
          $(this.slides[index]).addClass(this.options.slideLoadingClass)
          this.slides[index].appendChild(this.createElement(
            this.list[index],
            this.proxyListener
          ))
        }
      }
    },

    loadElements: function (index) {
      var limit = Math.min(this.num, this.options.preloadRange * 2 + 1)
      var j = index
      var i
      for (i = 0; i < limit; i += 1) {
        // First load the current slide element (0),
        // then the next one (+1),
        // then the previous one (-2),
        // then the next after next (+2), etc.:
        j += i * (i % 2 === 0 ? -1 : 1)
        // Connect the ends of the list to load slide elements for
        // continuous navigation:
        j = this.circle(j)
        this.loadElement(j)
      }
    },

    unloadElements: function (index) {
      var i,
        diff
      for (i in this.elements) {
        if (this.elements.hasOwnProperty(i)) {
          diff = Math.abs(index - i)
          if (diff > this.options.preloadRange &&
            diff + this.options.preloadRange < this.num) {
            this.unloadSlide(i)
            delete this.elements[i]
          }
        }
      }
    },

    addSlide: function (index) {
      var slide = this.slidePrototype.cloneNode(false)
      slide.setAttribute('data-index', index)
      this.slidesContainer[0].appendChild(slide)
      this.slides.push(slide)
    },

    positionSlide: function (index) {
      var slide = this.slides[index]
      slide.style.width = this.slideWidth + 'px'
      if (this.support.transform) {
        slide.style.left = (index * -this.slideWidth) + 'px'
        this.move(
          index, this.index > index
            ? -this.slideWidth
            : (this.index < index ? this.slideWidth : 0),
          0
        )
      }
    },

    initSlides: function (reload) {
      var clearSlides,
        i
      if (!reload) {
        this.positions = []
        this.positions.length = this.num
        this.elements = {}
        this.imagePrototype = document.createElement('img')
        this.elementPrototype = document.createElement('div')
        this.slidePrototype = document.createElement('div')
        $(this.slidePrototype).addClass(this.options.slideClass)
        this.slides = this.slidesContainer[0].children
        clearSlides = this.options.clearSlides ||
        this.slides.length !== this.num
      }
      this.slideWidth = this.container[0].offsetWidth
      this.slideHeight = this.container[0].offsetHeight
      this.slidesContainer[0].style.width =
        (this.num * this.slideWidth) + 'px'
      if (clearSlides) {
        this.resetSlides()
      }
      for (i = 0; i < this.num; i += 1) {
        if (clearSlides) {
          this.addSlide(i)
        }
        this.positionSlide(i)
      }
      // Reposition the slides before and after the given index:
      if (this.options.continuous && this.support.transform) {
        this.move(this.circle(this.index - 1), -this.slideWidth, 0)
        this.move(this.circle(this.index + 1), this.slideWidth, 0)
      }
      if (!this.support.transform) {
        this.slidesContainer[0].style.left =
          (this.index * -this.slideWidth) + 'px'
      }
    },

    unloadSlide: function (index) {
      var slide,
        firstChild
      slide = this.slides[index]
      firstChild = slide.firstChild
      if (firstChild !== null) {
        slide.removeChild(firstChild)
      }
    },

    unloadAllSlides: function () {
      var i,
        len
      for (i = 0, len = this.slides.length; i < len; i++) {
        this.unloadSlide(i)
      }
    },

    toggleControls: function () {
      var controlsClass = this.options.controlsClass
      if (this.container.hasClass(controlsClass)) {
        this.container.removeClass(controlsClass)
      } else {
        this.container.addClass(controlsClass)
      }
    },

    toggleSlideshow: function () {
      if (!this.interval) {
        this.play()
      } else {
        this.pause()
      }
    },

    getNodeIndex: function (element) {
      return parseInt(element.getAttribute('data-index'), 10)
    },

    getNestedProperty: function (obj, property) {
      property.replace(
        // Matches native JavaScript notation in a String,
        // e.g. '["doubleQuoteProp"].dotProp[2]'
        /\[(?:'([^']+)'|"([^"]+)"|(\d+))\]|(?:(?:^|\.)([^\.\[]+))/g,
        function (str, singleQuoteProp, doubleQuoteProp, arrayIndex, dotProp) {
          var prop = dotProp || singleQuoteProp || doubleQuoteProp ||
            (arrayIndex && parseInt(arrayIndex, 10))
          if (str && obj) {
            obj = obj[prop]
          }
        }
      )
      return obj
    },

    getDataProperty: function (obj, property) {
      if (obj.getAttribute) {
        var prop = obj.getAttribute('data-' +
          property.replace(/([A-Z])/g, '-$1').toLowerCase())
        if (typeof prop === 'string') {
          if (/^(true|false|null|-?\d+(\.\d+)?|\{[\s\S]*\}|\[[\s\S]*\])$/
              .test(prop)) {
            try {
              return $.parseJSON(prop)
            } catch (ignore) {}
          }
          return prop
        }
      }
    },

    getItemProperty: function (obj, property) {
      var prop = obj[property]
      if (prop === undefined) {
        prop = this.getDataProperty(obj, property)
        if (prop === undefined) {
          prop = this.getNestedProperty(obj, property)
        }
      }
      return prop
    },

    initStartIndex: function () {
      var index = this.options.index
      var urlProperty = this.options.urlProperty
      var i
      // Check if the index is given as a list object:
      if (index && typeof index !== 'number') {
        for (i = 0; i < this.num; i += 1) {
          if (this.list[i] === index ||
            this.getItemProperty(this.list[i], urlProperty) ===
            this.getItemProperty(index, urlProperty)) {
            index = i
            break
          }
        }
      }
      // Make sure the index is in the list range:
      this.index = this.circle(parseInt(index, 10) || 0)
    },

    initEventListeners: function () {
      var that = this
      var slidesContainer = this.slidesContainer
      function proxyListener (event) {
        var type = that.support.transition &&
        that.support.transition.end === event.type
          ? 'transitionend'
          : event.type
        that['on' + type](event)
      }
      $(window).on('resize', proxyListener)
      $(document.body).on('keydown', proxyListener)
      this.container.on('click', proxyListener)
      if (this.support.touch) {
        slidesContainer
          .on('touchstart touchmove touchend touchcancel', proxyListener)
      } else if (this.options.emulateTouchEvents &&
        this.support.transition) {
        slidesContainer
          .on('mousedown mousemove mouseup mouseout', proxyListener)
      }
      if (this.support.transition) {
        slidesContainer.on(
          this.support.transition.end,
          proxyListener
        )
      }
      this.proxyListener = proxyListener
    },

    destroyEventListeners: function () {
      var slidesContainer = this.slidesContainer
      var proxyListener = this.proxyListener
      $(window).off('resize', proxyListener)
      $(document.body).off('keydown', proxyListener)
      this.container.off('click', proxyListener)
      if (this.support.touch) {
        slidesContainer
          .off('touchstart touchmove touchend touchcancel', proxyListener)
      } else if (this.options.emulateTouchEvents &&
        this.support.transition) {
        slidesContainer
          .off('mousedown mousemove mouseup mouseout', proxyListener)
      }
      if (this.support.transition) {
        slidesContainer.off(
          this.support.transition.end,
          proxyListener
        )
      }
    },

    handleOpen: function () {
      if (this.options.onopened) {
        this.options.onopened.call(this)
      }
    },

    initWidget: function () {
      var that = this
      function openHandler (event) {
        if (event.target === that.container[0]) {
          that.container.off(
            that.support.transition.end,
            openHandler
          )
          that.handleOpen()
        }
      }
      this.container = $(this.options.container)
      if (!this.container.length) {
        this.console.log(
          'blueimp Gallery: Widget container not found.',
          this.options.container
        )
        return false
      }
      this.slidesContainer = this.container.find(
        this.options.slidesContainer
      ).first()
      if (!this.slidesContainer.length) {
        this.console.log(
          'blueimp Gallery: Slides container not found.',
          this.options.slidesContainer
        )
        return false
      }
      this.titleElement = this.container.find(
        this.options.titleElement
      ).first()
      if (this.num === 1) {
        this.container.addClass(this.options.singleClass)
      }
      if (this.options.onopen) {
        this.options.onopen.call(this)
      }
      if (this.support.transition && this.options.displayTransition) {
        this.container.on(
          this.support.transition.end,
          openHandler
        )
      } else {
        this.handleOpen()
      }
      if (this.options.hidePageScrollbars) {
        // Hide the page scrollbars:
        this.bodyOverflowStyle = document.body.style.overflow
        document.body.style.overflow = 'hidden'
      }
      this.container[0].style.display = 'block'
      this.initSlides()
      this.container.addClass(this.options.displayClass)
    },

    initOptions: function (options) {
      // Create a copy of the prototype options:
      this.options = $.extend({}, this.options)
      // Check if carousel mode is enabled:
      if ((options && options.carousel) ||
        (this.options.carousel && (!options || options.carousel !== false))) {
        $.extend(this.options, this.carouselOptions)
      }
      // Override any given options:
      $.extend(this.options, options)
      if (this.num < 3) {
        // 1 or 2 slides cannot be displayed continuous,
        // remember the original option by setting to null instead of false:
        this.options.continuous = this.options.continuous ? null : false
      }
      if (!this.support.transition) {
        this.options.emulateTouchEvents = false
      }
      if (this.options.event) {
        this.preventDefault(this.options.event)
      }
    }

  })

  return Gallery
}))
