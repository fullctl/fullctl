(function($, $tc, $ctl) {
$ctl.application.Ixctl.Settings = $tc.extend(
  "Settings",
  {
    Settings : function() {
      this.urlparam = "edit-rs"
      this.Tool("nets");
      this.active_view = null;
      this.activate();
    },

    format_request_url : function(url) {
      return url.replace("ix_tag", fullctl.ixctl.ix_object().slug);
    },

    menu : function() {
      var menu = this.Tool_menu();

      menu.find('[data-element="button_delete_ix"]').click(()=>{
        this.delete_exchange();
      });

      menu.find('[data-element="button_general_settings"]').click(()=>{
        this.general_settings();
      });

      menu.find('[data-element="button_lan_settings"]').click(()=>{
        this.lan_settings();
      });

      menu.find('[data-element="button_traffic_alerts"]').click(()=>{
        this.traffic_alerts();
      });

      return menu;
    },

    sync : function() {
      const exchange = $ctl.ixctl.ix_object();
      if(exchange) {
        this.$e.menu.find('[data-element="button_delete_ix"]').grainy_toggle(exchange.grainy, "d");
        this.$e.menu.find('[data-element="button_general_settings"]').grainy_toggle(exchange.grainy, "u");
        this.$e.menu.find('[data-element="button_lan_settings"]').grainy_toggle(exchange.grainy, "u");

      } else {
        this.$e.menu.find('[data-element="button_delete_exchange"]').hide();
        this.$e.menu.find('[data-element="button_general_settings"]').hide();
        this.$e.menu.find('[data-element="button_lan_settings"]').hide();

      }
      if(this.active_view == "lan_settings") {
        this.lan_settings();
      } else if (this.active_view == "traffic_alerts") {
        this.traffic_alerts();
      } else {
        this.general_settings();
      }
    },

    unload_dialog : function() {
      this.$e.body.empty();
    },

    general_settings : function() {
      this.active_view = "general_settings";
      var ix = $ctl.ixctl.ix_object();
      var dialog = this.custom_dialog("General settings for "+ix.name);
      const form = this.widget("form_general_settings", ($e) => {
        return new twentyc.rest.Form(
          this.template("form_general_settings", dialog)
        );
      })
      form.format_request_url = this.format_request_url;
      form.fill(ix);

      var information_public_view = $(`#public_view`);
      information_public_view.val(ix.public_view.toString());

      $(form).on("api-write:success", ()=>{
        $ctl.ixctl.refresh().then(()=>{
          $ctl.ixctl.select_ix(ix.id);
        });
      });

      $(form).on("api-write:before", (ev, e, data)=> {
        if(data.email_alert_recipients) {
          data.email_alert_recipients = data.email_alert_recipients.split(",");
        } else {
          data.email_alert_recipients = [];
        }
      });
    },

    lan_settings : function() {
      this.active_view = "lan_settings";
      var ix = $ctl.ixctl.ix_object();
      var dialog = this.custom_dialog("LAN settings for "+ix.name);


      // LAN settings

      const form = this.widget("form_lan_settings", ($e) => {
        return new twentyc.rest.Form(
          this.template("form_lan_settings", dialog)
        );
      })
      form.format_request_url = this.format_request_url;
      $(form).on("payload:after", (ev, payload) => {
        // sanitize vlan_id and mtu to null if they are ""
        if (payload.vlan_id == "") {
          payload.vlan_id = null;
        }
        if (payload.mtu == "") {
          payload.mtu = null;
        }
      });
      form.fill(ix);

      // Prefix list

      const prefix_list = this.widget("prefix_list", ($e) => {
        return new twentyc.rest.List(
          this.template("prefix_list", dialog)
        )
      });
      prefix_list.format_request_url = this.format_request_url;
      prefix_list.load();

      // Add Prefix form

      const add_prefix = this.widget("form_add_prefix", ($e) => {
        return new twentyc.rest.Form(
          this.template("form_add_prefix", dialog)
        )
      });
      add_prefix.format_request_url = this.format_request_url;

      $(add_prefix).on("api-write:success", () => {
        prefix_list.load();
        add_prefix.reset();
      });

      $(form).on("api-write:success", ()=>{
        $ctl.ixctl.refresh().then(()=>{
          $ctl.ixctl.select_ix(ix.id);
        });
      });
    },

    traffic_alerts: function() {
      // Load the traffic alert settings page form
      this.active_view = "traffic_alerts";
      var ix = $ctl.ixctl.ix_object();
      var dialog = this.custom_dialog(`Traffic Alert Settings for ${ix.name}`);

      const form = this.widget("form_traffic_alerts", ($e) => {
        return new twentyc.rest.Form(
          this.template("form_traffic_alerts", dialog)
        );
      });

      this.$w.form_traffic_alerts.fill({"traffic_poll_time": Math.round(ix.traffic_poll_time / 60)});

      this.load_traffic_alerts();

      form.format_request_url = this.format_request_url;

      $(form).on("api-write:before", (form, _, data) => {
        // Sanitize the request payload data before sending
        data["ix"] = ix.id;

        if (!data["operator_emails"]) {
          data["operator_emails_max_frequency"] = null;
        }

        if (!data["member_emails"]) {
          data["member_emails_max_frequency"] = null;
        }
      });

      this.$w.form_traffic_alerts.element.find("#edit_member_emails").on("click", (e) => {
        this.handle_member_config(e.target.checked);
      });

      this.$w.form_traffic_alerts.element.find("#edit_operator_emails").on("click", (e) => {
        this.handle_operator_config(e.target.checked);
      });
    },

    handle_operator_config: function(checked) {
      // Handles whether to show or hide the operator config settings
      if (checked) {
        this.$w.form_traffic_alerts.element.find(".operator_emails_config").show();
      } else {
        this.$w.form_traffic_alerts.element.find(".operator_emails_config").hide();
      }
    },

    handle_member_config: function(checked) {
      // Handles whether to show or hide the member config settings
      if (checked) {
        this.$w.form_traffic_alerts.element.find(".member_emails_config").show();
      } else {
        this.$w.form_traffic_alerts.element.find(".member_emails_config").hide();
      }
    },

    load_traffic_alerts: function() {
      // Get the traffic alert config data for the IX
      let url = this.$w.form_traffic_alerts.element.data("api-get-by-ix");
      url = this.format_request_url(url);

      $.ajax({ url })
      .done(({ data }) => {
        const traffic_alert_config = data[0];
        this.$w.form_traffic_alerts.fill(traffic_alert_config);
        this.$w.form_traffic_alerts.base_url = this.$w.form_traffic_alerts.base_url.replace("id", traffic_alert_config.id);
        this.handle_member_config(traffic_alert_config.member_emails);
        this.handle_operator_config(traffic_alert_config.operator_emails);
      })
      .fail(err => {
        if (err.status == 404) {
          // No exisiting data means we are creating a new one
          this.$w.form_traffic_alerts.method = "POST";
          this.$w.form_traffic_alerts.base_url = this.$w.form_traffic_alerts.base_url.replace("id", "");
          this.handle_member_config(false);
          this.handle_operator_config(false);
        }
      });
    },

    delete_exchange : function() {
      var ix = $ctl.ixctl.ix_object();
      var dialog = this.custom_dialog("Delete "+ix.name);

      var form = this.template("form_delete_ix", dialog);
      var button = new twentyc.rest.Button(
        form.find('[data-element="button_delete_ix_proceed"]')
      );

      button.action = ix.slug;
      $(button).on("api-write:success", () => {
        $ctl.ixctl.refresh().then(() => {
          $ctl.ixctl.unload_ix(ix.id);
          $ctl.ixctl.select_ix();
          $ctl.ixctl.page("overview");
        });
      });

      form.find('.ix-name').text(ix.name);
    },
  },
  $ctl.application.Tool
);


$($ctl).on("init_tools", (e, app) => {
  app.tool("settings", () => {
    return new $ctl.application.Ixctl.Settings();
  });

  $('#settings-tab').on('show.bs.tab', () => {
    app.$t.settings.sync();
  });

  if (window.location.hash == "#settings") {
    app.$t.settings.sync();
  }
});



})(jQuery, twentyc.cls, fullctl);
