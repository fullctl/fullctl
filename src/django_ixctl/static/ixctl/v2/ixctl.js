(function($, $tc, $ctl) {

$ctl.application.Ixctl = $tc.extend(
  "Ixctl",
  {
    Ixctl : function() {
      this.Application("ixctl");

      this.autoload_page();
      this.urlkeys = {}
      this.exchanges = {}
      this.ix_slugs = {}
      this.initial_load = false

      this.$c.header.app_slug = "ix";

      // v2 - move ix select to header
      this.$c.header.widget("ix_dropdown", ($e) => {
        const w = new twentyc.rest.List($('.ix-select'));

        $(w).on("insert:after", (e, row, data) => {
          row.attr('data-id', data.id);
          row.find(".manage-ix").click(() => {
            this.select_ix(data.id);
            fullctl.ixctl.page('settings');
          })
          row.find('[data-field="name"]').click(() => {
            this.select_ix(data.id)
          })
          this.urlkeys[data.id] = data.urlkey;
          this.exchanges[data.id] = data;
          this.ix_slugs[data.id] = data.slug;

          this.permission_ui();
        });

        return w;
      });


      // wire `Set as default` button

      var button_make_default = new twentyc.rest.Button(
        this.$c.header.$e.button_set_default_ix
      );

      // set the url for the button, replacing __ix_slug__ with the slug of the
      // currently selected exchange

      button_make_default.format_request_url = (url) => {
        return url.replace("__ix_slug__", this.ix_slug());
      };

      // on make default success, notify the user

      $(button_make_default).on("api-write:success", (ev, response) => {
        alert("Default IX set successfully");
      });

      // wire import and create ix buttons that are shown when the organization
      // has no exchanges
      const button_import_ix = $("#no-ix-notify [data-element='button_import_exchange']");
      button_import_ix.click(() => {
        this.prompt_import();
      });
      const button_create_ix = $("#no-ix-notify [data-element='button_create_ix']");
      button_create_ix.click(() => {
        this.prompt_create_exchange();
      });

      // load exchanges
      $(this.$c.header.$w.ix_dropdown).one("load:after", (ev, response)=> {
        this.select_ix(this.preselect_ix);
        const num_exchanges = response.content.data.length;

        // if theree are multiple exchanges, toggle elements with
        // data-toggled="multiple-exchanges" visible, otherwise hide them

        if(num_exchanges > 1) {
          $('[data-toggled="multiple-exchanges"]').show();
        } else {
          $('[data-toggled="multiple-exchanges"]').hide();
        }

        // trigger init_tools after ix selected
        $($ctl).trigger("init_tools", [this]);
      });

      this.$c.header.$w.ix_dropdown.load();

      $(this.$c.header.$e.button_create_ix).click(() => {
        this.prompt_create_exchange();
      });

      $(this.$c.header.$e.button_import_ix).click(() => {
        this.prompt_import();
      });

      this.tool("members", () => {
        return new $ctl.application.Ixctl.Members();
      });

      this.tool("member_details", () => {
        return new $ctl.application.Ixctl.MemberDetails();
      });

      this.tool("traffic", () => {
        return new $ctl.application.Ixctl.Traffic();
      });

      // this.tool("metric", () => {
      //   return new $ctl.application.Ixctl.Metric();
      // });

      this.$t.members.activate();
    },


    permission_ui : function() {
      let $e = this.$c.header.$e;
      let ix = this.exchanges[this.ix()];
      let org = $ctl.org.id;

      $e.button_create_ix.grainy_toggle(`ix.${org}`, "c");
      $e.button_import_ix.grainy_toggle(`ix.${org}`, "c");
    },

    ix : function() {
      return this.$c.header.$w.ix_dropdown.list_body.find('[data-selected]').attr('data-id');
    },

    ix_slug : function() {
      return this.ix_slugs[this.ix()];
    },

    ix_object: function() {
      return this.exchanges[this.ix()]
    },

    urlkey : function() {
      return this.urlkeys[this.ix()];
    },

    unload_ix : function(id) {
      delete this.exchanges[id];
      delete this.urlkeys[id];
      delete this.ix_slugs[id];
    },


    select_ix : function(id) {
      let dropdown = this.$c.header.$w.ix_dropdown.list_body;
      dropdown.find('[data-selected]').removeAttr('data-selected');
      if(id) {
        dropdown.find(`[data-id="${id}"]`).attr("data-selected", "");
      } else {
        id = dropdown.find('.ix-item').first().attr("data-id");
        dropdown.find('.ix-item').first().attr("data-selected", "")
      }

      let dropdown_header = this.$c.header.$w.ix_dropdown.list_head;
      dropdown_header.find(".ix-dropdown-label").text(
        dropdown.find("[data-selected]").text()
      );

      const ix = this.exchanges[id];
      if(!ix) {
        $('#no-ix-notify').show();
        $('#app-pages').hide();
        return;
      } else {
        $('#no-ix-notify').hide();
        $('#app-pages').show();
        if(!ix.verified) {
          $('#ix-unverified-notify').show();
        } else {
          $('#ix-unverified-notify').hide();
        }
      }


      this.sync();
      this.sync_url(id);
      $ctl.ixctl.$t.traffic.sync();
      // $ctl.ixctl.$t.metric.sync();
    },

    sync_url: function(id) {
      const url = new URL(window.location)
      const ix = this.exchanges[id];
      url.pathname = ix ? `/${fullctl.org.slug}/${ix.slug}/` : `/${fullctl.org.slug}/`;

      window.history.pushState({}, '', url);
    },

    refresh : function() {
      return this.refresh_select_ix();
    },

    refresh_select_ix : function() {
      return this.$c.header.$w.ix_dropdown.load();
    },

    prompt_import : function(first_import) {
      return new $ctl.application.Ixctl.ModalImport(first_import);
    },

    prompt_create_exchange : function() {
      return new $ctl.application.Ixctl.ModalCreateIX();
    },

  },
  $ctl.application.Application
);

$ctl.application.Ixctl.ModalImport = $tc.extend(
  "ModalImport",
  {
    ModalImport : function(first_import) {
      var form = this.form = new twentyc.rest.Form(
        $ctl.template("form_import")
      );

      var modal = this;

      if(first_import)
        form.element.find('.first-import').show();

      $(this.form).on("api-write:success", function(event, endpoint, payload, response) {
        $ctl.ixctl.refresh().then(
          () => { $ctl.ixctl.select_ix(response.content.data[0].id) }
        );
        modal.hide();
      });
      this.Modal("continue", "Import from PeeringDB", form.element);
      form.element.find("#pdb_ix_id").select2({
        dropdownParent : $(".modal")[0],
        ajax: {
          url: '/autocomplete/pdb/ix',
          dataType: 'json',
        },
        width: '20em'
      });
      $(document).on('select2:open', () => {
        document.querySelector('.select2-search__field').focus();
      });

      form.wire_submit(this.$e.button_submit);
    }
  },
  $ctl.application.Modal
);




$ctl.application.Ixctl.ModalCreateIX = $tc.extend(
  "ModalCreateIX",
  {
    ModalCreateIX : function() {
      let form = this.form = new twentyc.rest.Form(
        $ctl.template("form_create_ix")
      );

      let modal = this;
      $(this.form).on("api-write:success", function(event, endpoint, payload, response) {
        $ctl.ixctl.refresh().then(
          () => { $ctl.ixctl.select_ix(response.content.data[0].id) }
        );
        modal.hide();
      });
      this.Modal("continue", "Create new exchange", form.element);
      // remove dupe
      // form.element.find("span.select2").last().detach()
      form.wire_submit(this.$e.button_submit);
    }
  },
  $ctl.application.Modal
);


/**
 * Displays modal for editing and creating new InternetExchangeMember
 * objects
 *
 * @class ModalMember
 * @constructor
 * @extends $ctl.application.Modal
 * @namespace $ctl.application.Ixctl
 */

$ctl.application.Ixctl.ModalMember = $tc.extend(
  "ModalMember",
  {
    ModalMember : function(ix_slug, member) {
      var modal = this;
      var title = "Add Member";
      var form = this.form = new twentyc.rest.Form(
        $ctl.template("form_member")
      );

      this.member = member;
      form.base_url = form.base_url.replace("/default", "/"+ix_slug);

      $(this.form).on("payload:after", (ev, payload) => {
        // macaddr_set comes in as a string with a mac address
        // on each line. We need to split it into an array
        payload.macaddr_set = payload.macaddr_set.split("\n").filter((line) => {
          return line.trim() != "";
        });

        // delete payload.macaddr
        if(payload.macaddr)
          delete payload.macaddr;

        return payload;
      });

      $(this.form).on("fill:before", (ev, data) => {
        // macaddr_set comes in as an array, we need to join it into a string
        data.macaddr_set = data.macaddr_set.join("\n");
        data.virtual_port_name = data.port ? data.port.virtual_port_name : "";
        return data;
      });

      // load select options

      var state_select = new twentyc.rest.Select(
        form.element.find('#member-state')
      );
      state_select.load((member?member.ixf_state:null));

      var type_select = new twentyc.rest.Select(
        form.element.find('#member-type')
      );
      type_select.load((member?member.ixf_member_type:null));


      // handle port quantity select
      var quantity = 1;
      // when `lag` is false, disable the port quantity select
      form.element.find('#member-lag').change(function() {
        var lag = $(this).prop('checked');
        form.element.find('#member-port-quantity').prop('disabled', !lag);
      });

      // if lag is currently true, enable the port quantity select
      if(member && member.lag) {
        form.element.find('#member-port-quantity').prop('disabled', false);
      }

      // if port quantity is changed to > 1, enforce lag to true
      // and prevent user from changing it back to false

      form.element.find('#member-port-quantity').change(function() {
        quantity = Number($(this).val());
        if(quantity > 1) {
          form.element.find('#member-lag').prop('checked', true).prop('disabled', true);
        } else {
          form.element.find('#member-lag').prop('disabled', false);
        }
        modal.port_config_intent();
      });

      // if port quantity is > 1, enforce lag to true
      if(member && member.port_quantity > 1) {
        form.element.find('#member-lag').prop('checked', true).prop('disabled', true);
      }

      // member-macaddr-limit value is > than macaddr_set.length
      // show .macaddr-limit-warning
      form.element.find('#member-macaddr-limit').change(function() {
        var limit = Number($(this).val());
        var macaddr_set = modal.member.macaddr_set || [];
        if(limit < macaddr_set.length) {
          form.element.find('.macaddr-limit-warning').show();
        } else {
          form.element.find('.macaddr-limit-warning').hide();
        }
      });

      // if button_validate exists in from, wire the button to validate
      // the form
      let button_validate = form.element.find("[data-element='button_validate']");
      button_validate.click(() => {
        this.validate();
      });

      if(member) {
        title = "Edit "+member.display_name;
        form.method = "PUT"
        form.form_action = member.id;
        this.sync_form(member.id);

        form.element.find('#member-as-macro').attr('placeholder', member.as_macro)

        form.element.find('input[type="text"],select,input[type="checkbox"]').each(function() {
          if(!grainy.check(member.grainy+"."+$(this).attr("name"), "u")) {
            $(this).attr("disabled", true)
          }
        });


        $(this.form).on("api-write:before", (ev, e, payload) => {
          const intent = this.port_config_intent();
          payload["ix"] = member.ix;
          payload["id"] = member.id;
          payload["port_config_intent"] = intent;

          // if intent is lag-increase we need to combine
          // old and new port_set values
          if(intent == "lag-increase") {
            const old_ports = this.member.port.physical_ports.map((port) => {
              return port.id;
            });
            const new_ports = payload.port_set;
            payload.port_set = old_ports.concat(new_ports);
          }
        });
      } else {
        this.init_autocomplete_prefix_set();
        this.init_device_port_select();
      }

      $(this.form).on("api-write:success", (ev, e, payload, response) => {
        $ctl.ixctl.$t.members.$w.list.load();
        modal.hide();
      });

      this.Modal("save_right", title, form.element);
      form.wire_submit(this.$e.button_submit);

      this.jquery.on("hidden.bs.modal", () => {
        console.log("clearing validation checks");
        this.clear_validation_checks();
      });
    },

    /**
     * Returns the current port config intent action depending
     * on the choices made and whether or not a member is being
     * created or edited
     *
     * Returns:
     *
     * - null if no port config intent is being made on an existing member
     * - create if a new member is being created
     * - lag-increase if LAG is true on existing member and the quanity on the input
     *   greater from the quantity on the member.
     * - lag-decrease if LAG is true on existing member and the quanity on the input
     * - resize if not augment and any of size, LAG, or port quantity differ
     *
     * @method port_config_intent
     * @return {String}
     */

    port_config_intent : function() {
      const port_set_container = this.form.element.find('[data-element="port_set_container"]');

      if(!this.member) {
        $(".port-config-intent").hide();
        port_set_container.show();
        return "create";
      }

      const member = this.member;
      const port = member.port;

      const lag = this.form.element.find('#member-lag').prop('checked');
      const port_size = Number(this.form.element.find('#member-port-size').val());
      const port_quantity = Number(this.form.element.find('#member-port-quantity').val());
      const device = this.form.element.find('#device').val();
      const current_ports_container = this.form.element.find('[data-element="current_ports"]');
      const virtual_port_display = this.form.element.find('[data-element="virtual_port_display"]');
      current_ports_container.show();

      if(
        port &&
        lag &&
        port_quantity != member.port_quantity &&
        port_size == member.port_size &&
        device == port.device_id
      ) {
        virtual_port_display.show();
        port_set_container.show();
        $(".port-config-intent").hide().filter('.intent-augment').show();
        if(port_quantity > member.port_quantity) {
          current_ports_container.show();
          return "lag-increase";
        } else {
          current_ports_container.hide();
          return "lag-decrease";
        }
      }

      if(
        port && (
          lag != member.lag ||
          port_quantity != member.port_quantity ||
          port_size != member.port_size ||
          device != port.device_id
        )
      ) {
        current_ports_container.hide();
        virtual_port_display.hide();
        port_set_container.show();
        $(".port-config-intent").hide().filter('.intent-resize').show();
        return "resize";
      }

      port_set_container.hide();
      $(".port-config-intent").hide();

      if(port)
        virtual_port_display.show();
      else {
        port_set_container.show();
      }

      this.sync_validation_button_label();

      return null;
    },

    /**
     * Initalizes device and port selection fields
     * @method init_device_port_select
     */

    init_device_port_select : function(member) {
      const form = this.form;
      const port = member && member.port ? member.port : null;
      const modal = this;
      this.device_select = new twentyc.rest.Select(
        form.element.find('#device')
      );
      this.device_select.format_request_url = (url) => {
        return url.replace("__ix_tag__", fullctl.ixctl.ix_slug());
      };

      const device_select = this.device_select;

      device_select.load(port ? port.device_id : null).then(() => {
        // Initial load with the first option selected
        const initial_device_selection = form.element.find('#device').val();
        load_device_ports(initial_device_selection);
      }).catch((error) => {
        console.error('Error during load devices:', error);
      });

      // device port select
      // when device is selected, all ports are displayed
      form.element.find('#device').change(function() {
        load_device_ports($(this).val());
        modal.port_config_intent();
      });

      // Change ports also when port size changes
      form.element.find('#member-port-size').change(function() {
        var selectedValue = form.element.find('#device').val();
        load_device_ports(selectedValue);
        modal.port_config_intent();
      });

      // Change quantity also triggers load_device_ports
      form.element.find('#member-port-quantity').change(function() {
        var selectedValue = form.element.find('#device').val();
        load_device_ports(selectedValue);
        modal.port_config_intent();
      });

      form.element.find('#port_set').change(function() {
        const quanity = form.element.find('#member-port-quantity').val();
        var selection_limit = quantity;
        var selected_options = $(this).find('option:selected');

        if (selected_options.length > selection_limit) {
          // If the number of selected options exceeds the limit, deselect the last selected option
          selected_options.each(function(index) {
            if (index >= selection_limit) {
              $(this).prop('selected', false);
            }
          });

          // Provide feedback to the user
          alert('You can only select up to ' + selection_limit + ' options at once. Review the "Quantity" parameter.');
        }
      });

      function load_device_ports(selectedValue) {
        // Set the selected option's text into the text field
        var port_select = new twentyc.rest.Select(
          form.element.find('#port_set').empty()
        );
        port_select.format_request_url = (url) => {
          member_port_size = form.element.find('#member-port-size').val();
          url = url + '?size=' + member_port_size;
          url = url + '&unassigned=true';

          if(modal.port_config_intent() == "lag-decrease") {
            url = url + `&virtual_port=${port.virtual_port}`;
          }

          url = url.replace("0", selectedValue);
          return url;
        };
        port_select.load().then(() => {
          modal.port_config_intent();
          auto_select_ports();
        }).catch((error) => {
          console.error('Error during load ports:', error);
        });
      };

      function auto_select_ports() {
        var n = form.element.find('#member-port-quantity').val();
        form.element.find('#port_set option').each(function(index) {
          $(this).prop('selected', index < n);
        });
      }

      // Auto selected ports when change the quantity
      form.element.find('#member-port-quantity').change(function(){
        auto_select_ports();
      });

      // Populate current ports from port.physical_ports which
      // is a list of physical ports with name fields
      if(port && port.physical_ports) {
        const current_ports_container = form.element.find('[data-element="current_ports"]');
        const current_ports_list = current_ports_container.find('.port-list');
        current_ports_list.empty();
        port.physical_ports.forEach((port) => {
          current_ports_list.append(
            $('<li>').addClass('port').text(port.name)
          );
        });
      }
    },

    /**
     * Initializes the prefix-set autocomplete field
     * @method init_autocomplete_prefix_set
     */

    init_autocomplete_prefix_set : function() {
      const form = this.form;
      fullctl.ext.select2.init_autocomplete(

        // bind to prefix-set <select> element
        form.element.find("#prefix-set"),

        // parent dropdown to form element
        form.element,

        // options
        {

          // autocomplete url
          url: "/autocomplete/prefix/prefix_set?require_slug=1&org="+fullctl.org.slug,

          // place holder text for the search field
          placeholder: "Begin typing to Search Prefix Sets by name or slug",

          // if session is specifed, preselect it's prefix set
          initial: (callback) => {
            if(!this.member) {
              return null;
            }
            if(!this.member.prefix_set) {
              callback({});
              return;
            }

            callback({
              id: this.member.prefix_set,
              primary: this.member.prefix_set_name,
              secondary: this.member.prefix_set,
            })
          }
        }
      );
    },

    /**
     * Requests the member details from the API and fills the form with the
     * member's data.
     *
     * @method sync_form
     * @param {Number} member_id
     */

    sync_form : function(member_id) {
      const form = this.form;

      form.get(member_id).then((response) => {
        const member = response.first();
        this.member = member;

        form.fill(member);
        form.apply_data(member);

        // if mac limit is set, show warning if macaddr_set.length > limit
        if(member && member.macaddr_limit) {
          var limit = member.macaddr_limit;
          if(limit < member.macaddr_set.length) {
            form.element.find('.macaddr-limit-warning').show();
          }
        }

        // setup prefix-set auto complete
        this.init_autocomplete_prefix_set();
        this.init_device_port_select(member);


      });
    },

    /**
     * Run validation
     * @method validate
     */

    validate : function() {
      const payload = {
        name: this.form.element.find("#member-name").val(),
        asn: this.form.element.find("#member-asn").val(),
        case_number: this.form.element.find("#case_number").val(),
        port: this.form.element.find("#port").val() || "",
      }

      const headers = {
        "Content-Type": "application/json",
        "X-CSRFToken": twentyc.rest.config.csrf
      }

      const validation_results_node = this.form.element.find('#validation-results');
      validation_results_node.empty();
      this.clear_validation_checks();

      validation_results_node.append(
        $('<h6 class="please-wait">').text("Please wait ...")
      )

      // show the validaiton results container
      this.form.element.find('#validation-results-container').show();

      // hide validation button
      this.form.element.find("[data-element='button_validate']").hide();


      // if work order is selected, request next ip

      const selected_work_order = this.form.element.find('input[name="work_order"]:checked').val();

      if(selected_work_order) {
        payload.work_order = selected_work_order;
        this.request_next_ip_addresses(headers, payload);
      } else {
        this.validate_case_number(headers, payload);
      }

    },

    /**
     * Runs async validation task to validate the case number
     * If successful this will populate the name field and
     * display the work orders as radio buttons
     *
     * @method validate_case_number
     * @param {*} headers
     * @param {*} payload
     */

    validate_case_number : function(headers, payload) {
      const work_orders_node = this.form.element.find('#work-orders');

      // validate case number and org name
      work_orders_node.empty()

      if(this.form.element.find("#case_number").length > 0) {
        $.ajax({
          url: twentyc.rest.url.url_join(this.form.base_url, "/validate/case-number/"),
          method: "POST",
          headers: headers,
          data: JSON.stringify(payload),
        }).then((response) => {
          const task = response.data[0];
          this.handle_validation_task_update(task);
          this[`task_poller_${task.op}`] = setInterval(() => {
            this.check_validation_task(task.id, task.op);
          }, 1000);
        });
      }
    },

    /**
     * Runs async validation task to request the next ip addresses
     *
     * @method request_next_ip_addresses
     * @param {*} headers
     * @param {*} payload
     */

    request_next_ip_addresses : function(headers, payload) {
      // validate / autofill ipv4 and ipv6 addresses
      $.ajax({
        url: twentyc.rest.url.url_join(this.form.base_url, "/validate/request-ip-address-pair/"),
        method: "POST",
        headers: headers,
        data: JSON.stringify(payload),
      }).then((response) => {
        const task = response.data[0];
        this.handle_validation_task_update(task);
        this[`task_poller_${task.op}`] = setInterval(() => {
          this.check_validation_task(task.id, task.op);
        }, 1000);
      });
    },

    /**
     * Checks the status of a validation task by task ID
     *
     * @method check_validation_task
     */

    check_validation_task : function(taskId, taskOp) {
      const url = twentyc.rest.url.url_join(this.form.base_url, `/validate/result/${taskId}/`);
      $.ajax({
        url: url,
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        }
      }).then((response) => {
        const task = response.data[0];
        this.handle_validation_task_update(task);
      }).fail((xhr, status, error) => {
        clearInterval(this[`task_poller_${taskOp}`]);
        console.error("Error checking validation task", status, error);
      });

    },

    /**
     * Syncs the validation button label according to what
     * is the current validation state
     *
     * State 0: nothing validated, clicking the button would validate
     * case number - label: "Validate"
     *
     * State 1: case number validated, clicking the button would request
     * the next ip addresses - label: "Request Next IP Addresses"
     *
     * @method sync_validation_button_label
     */
    sync_validation_button_label: function() {
      const work_orders_node = this.form.element.find('#work-orders');
      const selected_work_order = work_orders_node.find('input[name="work_order"]:checked').val();
      const case_number = this.form.element.find("#case_number").val();
      const button_validate = this.form.element.find("[data-element='button_validate']");

      if(selected_work_order) {
        button_validate.text("Request IP Addresses");
      } else {
        button_validate.text("Validate");
      }
    },

    handle_validation_task_update : function(task) {

      $('.please-wait').detach();

      const op_to_label = {
        task_get_next_ip_addresses: "Next IP Addresses",
        task_verify_case_number: "Verifying Case Number",
      }

      const op_to_info_text = {
        task_get_next_ip_addresses: (task_data) => {
          return $("<p>").addClass('result').append(
            $("<div>").text("IPv4: " + task_data.result.ipaddr4),
            $("<div>").text("IPv6: " + task_data.result.ipaddr6)
          );
        }
      }

      const op_to_action = {
        // autofill ip addresses if they are empty
        task_get_next_ip_addresses: (task_data) => {
          const ip4_field = this.form.element.find("#member-ipaddr4");
          const ip6_field = this.form.element.find("#member-ipaddr6");
          if(ip4_field.val() == "" && ip6_field.val() == "") {
            ip4_field.val(task_data.result.ipaddr4);
            ip6_field.val(task_data.result.ipaddr6);
          }
        },

        // autofill name if it is empty
        task_verify_case_number: (task_data) => {
          const name_field = this.form.element.find("#member-name");
          if(name_field.val() == "") {
            name_field.val(task_data.result.name);
          }
          // we are getting back work orders in `result.work_orders` as
          // [{"elid":"..", "status":"empty or filled"}, ..]
          //
          // Display the ones with status `empty` as radio buttons (only one can be selected)
          // Display the ones with status `filled` as disabled radio buttons

          const work_orders_node = this.form.element.find('#work-orders');
          work_orders_node.empty();

          // append a "Work Orders" header
          work_orders_node.append(
            $("<h6>").text("Work Order(s)")
          );

          task_data.result.work_orders.forEach((work_order) => {
            const work_order_node = $('<div>')
            const radio = $('<input class="form-check-input">').attr("type", "radio").attr("name", "work_order").val(work_order.elid);
            if(work_order.status == "filled") {
              radio.attr("disabled", true);
            }
            radio.attr("id", `work_order_${work_order.elid}`);
            work_order_node.append(radio);
            work_order_node.append($('<label class="form-check-label">').text(work_order.label).attr("for", `work_order_${work_order.elid}`));
            work_orders_node.append(work_order_node);
          });

          // select the first empty work order
          // to find the first empty work order it needs to be enabled
          work_orders_node.find('input[type="radio"]').each((index, radio) => {
            if(!radio.disabled) {
              radio.checked = true;
              // update the
              return false;
            }
          });
        }
      }

      // if validation result node for task does not exist, create it
      if(!this.form.element.find(`[data-validation-task="${task.op}"]`).length) {
        this.form.element.find("#validation-results").append(
          $('<div>').addClass('task-status-row').attr("data-validation-task", task.op)
        );
      }

      var removeInterval = true;

      var infoNode = $('<div>').append(
        $('<p>').text(op_to_label[task.op])
      );

      if(task.status === "pending") {
        infoNode.append($('<div class="loading-indicator">'));
        removeInterval = false;
      } else if(task.status === "failed") {
        // <img src="/s/3.4.0-rc.30/common/icons/Indicator/X-Ind/X.svg" class="icon filled">
        infoNode.append($('<img>').addClass('status').attr("src", fullctl.static_path + "common/icons/Indicator/X-Ind/X.svg"));
        infoNode.append($('<p>').addClass('result').text(task.error));
      } else if(task.status === "completed") {
        const valid = task.result.valid;
        if(valid) {
          infoNode.append($('<img>').addClass('status').attr("src", fullctl.static_path + "common/icons/Indicator/Check-Ind/Check.svg"));
          if(op_to_info_text[task.op]) {
            infoNode.append(op_to_info_text[task.op](task));
          }
          if(op_to_action[task.op]) {
            op_to_action[task.op](task);
          }
        } else {
          infoNode.append($('<img>').addClass('status').attr("src", fullctl.static_path + "common/icons/Indicator/X-Ind/X.svg"));
          infoNode.append($('<p>').addClass('result').text(task.result.message));
        }

      }
      const container = $(`[data-validation-task="${task.op}"]`);
      container.empty().append(infoNode);

      if(removeInterval) {
        clearInterval(this[`task_poller_${task.op}`]);
        delete this[`task_poller_${task.op}`];
        // hide or show validate button based on if there are any pending tasks
        if(!this.has_validation_checks()) {
          this.form.element.find("[data-element='button_validate']").show();
        } else {
          this.form.element.find("[data-element='button_validate']").hide();
        }
      }

      this.sync_validation_button_label();
    },

    has_validation_checks : function() {
      // check if any validation checks are currently running
      return Object.keys(this).some((key) => {
        return key.startsWith("task_poller_");
      });
    },

    clear_validation_checks : function() {
      // clear existing validation result checks
      Object.keys(this).forEach((key) => {
        if(key.startsWith("task_poller_")) {
          clearInterval(this[key]);
          delete this[key];
        }
      });
    }


  },
  $ctl.application.Modal
);


$ctl.application.Ixctl.Members = $tc.extend(
  "Members",
  {
    Members : function() {
      this.Tool("members");
    },

    init : function() {

      this.widget("list", ($e) => {
        return new $ctl.application.Ixctl.MemberList(
          this.template("list", this.$e.body)
        );
      });

      this.$w.list.formatters.row = (row, data) => {

        // common/v2/metric.js
        let url = this.$w.list.element.data('api-metric-base');
        $.fn.show_metric_list(url, row, data);

        row.find('a[data-action="edit_member"]').click(() => {
          var member = row.data("apiobject");
          new $ctl.application.Ixctl.ModalMember($ctl.ixctl.ix_slug(), member);
        }).each(function() {
          if(!grainy.check(data.grainy+".?", "u")) {
            $(this).hide();
          }
        });

        row.find('a[data-action="view_member_details"]').click(() => {
          // console.log("member details",row.data("apiobject").id)
          $ctl.ixctl.$t.member_details.show_member(row.data("apiobject").id);
          window.location.href = '#member';
        });

        if(!grainy.check(data.grainy, "d")) {
          row.find('a[data-api-method="DELETE"]').hide();
        }

        // Initialize port status
        var statusSpan = row.find('span[data-field="status"]');
        if(data.status=="ok") {
          statusSpan.attr('data-toggle', 'checked');
          statusSpan.addClass('checked');

        } else if(data.status=="admin_down") {
          statusSpan.attr('data-toggle', 'unchecked');
          statusSpan.removeClass('checked');
        }

        // Change port status event
        row.find('a[data-action="toggle_status"]')
        .attr("title", data.status == "ok" ? "Disable Port" : "Enable Port")
        .click((event) => {
          event.preventDefault();
          // TODO <saf>: confirm only on disable?
          const confirmation = confirm("Are you sure you want to toggle this port status?");
          if (!confirmation) {
            return;
          }

          var statusSpan = row.find('span[data-field="status"]');
          var currentToggle = statusSpan.attr('data-toggle');

          var nextStatus = "ok";
          statusSpan.attr('data-toggle', 'checked');
          statusSpan.addClass('checked');
          if(currentToggle === 'checked') {
            nextStatus = "admin_down";
            statusSpan.attr('data-toggle', 'unchecked');
            statusSpan.removeClass('checked');
          }
          let member = row.data("apiobject");


          let url = this.$w.list.element.data('api-port-status');
          url = url.replace("default", $ctl.ixctl.ix_slug());
          url = url.replace(/0/g, member.id);

          $.ajax({
            url: url,
            method: 'PATCH',
            headers : {
              "Content-Type" : "application/json",
              "X-CSRFToken" : twentyc.rest.config.csrf
            },
            data: JSON.stringify({
              status: nextStatus,
              ipaddr4: member.ipaddr4,  // mandatory field
              ipaddr6: member.ipaddr6,  // mandatory field
            }),
            success: function(response) {
              // console.log('Success:', response);
              row.find('a[data-action="toggle_status"]')
              .attr("title", response.data[0].status == "ok" ? "Disable Port" : "Enable Port");
            },
            error: function(xhr, status, error) {
              // console.log('Error:', status, error);
            },
            async: false
          });
        });
      };

      this.$w.list.formatters.macaddr_set = (macaddr_set) => {
        return macaddr_set.join("\n");
      };

      this.$w.list.formatters.macaddr_warnings = (macaddr_warnings, data, col) => {
        // macaddr_warnings is an array of strings
        // format into divs
        if(!macaddr_warnings || macaddr_warnings.length == 0) {
          col.parent(".row").hide();
          return "";
        }

        let container = $('<div>').addClass("macaddr-warnings");
        macaddr_warnings.forEach((warning) => {
          container.append(
            $('<div>').addClass("message-warning marg-bot-sm").append(
              $('<span>').text(warning)
            )
          );
        });
        return container;
      }

      this.$w.list.formatters.speed = $ctl.formatters.pretty_speed;

      $(this.$w.list).on("api-read:before",function(endpoint)  {
        let url = this.base_url.split("/").slice(0,-1);
        url.push($ctl.ixctl.ix_slug());
        this.base_url = url.join("/");
      });

      $(this.$w.list).on("load:after", () => {
        this.update_counts();
        this.load_member_stats();
      });

      this.member_ids = new Set();
      $(this.$w.list).on("insert:after", (_, row_element, data) => {
        this.member_ids.add(data.id);
      });

      this.initialize_sortable_headers();
    },

    menu : function() {
      const menu = this.Tool_menu();
      menu.find('[data-element="button_add_member"]').click(() => {
        return new $ctl.application.Ixctl.ModalMember($ctl.ixctl.ix_slug());
      });

      // returns a function that will filter the list based on the search term.
      // This structure is needed because the list is loaded asynchronously
      // and we need to wait for it to load before we can filter it. and the
      // event doesn't pass the search term.
      const after_list_load_func = (search_term) => {
        return () => {
          const lowercase_search_term = search_term.toLowerCase();
          const members = this.$w.list.list_body.find("tr:not(.secondary)");
          let first_match;

          members.each(function() {
            const primary_row = $(this);
            const secondary_row = $(this).next();

            const asn = $(this).find('[data-field="asn"]').text().toLowerCase();
            const name = $(this).find('[data-field="display_name"]').text().toLowerCase();
            if (asn.startsWith(lowercase_search_term) || name.indexOf(lowercase_search_term) !== -1) {
              primary_row.removeClass("filter-hidden");
              secondary_row.removeClass("filter-hidden");

              if (!first_match) {
                primary_row[0].scrollIntoView();
                first_match = this;
              }
            } else {
              primary_row.addClass("filter-hidden");
              secondary_row.addClass("filter-hidden");
            }
          });
        };
      };

      // used to store the last after_list_load_func so we can remove it
      // when the filter is cleared.
      let last_after_load_func;

      const member_filter = (search_term) => {
        if (last_after_load_func) {
          $(this.$w.list).off("load:after", last_after_load_func);
        }

        last_after_load_func = after_list_load_func(search_term);

        $(this.$w.list).on("load:after", last_after_load_func);

        this.$w.list.load();
      }


      const clear_member_filter = () => {
        this.$w.list.list_body.find(".filter-hidden").removeClass("filter-hidden");
        if (last_after_load_func) {
          $(this.$w.list).off("load:after", last_after_load_func);
          last_after_load_func = null;
        }
      }

      new fullctl.application.Searchbar(
        menu.find(".member-searchbar"),
        member_filter,
        clear_member_filter
      );

      const member_list = this.$w.list;
      menu.find("[data-element=filter_non_active_members]").click(function() {
        $(this).toggleClass("active");
        member_list.toggle_non_active_filter();
      });

      menu.find("[data-element=filter_md5_members]").click(function() {
        $(this).toggleClass("active");
        member_list.toggle_md5_filter();
      });

      return menu;
    },

    update_counts : function() {
      const tool = this;
      let non_active_members = 0;
      let non_md5_members = 0;
      const members = this.$w.list.list_body.find("tr:not(.secondary)");
      members.each(function() {
        const data = $(this).data("apiobject");
        if (!tool.$w.list.is_member_active(data)) {
          non_active_members += 1;
        }
        if (tool.$w.list.is_member_md5(data)) {
          non_md5_members += 1;
        }
      });

      this.$e.menu.find('[data-element="filter_non_active_members"] .value').text(non_active_members);
      this.$e.menu.find('[data-element="filter_md5_members"] .value').text(non_md5_members);
      this.$e.menu.find('[data-element="members_count"] .value').text(members.length);
    },

    sync : function() {
      var ix_id = $ctl.ixctl.ix()
      if(ix_id) {
        var exchange = $ctl.ixctl.exchanges[ix_id]
        if(grainy.check(exchange.grainy, "r")) {
          this.show();
          this.apply_ordering();
          this.$w.list.load();
          let ixf_export_url = this.jquery.data("ixf-export-url").replace("default", $ctl.ixctl.ix_slug());
          if ($ctl.ixctl.ix_object().ixf_export_privacy == "private"){
            ixf_export_url = ixf_export_url + "?secret=" + $ctl.ixctl.urlkey()
          }
          this.$e.menu.find('[data-element="button_ixf_export"]').attr(
            "href", ixf_export_url
          )

          this.$e.menu.find('[data-element="button_api_view"]').attr(
            "href", this.$w.list.base_url + "/" + this.$w.list.action +"?pretty"
          )

          if(grainy.check(exchange.grainy, "c")) {
            this.$e.menu.find('[data-element="button_add_member"]').show();
            this.$e.menu.find('[data-element="button_ixf_export"]').show();
          } else {
            this.$e.menu.find('[data-element="button_add_member"]').hide();
            this.$e.menu.find('[data-element="button_ixf_export"]').hide();
          }

        } else {
          this.hide();
        }
      } else {
        // no exchange exists - hide members tool
        this.hide();
      }
    },

    load_member_stats: function () {
      let url = this.$w.list.element.data('api-member-stats');
      this.member_ids.forEach(member_id => {
        $.ajax({
          url: url.replace("default", $ctl.ixctl.ix_slug()).replace("/0/", `/${member_id}/`)
        }).done(({data = []}) => {
          const {bgp_stat = null, traffic_alert_data = null} = data[0];
          const row = this.$w.list.find_row(member_id);
          const row_data = row.data('apiobject');

          if (traffic_alert_data) {
            const port_is_hot = row.find('[data-element="port_is_hot"]');
            $.fn.show_traffic_alert({traffic_alert_data}, port_is_hot);
          }

          if (row_data.is_rs_peer && bgp_stat) {
            $.fn.show_bgp_stat(bgp_stat, row);
          }
        });
      });
    }

  },
  $ctl.application.Tool
);


$ctl.application.Ixctl.MemberList = $tc.extend(
  "MemberList",
  {
    MemberList : function(jq, filters) {
      this.List(jq);

      this.filter_status = {
        non_active_members : false,
        md5_members : false
      }

    },

    /**
     * hides or shows non active members in the list.
     *
     * @method toggle_non_active_filter
     * @param {Boolean} [active]
     */
    toggle_non_active_filter : function(active = null) {
      const filter_status =  active != null ? active : !this.filter_status.non_active_members;
      this.filter_status.non_active_members = filter_status;

      if (filter_status) {
        $(this).on("insert:after", this.hide_active_members)
      } else {
        $(this).off("insert:after", this.hide_active_members)
      }

      this.load();
    },

    /**
     * Add a class to rows that are not active. This is used to hide them.
     *
     * @method hide_active_members
     * @param {Event} e
     * @param {jQuery} row
     * @param {Object} data
     */
    hide_active_members : function(e, row, data) {
      if (this.is_member_active(data)) {
        row.addClass('filter-non-active-hidden')
      }
    },

    /**
     * Returns true if the member is active.
     *
     * @method is_member_active
     * @param {Object} apiobj
     */
    is_member_active : function(apiobj) {
      return apiobj.ixf_state == "active" || apiobj.port != null;
    },

    /**
     * hides or shows members with md5 activated in the list.
     *
     * @method toggle_md5_filter
     * @param {Boolean} [active]
     */
    toggle_md5_filter : function(active = null) {
      const filter_status =  active != null ? active : !this.filter_status.md5_members;
      this.filter_status.md5_members = filter_status;

      if (filter_status) {
        $(this).on("insert:after", this.hide_non_md5_members)
      } else {
        $(this).off("insert:after", this.hide_non_md5_members)
      }

      this.load();
    },


    /**
     * Add a class to rows that do not have md5. This is used to hide them.
     *
     * @method hide_non_md5_members
     * @param {Event} e
     * @param {jQuery} row
     * @param {Object} data
     */
    hide_non_md5_members : function(e, row, data) {
      if (!this.is_member_md5(data)) {
        row.addClass('filter-non-md5-hidden')
      }
    },

    /**
     * Returns true if the member has md5.
     *
     * @method is_member_md5
     * @param {Object} apiobj
     */
    is_member_md5 : function(apiobj) {
      return apiobj.md5 != null;
    },

  },
  twentyc.rest.List
);

/**
 * Metric tool
 */

// $ctl.application.Ixctl.Metric = $tc.extend(
//     "Metric",
//     {
//         Metric : function() {
//             this.Tool("metric");
//             this.member = null;
//         },

//         menu : function() {},

//         sync : function() {
//             // console.log("metric sync");
//         },

//         show : function(member) {
//             // console.log(member.port);
//         }

//     },
//     $ctl.application.Tool
// );

/**
 * Traffic tool
 */

$ctl.application.Ixctl.Traffic = $tc.extend(
  "Traffic",
  {

    Traffic : function() {
      this.Tool("traffic");

      if(this.$e.dev_tools) {
        this.$e.force_rrd_mrtg.click(() => {
          this.force_traffic_source = "rrd_mrtg";
          this.sync();
        });

        this.$e.force_vm_mrtg.click(() => {
          this.force_traffic_source = "vm_mrtg";
          this.sync();
        });

        this.$e.force_vm_sflow.click(() => {
          this.force_traffic_source = "vm_sflow";
          this.sync();
        });
      }

    },

    sync : function() {
      this.show_graph_controls().indicate_graph_loading().show_graph();
    },

    // Function to indicate loading
    indicate_graph_loading : function() {
      let graph_container = this.$e.graph_container;
      graph_container.empty().append(fullctl.template("graph_placeholder"));
      return this;
    },

    show_graph_controls() {
      let node = this.$e.graph_container.parents(".ix-total-traffic");
      fullctl.graphs.init_controls(node, this, (end_date, duration)=>{
        this.indicate_graph_loading().show_graph(end_date, duration);
      });
      node.find('.graph-controls').show();
      return this;
    },

    // Function to show graphs
    show_graph : function(end_date, duration) {
      let ix = $ctl.ixctl.ix_object();
      let graph_traffic_source = this.force_traffic_source || ix.graph_traffic_source;
      fullctl.graphs.show_graph(
        this.$e.graph_container,
        graph_traffic_source,

        end_date,
        duration,

        // title
        fullctl.ixctl.ix_object().name + " Total Traffic",

        // selector
        ".graph_container",

        // get_url function
        (graph_container, url_attribute) => {
          return graph_container.data(url_attribute).replace("/0/", "/"+$ctl.ixctl.ix()+"/")
        },

        // proxy
        this
      );
    }
  },
  $ctl.application.Tool
);

/**
 * Device details tool
 */

$ctl.application.Ixctl.MemberDetails = $tc.extend(
  "MemberDetails",
  {
    MemberDetails: function () {
      this.Tool("member_details");
      this.member_id = 0;
      this.member = null;
    },

    init : function() {

      var tool = this;

      // create member details widget that holds member information
      // such as ip addresses, speed and graphs

      this.widget("member", ($e) => {
        let form = new twentyc.rest.Form(
          this.template("member_widget", this.$e.member_container)
        );
        form.format_request_url = (url) => {
          return url.replace("default", $ctl.ixctl.ix_slug());
        }
        $(form).on("fill:before", (ev, data) => {
          data.macaddr_set = data.macaddr_set.join("\n");
        });
        return form;
      });

      this.widget("bgp_stats_list", ($e) => {
        return new twentyc.rest.List($("#bgp_stats_list"));
      });

      this.$w.bgp_stats_list.element.hide();
    },

    // Function to show member details
    show_member : function(member_id) {

      this.member_id = member_id;

      this.$e.menu.find('[data-element="button_api_view_member_detail"]').attr(
        "href", `${this.$w.member.base_url}/${member_id}/?pretty`.replace("default", $ctl.ixctl.ix_slug())
      )

      this.$e.graphs_container.empty().append(
        fullctl.template("graph_placeholder")
      );
      this.$e.refresh_traffic_graph.hide();

      $.fn.reset_metric_table();
      this.hide_summary_table();

      $("#tab-member").tab("show")

      this.$w.member.get(""+member_id).then(
        (response) => {
          let member = response.first();
          this.member = member;
          this.$e.menu.find('.member-name').text(member.name);
          this.$e.menu.find('.member-asn').text(member.asn);

          member.virtual_port_name = member.port ? member.port.virtual_port_name :"No port assigned";
          member.device_name = member.port ? member.port.device_name :"";
          member.pretty_speed = fullctl.formatters.pretty_speed(member.speed);
          member.as_macro_prepared = member.as_macro_override || member.as_macro || "";

          this.$e.menu.find('.ip4').text(member.ipaddr4);
          this.$w.member.fill(member);

          // Fill bgp stats
          if (member.bgp_stat) {
            this.show_summary_table(member.bgp_stat);
          }

          this.$e.body.parents(".tool").find('#date_range_select').val("24");
          this.show_graph_controls(member).indicate_graph_loading().show_graphs(member);
          //this.show_metric(member);
          let url = this.$w.member.element.data('api-metric-base');
          $.fn.show_metric_table(url, member);
        }
      );
    },

    hide_summary_table: function () {
      this.$w.bgp_stats_list.list_body.empty();
      $("#bgp_stats_list thead tr:first th:not(:first)").remove();
      $("#bgp_stats_list thead tr:eq(1) th").each(function(index) {
          if (index > 4) {
            $(this).remove();
          }
      });
      $("#bgp_stats_list tbody tr:eq(1) td").each(function(index) {
          if (index > 4) {
            $(this).remove();
          }
      });
      this.$w.bgp_stats_list.element.hide();
    },

    show_summary_table: function (data) {
      const routeservers = Object.keys(data);
      routeservers.forEach((routeserver_hostname, index) => {
        $("#bgp_stats_list thead tr:first").append(
          `<th colspan="4" class="text-center">${routeserver_hostname}</th>`
        )
        if (index > 0) {
          // const copied_headers = $("#bgp_stats_list thead tr:eq(1) th:nth-last-child(-n+4)");
          $(`#bgp_stats_list thead tr:eq(${index})`).append(
            "<th>State</th><th>Received</th><th>Advertised</th><th>Last Changed</th>"
          );
        }
        data[routeserver_hostname].forEach((stat, idx) => {
          if (index == 0) {
            this.$w.bgp_stats_list.insert(stat);
          } else {
            const {state, routes_imported, routes_exported, last_change} = stat;
            $(`#bgp_stats_list tbody tr:eq(${idx})`).append(
              `<td>${state}</td><td>${routes_imported}</td><td>${routes_exported}</td><td>${last_change}</td>`
            );
          }
        });
      });
      this.$w.bgp_stats_list.element.show();
    },

    // Function to indicate loading
    indicate_graph_loading : function() {
      let graph_container = this.$e.body.parents(".tool").find("[data-element=graphs_container]");
      graph_container.empty().append(fullctl.template("graph_placeholder"));
      return this;
    },

    show_graph_controls : function(member) {
      let node = this.$e.body.parents(".tool");

      node.data("graph-member", member);

      if(!this.graph_controls_initialized) {
        fullctl.graphs.init_controls(node, this, (end_date, duration)=>{

          this.indicate_graph_loading().show_graphs(node.data("graph-member"), end_date, duration);
        }, "member_graph_");
        this.graph_controls_initialized = true;
      }
      node.find('.graph-controls').show();
      return this;
    },

    hide_graph_controls : function() {
      let node = this.$e.body.parents(".tool");
      node.find('.graph-controls').hide();
    },

    // Function to show graphs
    show_graphs : function(member, end_date, duration) {

      if(!member.port) {
        // member does not have a port assigned
        // display a message and return

        let message = $('<div class="alert alert-info">').append(
          $('<p>').text("This member does not have a port assigned.")
        )
        graph_container.empty().append(message);
        return;
      }

      let ix = $ctl.ixctl.ix_object();
      let graph_traffic_source = this.force_traffic_source || ix.graph_traffic_source;

      fullctl.graphs.show_graph(
        this.$e.body.parents(".tool").find("[data-element=graphs_container]"),
        graph_traffic_source,
        end_date,
        duration,
        member.port.virtual_port_name,
        "#member_port_traffic_graph",
        (graph_container, url_attribute) => {
          return graph_container.data(url_attribute).replace(/0/g, member.port.virtual_port);
        },
        this,
        (params) => {
          // prepare URL parameters for the graph data request

          // check if query_override element is available, and if it is
          // and has a value, add it to the URL parameters
          //
          // this allows the user to override the aggregation query for live
          // debugging of the graph data (this feature is only available to superusers)
          if(!this.$e.query_override)
            return;
          const queryOverride = this.$e.query_override.val();
          const queryOverrideVisible = this.$e.query_override.is(":visible");
          if(queryOverride && queryOverrideVisible) {

            // base64 encode the query override
            let encoded = btoa(queryOverride);
            params.push(`query_override=${encoded}`);
          }
        }
      );
    }
  },
  $ctl.application.Tool
);

$(document).ready(function() {
  $ctl.ixctl = new $ctl.application.Ixctl();

  $('#traffic-tab').on('show.bs.tab', () => {
    $ctl.ixctl.$t.traffic.sync();
  });

    window.addEventListener('hashchange', function() {
        // Captures changes in the URL hash
        // console.log('on(hashchange) hash:', window.location.hash);
        loadContent(window.location.hash);
    });

    function loadContent(href) {
    //     console.log('load() href:', href);
    //     // Load or display content based on the page ID or hash
        $(href).addClass('active show')
            .siblings('.tab-pane.active')
            .removeClass('active show');
    };

});


})(jQuery, twentyc.cls, fullctl);
