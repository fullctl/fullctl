(function($, $tc, $ctl) {
$ctl.application.Devicectl.Settings = $tc.extend(
  "Settings",
  {
    Settings : function() {
      this.urlparam = "edit-rs"
      this.Tool("settings");
    },

    format_request_url : function(url) {
      return url
    },

    menu : function() {
      var menu = this.Tool_menu();

      this.widget("facilities", ($e) => {
        return new twentyc.rest.List(
          this.template("facilities", this.$e.menu.find('.facilities'))
        );
      })

      this.$w.facilities.formatters.row = (row, data) => {
        row.click(() =>{
          this.edit_facility(data);
        });
      };

      this.$w.facilities.format_request_url = (url) => {
        return url;
      };

      menu.find('[data-element="button_add_facility"]').click(()=>{
        this.create_facility();
      });

      /*
      menu.find('[data-element="button_general_settings"]').click(()=>{
        this.general_settings();
      });
      */


      return menu;
    },

    sync : function() {
      var ns = "facility."+fullctl.org.id
      this.$w.facilities.load();
      this.$e.menu.find('[data-element="button_add_facility"]').grainy_toggle(ns, "c");
      // this.$e.menu.find('[data-element="button_delete_ix"]').grainy_toggle(ns, "d");
      //this.$e.menu.find('[data-element="button_general_settings"]').grainy_toggle(ns, "u");
    },

    unload_dialog : function() {
      this.$e.body.empty();
    },

    general_settings : function() {
      return;
      /*
      var dialog = this.custom_dialog("General settings");
      var form = new twentyc.rest.Form(
        this.template("form_general_settings", dialog)
      );
      form.format_request_url = this.format_request_url;
      form.fill(ix);

      $(form).on("api-write:success", ()=>{
        $ctl.devicectl.refresh().then(()=>{
          $ctl.devicectl.select_ix(ix.id);
        });
      });
      */
    },

    wire_slug_auto_input : function(name_field, slug_field) {
      name_field.on("keyup", () => {
        slug_field.val(fullctl.util.slugify(name_field.val()))
      });
    },

    create_facility : function() {

      var dialog = this.custom_dialog('Create facility');

      var rs_wiz = new $ctl.widget.Wizard(this.template("facility_wizard", dialog));
      var rs_pdb_list = new twentyc.rest.List(
        this.template("facility_pdb_list", rs_wiz.element.find('.pdbfacility-list'))
      );
      var form = new twentyc.rest.Form(
        this.template("form_facility_page", rs_wiz.element.find('.rs-form'))
      );
      var button_delete = form.element.find('[data-element="rs_delete"]');

      var pdb_search = rs_wiz.element.find('#pdb-fac-search')
      pdb_search.search = new twentyc.util.SmartTimeout(() => {}, 100);
      $(pdb_search).on('keyup', function(ev) {
        pdb_search.search.set(() => {
          rs_pdb_list.payload = () => {
            return {q: pdb_search.val()}
          }
          rs_pdb_list.load();
        }, 250);

      });

      var form_defaults = {
        rpki_bgp_origin_validation: true,
        graceful_shutdown: true
      };

      rs_pdb_list.format_request_url = this.format_request_url;

      rs_pdb_list.formatters.row = (row, data) => {
        row.find('button').click(() =>{
          data.reference = data.id;
          data.slug = fullctl.util.slugify(data.name);
          form.fill(data);
          rs_wiz.set_step(2);
        });
      };

      this.wire_slug_auto_input(
        form.element.find('#name'),
        form.element.find('#slug')
      );


      $(rs_pdb_list).on("load:after", () => {
        /*
        if(!rs_pdb_list.list_body.find('tr.rs-row').length) {
          rs_wiz.set_step(2);
          button_delete.hide();
        }
        */
      });

      rs_pdb_list.load();

      form.format_request_url = this.format_request_url;
      form.reset();
      form.fill(form_defaults);

      button_delete.find('span.label').text('Back');
      button_delete.click(() => { rs_wiz.set_step(1); form.reset(); form.fill(form_defaults) });


      $(form).on("api-write:success", (ev, data, r_data, response) => {
        $ctl.devicectl.refresh().then(()=>{
          $ctl.devicectl.select_facility(response.first().id);
          fullctl.devicectl.page('overview');
        });
      });

    },


    edit_facility : function(rs) {
      console.log("editing", rs);

      var form = new twentyc.rest.Form(
        this.template("form_facility_page", this.custom_dialog('Edit '+rs.name))
      );
      var button_delete = new twentyc.rest.Button(
        form.element.find('[data-element="rs_delete"]')
      );
      button_delete.format_request_url = this.format_request_url
      button_delete.action = rs.slug;

      form.form_action = rs.slug;
      form.method = "put";
      form.format_request_url = this.format_request_url;

      form.element.find('#reference-is-sot').change(function() {
        console.log("sup", $(this))

        if($(this).prop("checked")) {
          form.element.find('[data-sot-toggled=yes] *').prop("disabled", true);
        } else {
          form.element.find('[data-sot-toggled=yes] *').prop("disabled", false);
        }

      });


      $(form).on("api-write:before", (ev, e, payload) => {
        payload["ix"] = rs.ix;
        payload["id"] = rs.id;
      });

      $(form).on("api-write:success", (ev, data, r_data, response) => {
        $ctl.devicectl.refresh().then(()=>{
          $ctl.devicectl.select_facility(response.first().id);
          fullctl.devicectl.page('overview');
        });
      });

      $(button_delete).on("api-write:success", (ev, e, payload) => {
        $ctl.devicectl.refresh().then(() => {
          $ctl.devicectl.unload_facility(rs.id);
          $ctl.devicectl.select_facility();
          $ctl.devicectl.refresh();
          $ctl.devicectl.page("overview");
        });
      });

      form.fill(rs);
      form.element.find('#reference-is-sot').trigger("change");

    }

  },
  $ctl.application.Tool
);


$($ctl).on("init_tools", (e, app) => {
  app.tool("settings", () => {
    return new $ctl.application.Devicectl.Settings();
  })

  $('#facilities-tab').on('show.bs.tab', () => {
    app.$t.settings.sync();
    app.$t.settings.create_facility();
  });
});



})(jQuery, twentyc.cls, fullctl);
