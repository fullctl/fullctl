(function($, $tc, $ctl) {
$ctl.application.Aclctl.AccessControlLists = $tc.extend(
  "AccessControlLists",
  {
    AccessControlLists : function() {
      this.Tool("access_control_lists");
    },

    init : function() {
      this.delete_selected_button = this.$t.button_delete_selected;
      this.widget("list", ($e) => {
        return new $ctl.widget.SelectionList(
          this.template("list", this.$e.body),
          $(this.delete_selected_button)
        );
      });

      this.$w.list.formatters.row = (row, data) => {
        row.find('a[data-action="edit_access_control_list"]').click(() => {
          this.edit_access_control_list(row.data("apiobject"))
        });

        row.find('a[data-action="view_all_filter_rules"]').click(() => {
          fullctl.aclctl.page('filter-rules');
          fullctl.aclctl.$t.filter_rules.view_access_control_list_filter_rules(row.data("apiobject"));
        });
      };

      // update filter rule access control list select on acl delete
      $(this.$w.list).on("api-delete:success", (e, ep, data) => {
        fullctl.aclctl.unload_access_control_list(data.id);
        fullctl.aclctl.sync_access_control_lists();
      });
    },

    menu : function() {
      var menu = this.Tool_menu();

      menu.find('[data-element="button_add_access_control_list"]').click(() => {
        this.create_access_control_list();
      });

      $(this.delete_selected_button).insertBefore(menu.find('[data-element="button_add_access_control_list"]'));

      $(this.delete_selected_button).click(() => {
        if (confirm("Remove selected Access Control Lists?")) {
          this.$w.list.delete_selected_list("slug");
        }
      });

      return menu;
    },

    create_access_control_list : function() {
      return new $ctl.application.Aclctl.ModalAccessControlLists();
    },

    edit_access_control_list : function(access_control_list) {
      return new $ctl.application.Aclctl.ModalAccessControlLists(access_control_list);
    },

    sync : function() {
      var namespace = "filter_rule."+fullctl.org.id;
      this.$e.menu.find('[data-element="button_add_filter_rule_template"]').grainy_toggle(namespace, "c");

      this.$w.list.load();
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

  },
  $ctl.application.Tool
);

$ctl.application.Aclctl.ModalAccessControlLists = $tc.extend(
  "ModalAccessControlLists",
  {
    ModalAccessControlLists : function(access_control_list) {
      var form = this.form = new twentyc.rest.Form(
        $ctl.template("form_access_control_lists")
      );

      var modal = this;
      var title = "Add Access Control List"

      var slug_field = form.element.find('[name=slug]')

      form.element.find('[name=name]').on("keyup", function() {
        slug_field.val(fullctl.util.slugify($(this).val()));
      });

      if(access_control_list) {
        form.fill(access_control_list)
        form.form_action = access_control_list.slug
        form.method = "PUT";
        title = "Edit Access Control List"
      }

      $(this.form).on("api-write:success", function(event, endpoint, payload, response) {
          fullctl.aclctl.sync_access_control_lists();
          fullctl.aclctl.$t.access_control_lists.$w.list.load();
          modal.hide();
          if ($ctl.aclctl.get_page("filter-rules").css("display") == "none")
            $ctl.aclctl.show_page("filter-rules");
        }
      );

      this.Modal("save_right", title, form.element);
      form.wire_submit(this.$e.button_submit);
    }
  },
  $ctl.application.Modal
)


$($ctl).on("init_tools", (e, app) => {
  app.tool("access_control_lists", () => {
    return new $ctl.application.Aclctl.AccessControlLists();
  })

  $('#tab-access-control-lists').on('show.bs.tab', () => {
    app.$t.access_control_lists.sync();
  });
});


})(jQuery, twentyc.cls, fullctl);
