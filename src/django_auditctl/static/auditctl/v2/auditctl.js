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
        return new twentyc.rest.List(
          this.template("list", this.$e.body)
        );
      });


      // find data-element=button_refresh and wire it up to trigger
      // list.load

      let refresh = $("[data-element=button_refresh]");
      refresh.click(() => {
        this.$w.list.load();
        this.sync_url();
      });

      this.$w.list.format_request_url = (url) => {

        // get text input [data-element="event_search"]

        let search = $("[data-element=event_search]").val();

        // split by / and take the first 3 elements as version, org_tag, ref_tag
        // then re-combine the remaining elements into ref_id

        let parts = search.split("/");
        let version = parts[0];
        let org_tag = parts[1];
        let ref_tag = parts[2];
        let ref_id = parts.slice(3).join("/");

        // now replace parts in url and return it

        return url.replace("version", version).replace("org_tag", org_tag).replace("ref_tag", ref_tag).replace("ref_id", ref_id);
      };

      this.$w.list.formatters.row = (row, data) => {

        // find data-element=toggle_info and wire it up to show hide the 
        // next tr element

        let toggle = row.find("[data-element=toggle_info]");

        row.find(".primary").click(() => {
          $(row[1]).toggle();
        });
      
      };

      this.$w.list.formatters.data = (value, data) => {
        let content;
        if(data.status=="ok") {
          content = JSON.stringify(data.data, null, 2);
          
        } else {
          content = JSON.stringify(data.error, null, 2)
        }
        return $("<div>").text(content);
      };

      this.$w.list.load();
    },

    sync_url: function(id) {
      window.history.pushState({}, '', "?q=" + $("[data-element=event_search]").val());
    }
  },

  $ctl.application.Tool
)

$(document).ready(function() {
  $ctl.auditctl = new $ctl.application.Auditctl();
});


})(jQuery, twentyc.cls, fullctl);
