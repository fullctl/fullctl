(function($, $tc, $ctl, $rest) {

/*
 * implements tools to query the service bridge
 * to aaactl
 */

$ctl.service_bridge = {}

$ctl.service_bridge.Base = $tc.extend(
  "Base",
  {

    Base:  function(base_url) {
      this.Client(base_url || "/api/")
    },

    org:  function() {
      return $ctl.org.slug;
    }
  },
  $rest.Client
);

$ctl.application.BillingSetup = $tc.define(
  "BillingSetup",
  {
    BillingSetup : function(product) {
      this.product = product;
      this.aaactl = new $ctl.service_bridge.aaactl();
      this.element = $ctl.template("billing-setup");
      this.scanner = ()=> {
        this.aaactl.require_billing_setup(this.product, (b)=> {
          if(!b)
            this.element.detach();
          else
            this.attach_scanner();
        });
      }
      this.attach_scanner();
    },
    attach_scanner : function() {
      $(document).one("visibilitychange", this.scanner);
    }

  }
);

$ctl.application.BillingSetupModal = $tc.extend(
  "BillingSetupModal",
  {
    BillingSetupModal : function(aaactl, product) {
      this.Modal(
        "no_button", "Billing setup required", $ctl.template("billing-setup")
      )

      this.scanner = ()=> {
        console.log("scanning");
        aaactl.require_billing_setup(product, (b)=> {
          console.log("RETURNED", b)
          if(!b)
            this.hide();
          else
            this.attach_scanner();
        });

      }

      this.attach_scanner();
    },

    attach_scanner : function() {
      $(document).one("visibilitychange", this.scanner);
    }

  },
  $ctl.application.Modal
);

$ctl.service_bridge.aaactl = $tc.extend(
  "aaactl",
  {

    /**
     * requires a service subscription for the
     * the specified product.
     *
     * this will set up the subscription if it does not
     * exist
     */

    require_subscription:  function(product) {

      var j, item, org = this.org(), status = {};

      return this.get(`billing/${org}/services/`).then((response) => {
        response.rows((row, i) => {
          for(j = 0; j < row.items.length; j++) {
            item = row.items[j];
            if(item.name.toLowerCase() == product.toLowerCase()) {
              status.found = true
              break;
            }
          }
        });
        if(!status.found) {
          this.subscribe(product)
        }
      });
    },

    /**
     * require billing setup
     *
     * queries aaactl to see if the specified subscription
     * has cost in the current cycle and if it does require
     * the org to have billing setup
     */

    require_billing_setup : function(product, callback) {
      return this.has_service_costs(
        product,
        (b, item, subscription) => {
          if(!b) {
            callback(false);
          } else if(callback) {
            callback(!subscription.pay);
          } else if(!subscription.pay) {
            new $ctl.application.BillingSetupModal(this, product)
          }
        }
      );
    },

    /**
     * determine if the org has costs in a products current
     * subscription cycle
     *
     * `callback` will be called if yes
     */

    has_service_costs : function(product, callback) {
      var j, item, org = this.org();

      return this.get(`billing/${org}/services/`).then((response) => {
        response.rows((row, i) => {
          for(j = 0; j < row.items.length; j++) {
            item = row.items[j];
            if(item.name.toLowerCase() == product.toLowerCase()) {
              return callback(item.cost > 0, item, row);
            }
          }
          callback(false);
        });
      });

    },

    /**
     * subscribe to a service product
     */

    subscribe : function(product) {
      var org = this.org()

      this.post(
        `billing/${org}/subscribe/`,
        { "product": product }
      ).then((response) => {
        console.log("subscribed", response);
      });
    }

  },
  $ctl.service_bridge.Base
);


/** misc events **/

$(twentyc.rest).on("non-field-error", (ev, error, errors, i, node, widget) => {
  var m = error.match(/^Billing setup required to continue using (.+). Please/)
  if(m) {
    errors[i] = null;
    node.prepend(
      new $ctl.application.BillingSetup(m[1]).element
    );
  }
});


})(jQuery, twentyc.cls, fullctl, twentyc.rest);
