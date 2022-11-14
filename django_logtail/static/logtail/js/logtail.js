(function($) {
  window.LogTailer = function(baseUrl, updateInterval, timeout, autoScroll, autoPoll) {
    this.baseUrl = baseUrl;
    this.timeout = timeout || (1000 * 60 * 8);
    this.updateInterval = updateInterval || 4000;
    this.autoScroll = autoScroll || false;
    this.autoPoll = autoPoll || true;
    this.requesting = false;
    this.position = 0;
    this.$textElement = $("#log-tail");
  }

  LogTailer.prototype = {

    poll: function(log) {
      this.log = log;
      this.position = 0;
      this.requesting = false;

      if (this.interval) {
        clearInterval(this.interval);
      }
      this.$textElement.text('');

      var thisTailer = this;
      this.interval = setInterval(function() {
        thisTailer.makeRequest();
      }, this.updateInterval);

      // Make a request now to avoid waiting
      thisTailer.makeRequest();
    },

    stop: function() {
      if (this.interval) {
        clearInterval(this.interval);
      }
    },

    makeRequest: function() {
      if (!this.requesting && this.autoPoll) {
        this.requesting = true;

        var fullUrl = this.baseUrl + this.log + "/" + this.position + "/",
            thisTailer = this;

        $.getJSON(fullUrl, function(data) {
          thisTailer.handleResponse(data);
        });
      }
    },

    handleResponse: function(data) {
      if (this.requesting) {
        this.position = data['ends'];
        this.$textElement.text(this.$textElement.text() + data["data"]);

        if (this.autoScroll) {
          this.scrollBottom();
        }
      }
      this.requesting = false;
    },

    scrollBottom: function() {
      $('html, body').animate(
        {scrollTop: $(document).height()-$(window).height()},
        0
      );
    }
  }
})(django.jQuery);
