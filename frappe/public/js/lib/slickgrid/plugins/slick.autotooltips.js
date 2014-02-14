(function ($) {
  // register namespace
  $.extend(true, window, {
    "Slick": {
      "AutoTooltips": AutoTooltips
    }
  });


  function AutoTooltips(options) {
    var _grid;
    var _self = this;
    var _defaults = {
      maxToolTipLength: null
    };

    function init(grid) {
      options = $.extend(true, {}, _defaults, options);
      _grid = grid;
      _grid.onMouseEnter.subscribe(handleMouseEnter);
    }

    function destroy() {
      _grid.onMouseEnter.unsubscribe(handleMouseEnter);
    }

    function handleMouseEnter(e, args) {
      var cell = _grid.getCellFromEvent(e);
      if (cell) {
        var node = _grid.getCellNode(cell.row, cell.cell);
        if ($(node).innerWidth() < node.scrollWidth) {
          var text = $.trim($(node).text());
          if (options.maxToolTipLength && text.length > options.maxToolTipLength) {
            text = text.substr(0, options.maxToolTipLength - 3) + "...";
          }
          $(node).attr("title", text);
        } else {
          $(node).attr("title", "");
        }
      }
    }

    $.extend(this, {
      "init": init,
      "destroy": destroy
    });
  }
})(jQuery);