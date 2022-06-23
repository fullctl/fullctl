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

      this.select_source_type = new twentyc.rest.Select(form.element.find("#src-type"));

      $(this.select_source_type.element).on("change", () => {
        this.select_prefix_set.load().then(()=>{});
        var v = this.select_source_type.element.val()
        form.element.find('#tgl-src-prefix-set,#tgl-src-prefix').hide();
        form.element.find('#tgl-src-'+v).show();
      });
      this.select_source_type.load(filter_rule ? filter_rule.src_type : null).then() => {
        if(filter_rule && filter_rule.src_type == "prefix-set") {
          this.select_prefix_set.load(filter_rule.src_prefix_set).then(() => {});
        }
      });

      this.select_prefix_set = new twentyc.rest.Select(form.element.find("#src-prefix-set"));


      $(this.form).on(
        "api-write:success",
        function(event, endpoint, payload, response) {
          var data = response.first()
          var list = $ctl.aclctl.$t.filter_rules.$w.list;
          list.load().then(() => {
            if(!data.irr_import) {
              $ctl.aclctl.$t.filter_rules.expand_prefixes(data)
            }
          });
          modal.hide();
        }
      );
      this.Modal("save", title, form.element);
      form.wire_submit(this.$e.button_submit);
    }
  },
  $ctl.application.Modal
)

$(document).ready(function() {
  $ctl.aclctl = new $ctl.application.Aclctl();
});

})(jQuery, twentyc.cls, fullctl);
