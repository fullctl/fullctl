(function($, $tc, $ctl) {

$ctl.application.Auditctl = $tc.extend(
  "Auditctl",
  {
    Auditctl : function() {
      this.Application("auditctl");

      this.tool("viewer", () => {
        return new $ctl.application.Auditctl.EventViewer();
      });
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

      this.$w.list.format_request_url = (url) => {
        return url.replace("version", "0.1").replace("org_tag", "demo").replace("ref_tag", "config/routeserver").replace("ref_id", "chix/rs0");
      };

      this.$w.list.formatters.data = (value) => {
        if(!value)
          return "";
        return $("<pre>").text(JSON.stringify(value, null, 2));
      };

      this.$w.list.formatters.error = (value) => {
        if(!value)
          return "";
        return $("<pre>").text(JSON.stringify(value, null, 2));
      };

      this.$w.list.load();
    }
  },

  $ctl.application.Tool
)

$(document).ready(function() {
  $ctl.auditctl = new $ctl.application.Auditctl();
});


})(jQuery, twentyc.cls, fullctl);
