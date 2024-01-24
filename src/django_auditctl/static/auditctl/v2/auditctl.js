(function($, $tc, $ctl) {

$ctl.application.Auditctl = $tc.extend(
  "Auditctl",
  {
    Auditctl : function() {
      this.Application("auditctl");

      this.tool("viewer", () => {
        return new $ctl.application.Auditctl.EventViewer();
      });

      this.autoload_page();
    },

    /**
     * Parses the autoload parameters to determien whether
     * or not autloading is enabled for the provided page.
     *
     * Will also parse arguments into named attribtes and return
     * them in an object literal.
     *
     * TODO: move to fullctl/fullctl
     * @method autoload_enabled
     * @param {String} page page/tab name
     * @param {Function} validate_arg function to validate argument values
     * @param {Array} names attribute names
     */

    autoload_enabled : function(page, validate_arg, names) {
      if(!this.autoload_args || this.autoload_args[0] != page) {
        return null;
      }

      var valid = false;
      var arg, autoload = {}

      for(var i = 1; i < this.autoload_args.length; i++) {
        arg = this.autoload_arg(i);
        if(validate_arg(arg,i)) {
          valid = true;
          autoload[names[i-1]] = arg;
        }
      }
      if(!valid)
        return null;
      return autoload;
    }

  },
  $ctl.application.Application
);

/**
 * List widget that can receive websocket updates and add items
 * to the list.
 *
 * TODO: move to fullctl/fullctl
 */

$ctl.application.Auditctl.StreamingList = $tc.extend(
  "StreamingList",
  {
    StreamingList : function($e, streaming_timeout = 600 * 1000) {
      this.streaming_timeout = streaming_timeout;
      this.List($e);

      $($ctl).on("session-expired", () => {
        this.disconnect();
      });

    },

    timeout_handle: null, // Add timeout_handle property to handle streaming mode timeout

    /**
     * insert a new row from object
     *
     * triggers insert:after event
     *
     * @method insert
     * @param {Object} data
     */

    insert : function(data, prepend) {

      var row = this.List_insert(data);

      if(prepend)
        this.list_body.prepend(row);

      return row;

    },

    connect: function() {

      if(this.socket)
        return;

      // Create a WebSocket connection
      async function getWebsocketUrl() {
          const response = await fetch('/event_stream_url/');
          const data = await response.json();
          return data.websocket_url;
      }

      (async () => {
          const websocketUrl = await getWebsocketUrl();
          this.socket = new WebSocket(websocketUrl);

          // Connection opened
          this.socket.addEventListener("open", (event) => {
            console.log("WebSocket connection opened:", event);
            $(this).trigger("websocket:open", [event]);
            $("#indicate-streaming").show();

            // Set up the timeout to automatically disconnect after specified streaming_timeout duration
            clearTimeout(this.timeout_handle);
            this.timeout_handle = setTimeout(() => {
              console.log("Streaming timeout reached. Disconnecting...");
              this.disconnect();
            }, this.streaming_timeout);

            $ctl.notification_manager.info("Stream connected", null, 3);
          });

          // Listen for messages from the server
          this.socket.addEventListener("message", (event) => {
            console.log("Message from server:", event.data);

            // Parse the received message and display it
            const message = JSON.parse(event.data);
            this.insert(message, true);
          });

          // Connection closed
          this.socket.addEventListener("close", (event) => {
            console.log("WebSocket connection closed:", event);
            $("#indicate-streaming").hide();
          });
      })();

    },

    disconnect: function() {
      if(!this.socket)
        return;
      this.socket.close();
      this.socket = null;

      // Clear the timeout when disconnected
      clearTimeout(this.timeout_handle);
      this.timeout_handle = null;

      // untick streaming checkbox
      $('#toggle-streaming').prop('checked', false);
      $ctl.notification_manager.info("Stream disconnected", null, 15);
    },

    send: function(message) {
      if (this.socket && this.socket.readyState === WebSocket.OPEN) {
        // Convert the message object to a JSON string and send it to the server
        const message_json = JSON.stringify(message);
        this.socket.send(message_json);
      } else {
        console.log("WebSocket connection is not open. Cannot send message.");
      }
    }
  },
  twentyc.rest.List
);

/**
 * Event viewer tool
 *
 * @class
 * @extends $ctl.application.Tool
 * @memberOf $ctl.application
 * @name $ctl.application.Auditctl.EventViewer
 * @constructor
 */

$ctl.application.Auditctl.EventViewer = $tc.extend(
  "EventViewer",
  {
    EventViewer : function() {
      this.Tool("viewer");
    },

    init : function() {
      this.widget("list", ($e) => {
        return new $ctl.application.Auditctl.StreamingList(
          this.template("list", this.$e.body)
        );
      });

      let filter_errors_checkbox = $("#filter-errors");
      let filter_ok_checkbox = $("#filter-ok");

      // hitting enter on the search input should trigger a list load

      $("[data-element=event_search]").keypress((e) => {
        if(e.which == 13) {
          this.$w.list.load();
          this.sync_url();
        }
      });

      // changing either checkbox should trigger sync url

      filter_errors_checkbox.change(() => {
        this.$w.list.load();
        this.sync_url();
      });

      filter_ok_checkbox.change(() => {
        this.$w.list.load();
        this.sync_url();
      });

      // find data-element=button_refresh and wire it up to trigger
      // list.load

      let refresh = $("[data-element=button_refresh]");
      refresh.click(() => {
        this.$w.list.load();
        this.sync_url();
      });

      // when the list is reloaded have it also send a filter
      // update to the websocket connection

      $(this.$w.list).on("load:after", () => {
        this.$w.list.send({"filter": this.get_complete_filter_string()});
      });

      $(this.$w.list).on("websocket:open", () => {
        this.$w.list.send({"filter": this.get_complete_filter_string()});
      });

      $(this.$w.list).one("load:after", ()=> {
        if($("#toggle-streaming").is(":checked"))
          this.$w.list.connect();
      })

      // wire toggle-streaming button

      let toggle_streaming = $("#toggle-streaming")
      toggle_streaming.change(() => {
        // check if checkbox is checked
        if(toggle_streaming.is(":checked")) {
          this.$w.list.load().then(() => {
            this.$w.list.connect();
          });
        } else {
          this.$w.list.disconnect();
        }
      });

      // format request url for list loads based on search input

      this.$w.list.format_request_url = (url) => {

        // get text input [data-element="event_search"]

        let search = $("[data-element=event_search]").val();
        let version = $("[data-element=event_version]").val();
        let org_tag = fullctl.org.slug;

        // split search term into ref tag and id

        let parts = search.split("/");
        let ref_tag = parts[0];
        let ref_id = parts.slice(1).join("/");

        // now replace parts in url and return it

        url = url.replace("version", version+"/")
          .replace("org_tag", org_tag+"/")
          .replace("ref_tag", ref_tag+"/")
          .replace("ref_id", ref_id)
          .replace("undefined","")
          .replace(/\/+$/g, "");

        // apply filter paramters

        let filter_errors = $("#filter-errors").is(":checked");
        let filter_ok = $("#filter-ok").is(":checked");

        if(filter_errors || filter_ok) {
          url += "?error="+filter_errors+"&ok="+filter_ok;
        }

        // also update API view button
        this.$e.button_api_view.attr("href", url);

        return url;
      };

      // general row formatting

      this.$w.list.formatters.row = (row, data) => {

        // find data-element=toggle_info and wire it up to show hide the
        // next tr element

        let toggle = row.find("[data-element=toggle_info]");

        toggle.click(() => {
          $(row[1]).toggle();
        });

        // filter button
        let search_input = $("[data-element=event_search]")
        let version = $("[data-element=event_version]").val();
        let filter_button = row.find("[data-element=button_filter]");
        filter_button.click((e) => {
          let filter_value = data.object_id.replace(`${version}/${fullctl.org.slug}/`, "");
          search_input.val(filter_value);
          this.$w.list.load();
          this.sync_url();
          e.stopPropagation();
        });

      };
      // format object id

      this.$w.list.formatters.object_id = (value, data) => {
        let search_id = this.object_id();
        let trimmed = value;
        let object_id_node;
        let url;

        // remove search_id from the beginning of value, so we are only left with the remainder

        trimmed = value.substring(search_id.length).replace(/^\/+/g, "")
        if(!trimmed) {
          // if trimmed is empty, then we are return the tail of the id
          trimmed = value.split("/").slice(-1)[0];
        }

        // if status == error, display the error message

        if(data.status=="error") {
          object_id_node = $("<span>").text(trimmed);
          let error_node = $("<span>").addClass("text-danger").text(" "+data.error.message);
          object_id_node.append(error_node);
          url = data.error.url;
        } else {
          object_id_node = $("<span>").text(trimmed);
          url = data.data.url;
        }

        // add url

        if(url) {
          let link = $("<a>").addClass("component-link").attr("href", url).text(url);
          object_id_node.append(link)

          // clicking the link should stop propagating the default event

          link.click((e) => {
            e.stopPropagation();
          });
        }

        return object_id_node;

      };

      // format data / error content

      this.$w.list.formatters.data = (value, data) => {
        let content;
        if(data.status=="ok") {
          data.data.created = data.created;
          content = JSON.stringify(data.data, null, 2);
        } else {
          data.error.created = data.created;
          content = JSON.stringify(data.error, null, 2)
        }
        return $("<div>").text(content);
      };

      // format status to be a badge

      this.$w.list.formatters.status = (value, data) => {
        let badge = $("<span>").addClass("badge");
        if(data.status=="ok") {
          badge.addClass("bg-success");
        } else if(data.status=="error") {
          badge.addClass("bg-danger");
        }
        return badge.text(data.status);
      };

      // format crrated date to human readable date time
      // including seconds but not microseconds

      this.$w.list.formatters.created = fullctl.formatters.datetime;

      this.$w.list.load();
    },

    sync_url: function(id) {

      let filter_errors = $("#filter-errors").is(":checked");
      let filter_ok = $("#filter-ok").is(":checked");
      let filters = "";

      // only if either are checked do we need to build a filter for the state

      if(filter_errors || filter_ok) {
        filters = "&error="+filter_errors+"&ok="+filter_ok;
      }

      window.history.pushState({}, '', "?q=" + $("[data-element=event_search]").val() + filters);
    },

    /**
     * Returns the object id for the current search
     *
     * This will take into account the selected version, the current org and the id search term
     *
     * @method object_id
     * @return {String} object id
     */

    object_id : function() {
      let version = $("[data-element=event_version]").val();
      let org = fullctl.org.slug;
      let id = $("[data-element=event_search]").val();
      return [version, org, id].join("/");
    },

    get_complete_filter_string : function() {
        // get text input [data-element="event_search"]

        let search = $("[data-element=event_search]").val();
        let version = $("[data-element=event_version]").val();
        let org_tag = fullctl.org.slug;

        // split search term into ref tag and id

        let parts = search.split("/");
        let ref_tag = parts[0];
        let ref_id = parts.slice(1).join("/");

        return `${version}/${org_tag}/${ref_tag}/${ref_id}`.replace(/\/+$/g, "");
    }
  },

  $ctl.application.Tool
)

$(document).ready(function() {
  $ctl.auditctl = new $ctl.application.Auditctl();
});



})(jQuery, twentyc.cls, fullctl);
