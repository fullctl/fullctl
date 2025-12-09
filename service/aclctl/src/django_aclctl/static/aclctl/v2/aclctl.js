(function($, $tc, $ctl) {

$ctl.application.Aclctl = $tc.extend(
  "Aclctl",
  {
    Aclctl : function() {
      this.Application("aclctl");
      this.$c.header.app_slug = "prefix";

      // v2 - move acl select to header
      this.acls = {}

      this.$c.header.widget("acl_dropdown", ($e) => {
        let w = new twentyc.rest.List($('.org-select'));
        $(w).on("insert:after", (e, row, data) => {
          row.attr('data-id', data.id);
          row.click(() => {
            this.select_acl(data.id)
          })
          this.acls[data.id] = data;
        });

        $(w.element).find('[data-element="button_create_acl"]').click(() => {
          this.page('access-control-lists');
          this.$t.access_control_lists.create_access_control_list();
        })

        return w;
      });

      this.$c.header.$w.acl_dropdown.load();

      $(this.$c.header.$w.acl_dropdown).one("load:after", ()=> {
        this.select_acl(this.preselect_acl);
      });

      $(this.$c.header.$w.acl_dropdown).on("load:after", ()=> {
        if(Object.keys(this.acls).length == 0) {
          $(this).trigger("no-containers", []);
        }
      });

      this.tool("filter_rules", () => {
        return new $ctl.application.Aclctl.FilterRules();
      });
      this.$t.filter_rules.activate();

      $($ctl).trigger("init_tools", [this]);
      $($ctl.application).trigger("aclctl-ready", [this]);

      // v2 - no containers logic
      $(this).on("no-containers", () => {
        this.hide_page('filter-rules');
        this.page('access-control-lists');
        this.$t.access_control_lists.create_access_control_list();
      });

    },

    permission_ui : function() {
      let $e = this.$c.toolbar.$e;
      let org = $ctl.org.id;
      $e.button_create_access_control_list.grainy_toggle(`access_control_list.${org}`, "c");
    },

    // v2 - update dropdown on selecting access control list
    select_acl : function(id) {
      let dropdown = this.$c.header.$w.acl_dropdown.list_body;
      dropdown.find('[data-selected]').removeAttr('data-selected');
      if(id) {
        dropdown.find(`[data-id="${id}"]`).attr("data-selected", "");
      } else {
        id = dropdown.find('.acl-item').first().attr("data-id");
        dropdown.find('.acl-item').first().attr("data-selected", "")
      }

      let dropdown_header = this.$c.header.$w.acl_dropdown.list_head;
      dropdown_header.find(".acl-dropdown-label").text(
        dropdown.find("[data-selected]").text()
      );

      this.sync();
      this.sync_url(id);
    },

    unload_access_control_list : function(id) {
      delete this.acls[id];
    },

    access_control_list : function() {
      return this.$c.header.$w.acl_dropdown.list_body.find('[data-selected]').data("id");
    },

    access_control_list_object : function() {
      let acl_id = this.$c.header.$w.acl_dropdown.list_body.find('[data-selected]').data("id");
      return this.acls[acl_id];
    },

    access_control_list_slug : function() {
      let acl_id = this.$c.header.$w.acl_dropdown.list_body.find('[data-selected]').data("id");
      return this.acls[acl_id].slug;
    },

    // v2 - update url
    sync_url: function(id) {
      var ix = this.acls[id];
      var url = new URL(window.location)
      if(!ix) {
        url.pathname = `/${fullctl.org.slug}/`
      } else {
        url.pathname = `/${fullctl.org.slug}/${ix.slug}/`
      }
      window.history.pushState({}, '', url);
    },

    // v2 - update acls in application
    sync_access_control_lists : function() {
      this.$c.header.$w.acl_dropdown.load();
      $(this.$c.header.$w.acl_dropdown).one("load:after", ()=> {
        this.select_acl();
      });
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
      this.delete_selected_button = this.$t.button_delete_selected;
      this.widget("list", ($e) => {
        return new $ctl.widget.SelectionList(
          this.template("list", this.$e.body),
          $(this.delete_selected_button)
        );
      })

      $(this.$w.list).on("api-read:before", (ev, ep, data) => {
        data.access_control_list = fullctl.aclctl.access_control_list();
      });


      $('[data-element="filter_rule_config"]').click(()=>{
        new $ctl.application.Aclctl.ModalFilterRuleConfig();
      });

      $('[data-element="button_api_view"]').attr(
        "href", this.$w.list.base_url + "/?pretty"
      )

      this.$w.list.formatters.row = (row, data) => {
        row.find('a[data-action="edit_filter_rule"]').click(() => {
          this.prompt_edit_filter_rule(row.data("apiobject"))
        });
      };

      this.$w.list.formatters.src_type = (v, data) => {
        if(v == "prefix")
          return "Prefix";
        return "PrefixCtl";
      };

      this.$w.list.formatters.dest_type = (v, data) => {
        if(v == "prefix")
          return "Prefix";
        return "PrefixCtl";
      };

      this.$w.list.formatters.src_prefix = (v, data) => {
        if(data.src_type == "prefix")
          return v;
        return data.src_prefix_set_name
      };

      this.$w.list.formatters.dest_prefix = (v, data) => {
        if(data.dest_type == "prefix")
          return v;
        return data.dest_prefix_set_name
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
    },

    prompt_add_filter_rule : function() {
      return new $ctl.application.Aclctl.ModalFilterRule();
    },

    prompt_edit_filter_rule : function(filter_rule) {
      return new $ctl.application.Aclctl.ModalFilterRule(filter_rule);
    },

    view_access_control_list_filter_rules : function(access_control_list) {
      fullctl.aclctl.select_acl(access_control_list.id);
    },

    menu : function() {
      var menu = this.Tool_menu();

      menu.find('[data-element="button_add_filter_rule"]').click(() => {
        this.prompt_add_filter_rule();
      });

      $(this.delete_selected_button).insertBefore(menu.find('[data-element="button_add_filter_rule"]'));

      $(this.delete_selected_button).click(() => {
        if (confirm("Remove selected Filter Rules?")) {
          this.$w.list.delete_selected_list();
        }
      });
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
      this.Modal("save_right", title, form.element);
      form.wire_submit(this.$e.button_submit);
    }
  },
  $ctl.application.Modal
)

$ctl.application.Aclctl.ModalFilterRuleConfig = $tc.extend(
  "ModalFilterRuleConfig",
  {
    ModalFilterRuleConfig: function() {
      let form = new $ctl.application.Aclctl.FilterRuleTemplatePreview(
        $ctl.template('filter_rule_config'),
        $('[data-element="filter_rule_config_template"]').val(),
      );

      this.Modal("save", "Filter Rule Config", form.element);
      this.$e.button_submit.text("Copy to clipboard").click(()=>{
        let code = '';
        form.codeblock.children().each(function() {
          code = code.concat($(this).text(), "\n");
        });
        navigator.clipboard.writeText(code);
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
      this.ConfigPreview(jq, $ctl.application.Aclctl.ModalFilterTemplateSelect, type);
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
  $ctl.ConfigPreview
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
