(function($, $tc, $ctl) {

$ctl.application.Aclctl = $tc.extend(
  "Aclctl",
  {
    Aclctl : function() {
      this.Application("aclctl");
      this.$c.header.app_slug = "prefix";

      this.tool("filter_rules", () => {
        return new $ctl.application.Aclctl.FilterRules();
      });
      this.$t.filter_rules.activate();
      $($ctl.application).trigger("aclctl-ready", [this]);
    }
  },
  $ctl.application.Application
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

      this.$w.list.formatters.row = (row, data) => {
        row.find('a[data-action="edit_filter_rule"]').click(() => {
          this.prompt_edit_filter_rule(row.data("apiobject"))
        });
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
      this.$w.list.load();
      return this.Tool_activate();
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

      if(filter_rule) {
        form.fill(filter_rule)
        form.form_action = filter_rule.id
        form.method = "PUT";
        title = "Edit Filter Rule"
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
    ModalFilterRuleConfig: function(peer) {
      this.peer = peer;
      var form = new $ctl.application.Aclctl.FilterRuleTemplatePreview(
        $ctl.template('filter_rule_config'),
        peer,//peer ? {id:peer.device_id} : fullctl.peerctl.port_object().device,
        "test",//fullctl.peerctl.$t.peering_lists.$w.port_device_template.element.val(),
        peer//peer
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
    FilterRuleTemplatePreview: function(jq, device, type, peer) {
      this.peer = peer;
      this.device = device;
      this.TemplatePreview(jq, $ctl.application.Aclctl.ModalFilterTemplateSelect, type);
    },

    preview_payload: function() {
      var payload = {
        type: this.type,
        device: this.device.id
      }

      if(this.peer) {
        payload.member = this.peer.id;
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
      return {"test": "123"};
    }
  },
  $ctl.TemplateSelect
)

$(document).ready(function() {
  $ctl.aclctl = new $ctl.application.Aclctl();

  $('[data-element="device_config"]').click(()=>{
    new $ctl.application.Aclctl.ModalFilterRuleConfig();
  });
});

})(jQuery, twentyc.cls, fullctl);
