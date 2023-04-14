(function($, $tc, $ctl) {

$ctl.application.Auditctl = $tc.extend(
  "Auditctl",
  {
    Auditctl : function() {
      this.Application("auditctl");
    }
  },
  $ctl.application.Application
);

$(document).ready(function() {
  $ctl.auditctl = new $ctl.application.Auditctl();
});


})(jQuery, twentyc.cls, fullctl);
