(function($, $tc, $ctl) {

$ctl.application.Aclctl = $tc.extend(
  "Aclctl",
  {
    Aclctl : function() {
      this.Application("aclctl");
      this.$c.header.app_slug = "prefix";

      this.init_container("access_control_list", "access_control_lists");

      this.tool("filter_rules", () => {
        return new $ctl.application.Aclctl.FilterRules();
      });
      this.$t.filter_rules.activate();

      $(this.$c.toolbar.$e.button_create_access_control_list).click(() => {
        fullctl.aclctl.page('settings');
        fullctl.aclctl.$t.settings.create_access_control_list();
      });

      $(this).on("no-containers", () => {
        fullctl.aclctl.hide_page('overview');
        fullctl.aclctl.page('settings');
        fullctl.aclctl.$t.settings.create_access_control_list();
      });

      $($ctl).trigger("init_tools", [this]);
      $($ctl.application).trigger("aclctl-ready", [this]);
    },

    permission_ui : function() {
      let $e = this.$c.toolbar.$e;
      let org = $ctl.org.id;
      $e.button_create_access_control_list.grainy_toggle(`access_control_list.${org}`, "c");
    }
  },
  $ctl.application.ContainerApplication
);

$ctl.application.Aclctl.FilterRules = $tc.extend(
  "FilterRules",
  {
    FilterRules : function() {
      this.Tool("filter_rules");
    },

    init : function() {
      this.widget("list", ($e) => {
        return new twentyc.rest.List(
          this.template("list", this.$e.body)
        );
      })

      $(this.$w.list).on("api-read:before", (ev, ep, data) => {
        data.access_control_list = fullctl.aclctl.access_control_list();
      });


      $('[data-element="filter_rule_config"]').click(()=>{
        new $ctl.application.Aclctl.ModalFilterRuleConfig();
      });

      this.$w.list.formatters.row = (row, data) => {
        row.find('a[data-action="edit_filter_rule"]').click(() => {
          this.prompt_edit_filter_rule(row.data("apiobject"))
        });
      };

      this.$w.list.formatters.src_prefix = (v, data) => {
        if(data.src_type == "prefix")
          return v;

        var n = $('<div>')
        n.append($('<label>').text("PrefixCtl"));
        n.append($('<div>').text(data.src_prefix_set_name));
        return n;
      };

      this.$w.list.formatters.dest_prefix = (v, data) => {
        if(data.dest_type == "prefix")
          return v;

        var n = $('<div>')
        n.append($('<label>').text("PrefixCtl"));
        n.append($('<div>').text(data.dest_prefix_set_name));
        return n;
      };


      this.$w.list.formatters.priority = (v, data) => {
        var n = this.template("priority_inline_edit");
        var input = new twentyc.rest.Input(n.find('input'))
        input.element.val(v);

        input.payload = () => {
          var payload = $.extend({}, data);
          payload.priority = input.element.val();
          return payload;
        }

        $(input).on("api-write:success", () => { this.$w.list.load(); });

        input.format_request_url = (url) => {
          return url.replace("/0/", "/"+data.id+"/");
        }

        return input.element;
      };



      this.$w.list.element.find('[data-element="button_add_filter_rule"]').click(() => {
        this.prompt_add_filter_rule();
      });

    },

    prompt_add_filter_rule : function() {
      return new $ctl.application.Aclctl.ModalFilterRule();
    },

    prompt_edit_filter_rule : function(filter_rule) {
      return new $ctl.application.Aclctl.ModalFilterRule(filter_rule);
    },

    menu : function() {
      var menu = this.Tool_menu();

      menu.find('[data-element="button_add_filter_rule"]').click(() => {
        this.prompt_add_filter_rule();
      });
      menu.find('[data-element="button_api_view"]').attr(
        "href", this.$w.list.base_url + "/?pretty"
      )
      return menu;
    },

    activate : function() {
      return this.Tool_activate();
    },

    sync : function() {

      this.$w.list.load();
    }
  },
  $ctl.application.Tool
);

$ctl.application.Aclctl.ModalFilterRule = $tc.extend(
  "ModalFilterRule",
  {
    ModalFilterRule : function(filter_rule) {
      var form = this.form = new twentyc.rest.Form(
        $ctl.template("form_filter_rule")
      );

      var modal = this;
      var title = "Add Filter Rule"

      $(form).on("api-write:before", function(ev,ep,data,method) {
        data.access_control_list = fullctl.aclctl.access_control_list();
      });

      if(filter_rule) {
        form.fill(filter_rule)
        form.form_action = filter_rule.id
        form.method = "PUT";
        title = "Edit Filter Rule"
      }

      this.select_source_type = new twentyc.rest.Select(form.element.find("#src-type"));

      $(this.select_source_type.element).on("change", () => {
        this.select_prefix_set.load().then(()=>{});
        var v = this.select_source_type.element.val()
        form.element.find('#tgl-src-prefix-set,#tgl-src-prefix').hide();
        form.element.find('#tgl-src-'+v).show();
      });
      this.select_source_type.load(filter_rule ? filter_rule.src_type : null).then(() => {
      });

      this.select_prefix_set = new twentyc.rest.Select(form.element.find("#src-prefix-set"));

      if(filter_rule && filter_rule.src_type == "prefix-set") {
        this.select_prefix_set.load(filter_rule.src_prefix_set);
        form.element.find('#tgl-src-prefix').hide();
        form.element.find('#tgl-src-prefix-set').show();
      }


      this.select_dest_type = new twentyc.rest.Select(form.element.find("#dest-type"));

      $(this.select_dest_type.element).on("change", () => {
        this.select_dest_prefix_set.load().then(()=>{});
        var v = this.select_dest_type.element.val()
        form.element.find('#tgl-dest-prefix-set,#tgl-dest-prefix').hide();
        form.element.find('#tgl-dest-'+v).show();
      });
      this.select_dest_type.load(filter_rule ? filter_rule.dest_type : null).then(() => {
      });

      this.select_dest_prefix_set = new twentyc.rest.Select(form.element.find("#dest-prefix-set"));

      if(filter_rule && filter_rule.dest_type == "prefix-set") {
        this.select_dest_prefix_set.load(filter_rule.dest_prefix_set);
        form.element.find('#tgl-dest-prefix').hide();
        form.element.find('#tgl-dest-prefix-set').show();
      }



      $(this.form).on(
        "api-write:success",
        function(event, endpoint, payload, response) {
          var data = response.first()
          var list = $ctl.aclctl.$t.filter_rules.$w.list;
          list.load();
          modal.hide();
        }
      );
      this.Modal("save", title, form.element);
      form.wire_submit(this.$e.button_submit);
    }
  },
  $ctl.application.Modal
)

$ctl.application.Aclctl.ModalFilterRuleConfig = $tc.extend(
  "ModalFilterRuleConfig",
  {
    ModalFilterRuleConfig: function() {
      console.log($ctl.template('filter_rule_config'));
      var form = new $ctl.application.Aclctl.FilterRuleTemplatePreview(
        $ctl.template('filter_rule_config'),
        $('[data-element="filter_rule_config_template"]').val(),
      );

      this.Modal("save_lg", "Filter Rule Config", form.element);
      this.$e.button_submit.text("Copy to clipboard").click(()=>{
        form.editor.select();
        document.execCommand("copy");
        this.hide();
      });
      //form.wire_submit(this.$e.button_submit);
    }
  },
  $ctl.application.Modal
);

$ctl.application.Aclctl.FilterRuleTemplatePreview = $tc.extend(
  "FilterRuleTemplatePreview",
  {
    FilterRuleTemplatePreview: function(jq, type) {
      this.type = type;
      console.log(type);
      this.TemplatePreview(jq, $ctl.application.Aclctl.ModalFilterTemplateSelect, type);
    },

    format_request_url : function(url) {
      return url.replace(/acl_tag/g, fullctl.aclctl.access_control_list_slug()).replace(/\/\/$/,"/");
    },

    preview_payload: function() {
      var payload = {
        type: this.type,
        tmpl_id: this.tmpl_id,
      }
      return payload;
    }
  },
  $ctl.TemplatePreview
)

$ctl.application.Aclctl.ModalFilterTemplateSelect = $tc.extend(
  "ModalFilterTemplateSelect",
  {
    load_params : function() {
      return {"type": $('[data-element="filter_rule_config_template"]').val()};
    }
  },
  $ctl.TemplateSelect
)

$(document).ready(function() {
  $ctl.aclctl = new $ctl.application.Aclctl();

});

})(jQuery, twentyc.cls, fullctl);
