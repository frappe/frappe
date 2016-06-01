/*
 * blueimp Gallery Vimeo Video Factory JS
 * https://github.com/blueimp/Gallery
 *
 * Copyright 2013, Sebastian Tschan
 * https://blueimp.net
 *
 * Licensed under the MIT license:
 * http://www.opensource.org/licenses/MIT
 */

/* global define, window, document, $f */

;(function (factory) {
  'use strict'
  if (typeof define === 'function' && define.amd) {
    // Register as an anonymous AMD module:
    define([
      './blueimp-helper',
      './blueimp-gallery-video'
    ], factory)
  } else {
    // Browser globals:
    factory(
      window.blueimp.helper || window.jQuery,
      window.blueimp.Gallery
    )
  }
}(function ($, Gallery) {
  'use strict'

  if (!window.postMessage) {
    return Gallery
  }

  $.extend(Gallery.prototype.options, {
    // The list object property (or data attribute) with the Vimeo video id:
    vimeoVideoIdProperty: 'vimeo',
    // The URL for the Vimeo video player, can be extended with custom parameters:
    // https://developer.vimeo.com/player/embedding
    vimeoPlayerUrl: '//player.vimeo.com/video/VIDEO_ID?api=1&player_id=PLAYER_ID',
    // The prefix for the Vimeo video player ID:
    vimeoPlayerIdPrefix: 'vimeo-player-',
    // Require a click on the native Vimeo player for the initial playback:
    vimeoClickToPlay: true
  })

  var textFactory = Gallery.prototype.textFactory ||
                      Gallery.prototype.imageFactory
  var VimeoPlayer = function (url, videoId, playerId, clickToPlay) {
    this.url = url
    this.videoId = videoId
    this.playerId = playerId
    this.clickToPlay = clickToPlay
    this.element = document.createElement('div')
    this.listeners = {}
  }
  var counter = 0

  $.extend(VimeoPlayer.prototype, {
    canPlayType: function () {
      return true
    },

    on: function (type, func) {
      this.listeners[type] = func
      return this
    },

    loadAPI: function () {
      var that = this
      var apiUrl = '//f.vimeocdn.com/js/froogaloop2.min.js'
      var scriptTags = document.getElementsByTagName('script')
      var i = scriptTags.length
      var scriptTag
      var called
      function callback () {
        if (!called && that.playOnReady) {
          that.play()
        }
        called = true
      }
      while (i) {
        i -= 1
        if (scriptTags[i].src === apiUrl) {
          scriptTag = scriptTags[i]
          break
        }
      }
      if (!scriptTag) {
        scriptTag = document.createElement('script')
        scriptTag.src = apiUrl
      }
      $(scriptTag).on('load', callback)
      scriptTags[0].parentNode.insertBefore(scriptTag, scriptTags[0])
      // Fix for cached scripts on IE 8:
      if (/loaded|complete/.test(scriptTag.readyState)) {
        callback()
      }
    },

    onReady: function () {
      var that = this
      this.ready = true
      this.player.addEvent('play', function () {
        that.hasPlayed = true
        that.onPlaying()
      })
      this.player.addEvent('pause', function () {
        that.onPause()
      })
      this.player.addEvent('finish', function () {
        that.onPause()
      })
      if (this.playOnReady) {
        this.play()
      }
    },

    onPlaying: function () {
      if (this.playStatus < 2) {
        this.listeners.playing()
        this.playStatus = 2
      }
    },

    onPause: function () {
      this.listeners.pause()
      delete this.playStatus
    },

    insertIframe: function () {
      var iframe = document.createElement('iframe')
      iframe.src = this.url
        .replace('VIDEO_ID', this.videoId)
        .replace('PLAYER_ID', this.playerId)
      iframe.id = this.playerId
      this.element.parentNode.replaceChild(iframe, this.element)
      this.element = iframe
    },

    play: function () {
      var that = this
      if (!this.playStatus) {
        this.listeners.play()
        this.playStatus = 1
      }
      if (this.ready) {
        if (!this.hasPlayed && (this.clickToPlay || (window.navigator &&
          /iP(hone|od|ad)/.test(window.navigator.platform)))) {
          // Manually trigger the playing callback if clickToPlay
          // is enabled and to workaround a limitation in iOS,
          // which requires synchronous user interaction to start
          // the video playback:
          this.onPlaying()
        } else {
          this.player.api('play')
        }
      } else {
        this.playOnReady = true
        if (!window.$f) {
          this.loadAPI()
        } else if (!this.player) {
          this.insertIframe()
          this.player = $f(this.element)
          this.player.addEvent('ready', function () {
            that.onReady()
          })
        }
      }
    },

    pause: function () {
      if (this.ready) {
        this.player.api('pause')
      } else if (this.playStatus) {
        delete this.playOnReady
        this.listeners.pause()
        delete this.playStatus
      }
    }

  })

  $.extend(Gallery.prototype, {
    VimeoPlayer: VimeoPlayer,

    textFactory: function (obj, callback) {
      var options = this.options
      var videoId = this.getItemProperty(obj, options.vimeoVideoIdProperty)
      if (videoId) {
        if (this.getItemProperty(obj, options.urlProperty) === undefined) {
          obj[options.urlProperty] = '//vimeo.com/' + videoId
        }
        counter += 1
        return this.videoFactory(
          obj,
          callback,
          new VimeoPlayer(
            options.vimeoPlayerUrl,
            videoId,
            options.vimeoPlayerIdPrefix + counter,
            options.vimeoClickToPlay
          )
        )
      }
      return textFactory.call(this, obj, callback)
    }

  })

  return Gallery
}))
