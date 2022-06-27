(function($, $tc, $ctl) {
$ctl.application.Aclctl.Settings = $tc.extend(
  "Settings",
  {
    Settings : function() {
      this.urlparam = "edit-filter-rule-template"
      this.Tool("settings");
    },

    format_request_url : function(url) {
      return url;
    },

    menu : function() {
      var menu = this.Tool_menu();

      this.widget("filter_rule_templates", ($e) => {
        return new twentyc.rest.List(
          this.template("filter_rule_templates", this.$e.menu.find('.filter_rule_templates'))
        );
      })

      this.$w.filter_rule_templates.formatters.row = (row, data) => {
        row.click(() =>{
          this.edit_filter_rule_template(data);
        });
      };

      this.$w.filter_rule_templates.format_request_url = (url) => {
        return url;
      };

      menu.find('[data-element="button_add_filter_rule_template"]').click(()=>{
        this.create_filter_rule_template();
      });

      menu.find('[data-element="button_general_settings"]').click(()=>{
        this.general_settings();
      });

      return menu;
    },

    sync : function() {
      var namespace = "filter_rule."+fullctl.org.id;
      this.$e.menu.find('[data-element="button_add_filter_rule_template"]').grainy_toggle(namespace, "c");
      this.$e.menu.find('[data-element="button_general_settings"]').hide();

      this.$w.filter_rule_templates.load();
    },

    unload_dialog : function() {
      this.$e.body.empty();
    },

    general_settings : function() {
      var dialog = this.custom_dialog("General settings for "+ix.name);
      var form = new twentyc.rest.Form(
        this.template("form_general_settings", dialog)
      );
      form.format_request_url = this.format_request_url;
      form.fill(ix);

      $(form).on("api-write:success", ()=>{
        $ctl.aclctl.refresh().then(()=>{
          $ctl.aclctl.select_ix(ix.id);
        });
      });
    },


    create_filter_rule_template : function() {

      var dialog = this.custom_dialog('Create configuration template');

      var rs_wiz = new $ctl.widget.Wizard(this.template("filter_rule_template_wizard", dialog));
      var form = new twentyc.rest.Form(
        this.template("form_filter_rule_template_page", rs_wiz.element.find('.rs-form'))
      );
      var button_delete = form.element.find('[data-element="rs_delete"]');

      var form_defaults = {
        type: "cisco-nexus"
      };

      $.get(form.element.find('[name="body"]').data("api-base")).then((response) => {
        form.fill({body: response.responseText})
      });

      form.format_request_url = this.format_request_url;
      form.reset();
      form.fill(form_defaults);

      button_delete.find('span.label').text('Back');
      button_delete.click(() => { rs_wiz.set_step(1); form.reset(); form.fill(form_defaults) });


      $(form).on("api-write:success", (ev, e, payload) => {
        fullctl.aclctl.page('overview');
        this.unload_dialog();
      });

    },


    edit_filter_rule_template : function(rule) {
      console.log("editing", rule);

      var form = new twentyc.rest.Form(
        this.template("form_filter_rule_template_page", this.custom_dialog('Edit '+rule.name))
      );
      var button_delete = new twentyc.rest.Button(
        form.element.find('[data-element="filter_rule_template_delete"]')
      );
      button_delete.format_request_url = this.format_request_url
      button_delete.action = rule.id;

      form.form_action = rule.id;
      form.method = "put";
      form.format_request_url = this.format_request_url;


      $(form).on("api-write:before", (ev, e, payload) => {
        payload["id"] = rule.id;
      });


      $(form).on("api-write:success", (ev, e, payload) => {
        fullctl.aclctl.page('overview');
      });

      $(button_delete).on("api-write:success", (ev, e, payload) => {
        fullctl.aclctl.page('overview');
        this.unload_dialog();
      });


      form.fill(rule);

    }

  },
  $ctl.application.Tool
);


$($ctl).on("init_tools", (e, app) => {
  app.tool("settings", () => {
    return new $ctl.application.Aclctl.Settings();
  })

  $('#settings-tab').on('show.bs.tab', () => {
    app.$t.settings.sync();
    app.$t.settings.create_filter_rule_template();
  });
});


})(jQuery, twentyc.cls, fullctl);
