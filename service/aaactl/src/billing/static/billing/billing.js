(function($, $tc) {

window.billing = {}

billing.api_client = new twentyc.rest.Client("/api/billing");

billing.BillingContact = twentyc.cls.define(
  "BillingContact",
  {
    BillingContact : function() {
      this.elements = {}
      this.elements.payment_method_list = $('.payment_method-listing')
      this.elements.billing_contact_form = $('form.billing_contact')

      this.rest_api_payment_method_list = new twentyc.rest.List(this.elements.payment_method_list);
      this.rest_api_payment_method_list.format_request_url = (url) => {
        let billing_contact_id = this.elements.payment_method_list.data('billing-contact-id');
        return `${url}?billing_contact=${billing_contact_id}`
      }
      this.rest_api_payment_method_list.formatters.updated = fullctl.formatters.datetime;
      this.rest_api_payment_method_list.load()

      this.rest_api_billing_contact_form = new billing.BillingForm(this.elements.billing_contact_form);;
      $(this.rest_api_billing_contact_form).on('api-delete:success', function() {
        document.location.href = "/billing/billing-contacts/";
      });
    }
  }
);

billing.BillingSetup = twentyc.cls.define(
  "BillingSetup",
  {
    BillingSetup : function() {
      this.elements = {}
      this.elements.form = $('form.billing-setup');
      this.elements.section_create_payopt = this.elements.form.find('#form-create-payopt');
      this.elements.section_select_payopt = this.elements.form.find('#form-select-payopt');
      this.elements.button_create_payopt = this.elements.form.find('.toggle-create-payopt');
      this.elements.select_payopt = this.elements.form.find('[name="payment_method"]')

      this.initial_payopt = this.elements.select_payopt.val()

      this.rest_api_form = new billing.BillingForm(this.elements.form);
      this.track_form_changes();
      $(this.rest_api_form).on("api-post:success", function(e, endpoint, sent_data, response) {
        console.log("Got submit success", {e, endpoint, response, sent_data});
        window.processorHandleConfirm(response.first().payment_method_id);
      }.bind(this));
      this.elements.button_create_payopt.click(function() {
        this.toggle_create_payopt();
      }.bind(this));


      this.elements.return_to_dashboard = $('a.return-to-dashbaord');
      this.elements.return_to_dashboard.on('click', (e) => {
        if (this.elements.form.attr('data-submitted') == 'true') {
          this.elements.form.attr('data-submitted', 'false');
        } else if (this.changed) {
          const conrimation = confirm("Are you sure you want to close this modal? Any unsaved changes will be lost.");
          if (!conrimation) {
            e.preventDefault();
            return;
          }
        }
      })
    },

    track_form_changes : function() {
      const billing_contact_form = this.rest_api_form;
      this.changed = false;

      billing_contact_form.element.find('input').on('change', () => {
        this.changed = true;
      });
      $(billing_contact_form).on('api-post:success api-delete:success', function() {
        billing_contact_form.element.attr('data-submitted', 'true');
      })
    },

    toggle_create_payopt : function() {
      if(this.elements.section_create_payopt.is(":visible"))
        this.hide_create_payopt();
      else
        this.show_create_payopt();
    },

    show_create_payopt : function() {
      this.elements.select_payopt.val(0);
      this.elements.section_create_payopt.collapse("show");
      this.elements.section_select_payopt.collapse("hide");
    },

    hide_create_payopt : function() {
      this.elements.select_payopt.val(this.inital_payopt);
      this.elements.section_create_payopt.collapse("hide");
      this.elements.section_select_payopt.collapse("show");
    }
  }
);

billing.BillingForm = $tc.extend(
  "BillingSetupForm",
  {
    BillingSetupForm : function(jq) {
      this.Form(jq);
    },

    payload : function() {
      const payload = this.Form_payload();
      payload["phone_number_country"] = payload["phone_number_0"]
      payload["phone_number"] = payload["phone_number_1"]
      delete payload["phone_number_0"]
      delete payload["phone_number_1"]

      return payload;
    },


    render_error : function(key, errors) {
      if (key == "phone_number") {
        key = "phone_number_1";
      }
      this.Form_render_error(key, errors);
    }
  },
  twentyc.rest.Form
);

})(jQuery, twentyc.cls);
