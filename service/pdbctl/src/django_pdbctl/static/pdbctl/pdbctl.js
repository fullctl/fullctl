(function($, $tc, $ctl) {
$ctl.application.Pdbctl = $tc.extend(
  "Pdbctl",
  {
    Pdbctl : function() {
      this.Application("pdbctl");
    }
  },
  $ctl.application.ContainerApplication
);

$(document).ready(function() {
  $ctl.pdbctl = new $ctl.application.Pdbctl();
});

})(jQuery, twentyc.cls, fullctl);
