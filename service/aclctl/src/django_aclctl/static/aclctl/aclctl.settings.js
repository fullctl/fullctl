(function($, $tc, $ctl) {
$ctl.application.Aclctl.Settings = $tc.extend(
  "Settings",
  {
    Settings : function() {
      this.urlparam = "edit-filter-rule-template"
      this.Tool("settings");
    },

    format_request_url : function(url) {
      return url.replace(/acl_tag/, fullctl.aclctl.access_control_list_slug());
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

      menu.find('[data-element="button_delete_access_control_list"]').click(()=>{
        this.delete_access_control_list();
      });


      menu.find('[data-element="button_create_access_control_list"]').click(()=>{
        this.create_access_control_list();
      });


      return menu;
    },

    sync : function() {
      var namespace = "filter_rule."+fullctl.org.id;
      this.$e.menu.find('[data-element="button_add_filter_rule_template"]').grainy_toggle(namespace, "c");

      this.$w.filter_rule_templates.load();
      this.general_settings();
    },

    unload_dialog : function() {
      this.$e.body.empty();
    },

    general_settings : function() {
      var access_control_list = fullctl.aclctl.access_control_list_object();
      if(!access_control_list)
        return;
      var dialog = this.custom_dialog("Settings for "+access_control_list.name);
      var form = new twentyc.rest.Form(
        this.template("form_general_settings", dialog)
      );
      form.format_request_url = this.format_request_url;
      form.fill(access_control_list);

      $(form).on("api-write:success", ()=>{
        $ctl.aclctl.refresh().then(()=>{
          $ctl.aclctl.select_access_control_list(access_control_list.id);
        });
      });
    },

    create_access_control_list : function() {
      var dialog = this.custom_dialog("Create new list");
      var form = new twentyc.rest.Form(
        this.template("form_create_access_control_list", dialog)
      );

      var slug_field = form.element.find('[name=slug]')

      form.element.find('[name=name]').on("keyup", function() {
        slug_field.val(fullctl.util.slugify($(this).val()));
      });

      form.format_request_url = this.format_request_url;
      $(form).on("api-write:success", (ev, data, r_data, response)=>{
        console.log("response", response, r_data)
        $ctl.aclctl.refresh().then(()=>{
          $ctl.aclctl.select_access_control_list(response.first().id);
          fullctl.aclctl.show_page('overview');
          fullctl.aclctl.page('overview');
        });
      });
    },


    delete_access_control_list: function() {
      var access_control_list = $ctl.aclctl.access_control_list_object();
      var dialog = this.custom_dialog("Delete "+access_control_list.name);

      var form = this.template("form_delete_access_control_list", dialog);
      var button = new twentyc.rest.Button(
        form.find('[data-element="button_delete_access_control_list_proceed"]')
      );

      button.action = access_control_list.slug;
      $(button).on("api-write:success", () => {
        $ctl.aclctl.refresh().then(() => {
          $ctl.aclctl.unload_access_control_list(access_control_list.id);
          $ctl.aclctl.select_access_control_list();
          if ($ctl.aclctl.get_page("overview").css("display") != "none")
            $ctl.aclctl.page("overview");
        });
      });

      form.find('.access_control_list-name').text(access_control_list.name);
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
    app.$t.settings.general_settings();
  });
});


})(jQuery, twentyc.cls, fullctl);
