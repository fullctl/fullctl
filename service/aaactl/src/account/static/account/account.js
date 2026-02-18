(function() {

window.account = {}

account.api_client = new twentyc.rest.Client("/api/account");

$().ready(function() {
  const url = new URL(window.location.href);

  if (url.searchParams.has("edit")) {
    return
  }

  if (!aaactl_user_info.has_org_setup) {
    url.searchParams.set("edit", "new-org");
  }

  history.replaceState({}, null, url);
});

account.ControlPanel = twentyc.cls.define(
  "ControlPanel",
  {
    ControlPanel : function() {
      this.elements = {};
      this.forms = {};

      if ($('.org-select').length > 0) {
        this.loadDropDown();
        this.styleDropDown();
      }


      this.createOrganization();
      this.editOrganization();

      this.changePassword();

      this.elements.order_history = $('.order-history');
      if(this.elements.order_history.length > 0) {
        this.order_history_list = new twentyc.rest.List(this.elements.order_history);
      }
      this.buildOrderHistory();

      this.elements.resend_confirmation_email = $('form.resend-confirmation-email');
      if(this.elements.resend_confirmation_email.length  > 0)
        this.resend_confirmation_email = new twentyc.rest.Form(this.elements.resend_confirmation_email);
      $(this.resend_confirmation_email).on("api-post:success", function() {
        this.popoverAlert(
          this.resend_confirmation_email.element.find('button.submit'),
          "Confirmation email has been sent"
        );

      }.bind(this));

      $(this.resend_confirmation_email).on("api-post:error", function(event, endpoint, data, response) {
        console.log(response.content);
      }.bind(this));

      if($('.personal-keys').length > 0) {
        this.personal_invites = new account.PersonalInvites();
      }

    },

    postFromLink: function(url) {
      $.ajax({
        method: "post",
        url: url,
        headers : {
          "X-CSRFToken": twentyc.rest.config.csrf
        }
      }).done(() => { window.document.location.href = window.document.location.href })
    },

    buildOrderHistory: function() {

      // if the user isn't provisioned to view the order history this
      // property wont be set and we can just return
      if(!this.order_history_list)
        return;

      this.order_history_list.formatters.description = function(value, data) {
        return $('<span>').append(
          $('<strong>').text(value),
        );
      }
      this.order_history_list.formatters.processed = function(value, data) {
        var date = new Date(value)
        return $('<span>').append(
          $('<span>').text(date.toDateString().split(' ').slice(1).join(' ')),
        );
      }
      this.order_history_list.formatters.price = function(value, data) {
        return $('<span>').append(
          $('<strong>').text('USD $' + value),
        );
      }
      this.order_history_list.formatters.order_id = function(value, data) {
        return $('<span>').append(
          $('<a>')
            .attr('href', '/billing/order-history/details/' + value)
            .text('Details')
        );
      }
      $(this.order_history_list).on("load:after", () => {
        if ( $("#orderHistoryListBody:empty").length ){
          $('#orderHistoryListBody')
            .append('<tr><td>No entries</td></tr>')
        }
      })
      this.order_history_list.load();
    },

    loadDropDown: function(){
      this.dropDown = new twentyc.rest.List($('.org-select'));
      $('.org-select-dropdown-header').empty();


      this.dropDown.formatters.label = (value, data) => {
        if(data.is_default) {
          return value + " (Primary)";
        }
        return value;
      }


      $(this.dropDown).on("insert:after", (e, row, data) => {
        row.attr('href', '/?org='+ data.slug)
        if (data.selected) {
          $('.org-select-dropdown-header')
            .append($('<span>').text(data.label).addClass('float-left'))
            .append($('<span>').addClass('caret down float-right'));
          row.hide();
        };
      });
      $(this.dropDown).on("load:after", ()=> {
        var menu = $('.org-select-menu');

        menu.children().last().wrap('<div class="custom-divider"></div');

        var btn_make_default = new twentyc.rest.Button(this.dropDown.template("btn_make_default"));
        $(btn_make_default).on('api-write:success', ()=>{ this.loadDropDown(); });
        menu.append(btn_make_default.element)

        menu.append(`<a class="dropdown-item org-item text-body" role="button" data-bs-toggle="modal" data-bs-target="#createOrgModal">+ Create Organization</a>`)
      });
      this.dropDown.load();
    },

    styleDropDown: function() {
      $(".dropdown").on("hide.bs.dropdown", function(){
        $(".org-select").removeClass('dd-box-shadow');
        $(".caret").removeClass('up').addClass('down');
      });
      $(".dropdown").on("show.bs.dropdown", function(){
        $(".org-select").addClass('dd-box-shadow');
        $(".caret").removeClass('down').addClass('up');
      });
    },

    createOrganization: function(){
      this.initializeForm('create-organization', '/');
      if ( !this.forms['create_organization'] ){
        return
      }

      this.forms['create_organization'].post_success = function(response){
        var slug = response.content.data[0].slug;
        document.location.href = `/?org=${slug}`
      }
    },

    editOrganization: function(){
      this.initializeForm('edit-organization');
      if (!this.forms['edit_organization']) {
        return
      }

      $(this.forms['edit_organization']).on("api-write:success", function() {
        document.location.href = '/';
      });
    },

    changePassword: function(){
      this.initializeForm('change-password');
      var has_usuable_password = !$('#setPasswordAlert').length;

      if ( has_usuable_password ){
        $(this.forms['change_password']).on("api-write:success", function() {
          $('#collapseFour').collapse('hide');
          $('#changePwdPopover').popover('show');
          $('.change-password input').val("");
          setTimeout(() => {
              $('#changePwdPopover').popover('hide');
          }, 4000);

        })
      } else {
        $(this.forms['change_password']).on("api-write:success", function() {
          document.location.href = "/";
        })
      }


    },

    initializeForm: function(form_class){
      var form_name = form_class.replace('-','_');
      const form = $(`form.${form_class}`);
      if (form.length == 0) {
        return
      }

      this.elements[form_name] = form;
      this.forms[form_name] = new twentyc.rest.Form(this.elements[form_name]);
    },

    popoverAlert : function(anchor, text) {
      anchor.popover({
        trigger: 'manual',
        content: text
      })
      anchor.popover('show');
      setTimeout(() => {
        anchor.popover('hide');
        anchor.popover('dispose');
      }, 2000);
    }
});



account.ChangeInformation = twentyc.cls.define(
  "ChangeInformation",
  {
    ChangeInformation : function() {
      this.elements = {}
      this.elements.form = $('form.change-information');

      this.styleAccountInformation();

      this.rest_api_form = new twentyc.rest.Form(this.elements.form);
      $(this.rest_api_form).on("api-write:success", function() {
        document.location.href = "/"
      }.bind(this));
    },

    styleAccountInformation : function() {
      $('.collapse').on('show.bs.collapse', function () {
        $( this ).parent().css('background-color','rgba(224, 225, 226, 0.6)');
      });
      $('.collapse').on('hidden.bs.collapse', function () {
        $( this ).parent().css('background-color','rgba(224, 225, 226, 0)');
      });
    },
  }
);


account.UserSettings = twentyc.cls.define(
  "UserSettings",
  {
    UserSettings : function() {
      this.elements = {}
      this.elements.form = $('form.user-settings');

      this.styleAccountInformation();

      this.rest_api_form = new twentyc.rest.Form(this.elements.form);
      $(this.rest_api_form).on("api-write:success", function() {
        document.location.href = "/"
      }.bind(this));
    },

    styleAccountInformation : function() {
      $('.collapse').on('show.bs.collapse', function () {
        $( this ).parent().css('background-color','rgba(224, 225, 226, 0.6)');
      });
      $('.collapse').on('hidden.bs.collapse', function () {
        $( this ).parent().css('background-color','rgba(224, 225, 226, 0)');
      });
    },
  }
);



account.ChangePassword = twentyc.cls.define(
  "ChangePassword",
  {
    ChangePassword : function() {
      this.elements = {}
      this.elements.form = $('form.change-password');

      this.rest_api_form = new twentyc.rest.Form(this.elements.form);
      $(this.rest_api_form).on("api-write:success", function() {
        if(this.rest_api_form.redirect) {
          document.location.href = this.rest_api_form.redirect;
        } else {
          document.location.href = "/"
        }
      }.bind(this));
    }
  }
);


account.CreateOrganization = twentyc.cls.define(
  "CreateOrganization",
  {
    CreateOrganization : function() {
      this.elements = {}
      this.elements.form = $('form.create-organization');

      this.rest_api_form = new twentyc.rest.Form(this.elements.form);
      $(this.rest_api_form).on("api-write:success", function() {
        if(this.rest_api_form.redirect) {
          document.location.href = this.rest_api_form.redirect;
        }
      }.bind(this));
    }
  }
);

account.UsersList = twentyc.cls.define(
  "UsersList",
  {
    UsersList : function() {
      this.elements = {}
      this.elements.user_listing = $('.user-listing')

      this.rest_api_list = new twentyc.rest.List(this.elements.user_listing);

      var rest_api_list = this.rest_api_list;

      // user permission management

      this.rest_api_list.formatters.permissions = function(value, data) {
        if(!data.manageable.match(/ud/))
          return;
        var component, editor, widget, container = $('<div>');
        for(component in value) {
          editor = this.template("permissions")
          var label = value[component].label
          widget = new twentyc.rest.PermissionsForm(editor);
          widget.fill(data);
          widget.fill({component:component});
          widget.set_flag_values(value[component]);
          editor.find('[data-field="component"]').text(label);

          $(widget).on("api-write:success", function(e, ev, d, response) {
            this.element.addClass("override");
            var data = response.first();
            data.perms = data.permissions;
            this.set_flag_values(data);
            console.log("DATA",data);
            this.override_id = data["override_id"];
          });

          if(value[component].override) {
            editor.addClass("override");
          }

          var node_remove_override = editor.find('.delete-override')
          node_remove_override.
            data("api-base", widget.base_url).
            data("api-action", "remove_permissions");

          var btn_remove_override = new twentyc.rest.Button(editor.find('.delete-override'));
          widget.override_id = value[component].override;
          btn_remove_override.form = widget;

          $(btn_remove_override).on("api-write:before", function (ev, e, data) {
            data["id"] = this.form.override_id;
          });
          $(btn_remove_override).on("api-write:success", function (ev, e, data, response) {
            $(this.element).parents(".permissions").removeClass("override");
            this.form.set_flag_values(response.first());
          });

          container.append(editor)
        }
        return container;
      }.bind(this.rest_api_list)

      // user role management

      this.rest_api_list.formatters.roles = function(value, data) {
        if(!data.manageable.match(/ud/))
          return;
        var component, container = $('<div>');
        for(component in value) {
          var label = value[component].name;
          var role_id = value[component].role;
          var badge = $('<button>').addClass("btn btn-manage btn-slim role").attr("data-confirm", "Remove user from "+label+" role?");
          badge.append($('<span>').text(label));

          badge.data('api-base', rest_api_list.base_url).
            data('api-action', 'remove_role').
            data('role', role_id).
            data("orguser", data.id);

          var btn_role = new twentyc.rest.Button(badge);

          $(btn_role).on("api-write:before", function (ev, e, data_o, data_r) {
            data_o["org_user"] = data.id;
            data_o["role"] = this.element.data('role');
          });

          $(btn_role).on("api-write:success", function() {
            var orguser = this.element.data("orguser");
            rest_api_list.load().then(() => {
              rest_api_list.element.find('.row-'+orguser+' .manage').trigger("click");
            });
          });

          container.append(badge);
        }

        var role_options_container = $('<div class="dropdown" style="display:inline-block;">');
        var btn_show_role_choices = $('<button>').addClass("btn btn-manage btn-slim-dynamic dropdown-toggle").text('+');
        btn_show_role_choices.
          attr('data-bs-toggle', "dropdown").
          attr('role', 'button').
          attr('type', 'button').
          attr("aria-expanded","false").
          attr('id', 'role-options-'+data.id);
        role_options_container.append(btn_show_role_choices);


        var dd_role_options = $('<div class="dropdown-menu role-options">')
        $(data.role_options).each(function() {

          var i;
          for(i = 0; i < data.roles.length; i++) {
            if(data.roles[i].role == this.id) {
              return;
            }
          }

          var btn_add_role = new twentyc.rest.Button(
            $('<a href="#" class="dropdown-item">').
              data("api-base", rest_api_list.base_url).
              data("api-action", "add_role").
              data("orguser", data.id).
              text(this.name)
          );

          $(btn_add_role).on("api-write:before", (ev, e, data_o, data_r) => {
            data_o["org_user"] = data.id;
            data_o["role"] = this.id;
          });

          $(btn_add_role).on("api-write:success", function() {
            var orguser = this.element.data("orguser");
            rest_api_list.load().then(() => {
              rest_api_list.element.find('.row-'+orguser+' .manage').trigger("click");
            });
          });

          dd_role_options.append(btn_add_role.element);
        })

        role_options_container.append(btn_show_role_choices);
        role_options_container.append(dd_role_options);

        container.append(role_options_container);

        new bootstrap.Dropdown(btn_show_role_choices);

        return container;
      }.bind(this.rest_api_list)

      // user management

      this.rest_api_list.formatters.row = function(row,data) {
        var manage_container = row.filter('.manage')
        if(data.you) {
          row.find('.btn.manage').attr('disabled', true);
          row.find('.btn.manage')
            .text('You')
            .removeClass('btn-manage')
            .addClass('btn-disabled')
        }
        else if(!data.manageable.match(/[ud]/)) {
          row.find('.btn.manage').hide();
        }
        else {
          row.find('.btn.manage').click(function() {
            if(manage_container.is(':visible'))
              manage_container.hide();
            else
              manage_container.show();
          });
        }
        manage_container.hide();
      }

      this.rest_api_list.load();
    }
  }
);

account.PasswordReset = twentyc.cls.define(
  "PasswordReset",
  {
    PasswordReset : function() {
      this.elements = {}
      this.elements.form = $('form.password-reset');

      this.rest_api_form = new twentyc.rest.Form(this.elements.form);
      $(this.rest_api_form).on("api-post:success", function() {
          if(this.rest_api_form.base_url.match(/\/start$/)) {
            this.rest_api_form.element.hide()
            this.rest_api_form.element.siblings('.alert-success').show()
            this.rest_api_form.element.siblings('.alert-info').hide()
          } else {
            document.location.href = "/";
          }
      }.bind(this));
    }
  }
);

account.ServiceApplications = twentyc.cls.define(
  "ServiceApplications",
  {
    ServiceApplications : function() {
      this.element = $('.service-apps-listing');
      this.rest_api_list = new twentyc.rest.List(this.element);

      this.rest_api_list.formatters.row = (row, data) => {

        const redirect_url = data.service_url.replace("{org.slug}", account.org.slug)
        const img =  row.find("img.logo")

        row.attr("href", redirect_url);
        if(!data.logo) {
          img.each(function() {
            $(this).attr("src", $(this).data("logo-url").replace("svc_slug", data.slug));
          })
        } else {
          img.attr("src", data.logo);
        }
      };

      // order services
      $(this.rest_api_list).on("load:after", () => {
        const service_list_order = ["ixctl", "peerctl", "devicectl", "prefixctl", "pdbctl", "aclctl", "aaactl"];
        const service_list = {};
        this.rest_api_list.list_body.find(".row").each(function() {
          service_list[$(this).data("apiobject").slug] = $(this);
        })

        service_list_order.reverse().forEach((value, index) => {
          this.rest_api_list.list_body.prepend(service_list[value]);
        });
      })

      this.rest_api_list.load();


    }
});


account.Services = twentyc.cls.define(
  "Services",
  {
    Services : function() {
      this.element = $('.service-listing');
      this.rest_api_list = new twentyc.rest.List(this.element);

      $(this.rest_api_list).on("insert:after", (e, row, data) => {
        var item_heading = row;
        item_heading.addClass('item-group clearfix');
        var total_cost = 0;

        var item_table = $('<table>').addClass('item-table');
        item_heading.after(item_table);
        data.items.forEach((item, idx, array) => {
          var ihf = new this.itemHtmlFormatter(item);
          item_table.append(
            $('<tr>').append([
              ihf.formattedDescription(),
              ihf.formattedUsageType(),
              ihf.formattedUsageAmount(),
              ihf.formattedLink().hide(),
              ihf.formatted_expiration_date(),
              ihf.formattedCost()
            ])
          )
          total_cost += parseFloat(item.cost);
        });
        item_table.children().first().children().addClass('pt-2');
        item_table.children().last().children().addClass('pb-2');
        item_table.after($('<tr>').addClass('blank-row'));

        const item_cost_summary = $('<div>').addClass("row align-items-center").append([
          $('<div>').text('Total Monthly Cost: ').addClass('light-grey col-auto px-0'),
          $('<div>').text('$' + Number(total_cost).toFixed(2)).addClass('table-text-bold white col-auto ps-1'),
          $('<div>').addClass('col'),
        ]);
        if (data.subscription_cycle) {
          item_cost_summary.append(
            $('<div>').html(
              `${data.subscription_cycle.start} <span class="light-grey">to</span> ${data.subscription_cycle.end}`
            ).addClass('ms-auto col-auto pe-0')
          );
        }

        item_heading.children().addClass('px-0').append(
          $('<div>').addClass('container-fluid').append(item_cost_summary)
        );
      });

      $(this.rest_api_list).on("load:after", () => {
        if ( $("#serviceListBody:empty").length ){
          $('#serviceListBody')
            .append('<tr><td class="pt-0 pb-3 px-0">No service subscriptions</td></tr>')
        }
      })

      this.rest_api_list.load();
    },

    itemHtmlFormatter: function(item) {
      this.description = item.description;
      this.type = item.type;
      this.usage = item.usage;
      this.cost = item.cost;
      this.unit_name_plural = item.unit_name_plural;
      this.unit_name = item.unit_name;
      this.expiration_date = item.expiration_date;

      this.formattedDescription = () => {
        return $('<td>').text(this.description).addClass('dark-grey table-text-bold')
      }

      this.formattedUsageType = () => {
        if(this.type == "Fixed Price") {
          return $('<td>');
        } else {
          return $('<td>').append([
            $('<span>').text('Usage: ').addClass('light-grey table-text-thin'),
            $('<span>').text(this.editedUsageType()).addClass('dark-grey table-text-large')
          ])
        }
      }

      this.editedUsageType = () => {
        if ( this.type == 'Metered Usage') {
          return 'metered'
        }
        else {
          return this.type.toLowerCase()
        }
      }

      this.formattedUsageAmount = () => {
        if(this.type == "Fixed Price") {
          return $('<td>');
        } else {
          return $('<td>').append([
            $('<span>').text('Usage: ').addClass('light-grey table-text-thin'),
            $('<span>').text(this.editedUsageAmount()).addClass('dark-grey table-text-large')
          ])
        }
      }

      this.editedUsageAmount = () => {
        if ( this.usage === 1 ){
          return this.usage + ' ' + this.unit_name
        } else {
          return this.usage + ' ' + this.unit_name_plural
        }
      }

      this.formattedLink = () => {
        return $('<td>').addClass('small-links').append(
          $('<a>').attr('href','/').text('Details')
        )
      }

      this.formatted_expiration_date = () => {
        return $('<td>').addClass('light-grey').text(
          this.expiration_date ? 'Expires at ' + window.fullctl.formatters.datetime(this.expiration_date) : ''
        )
      }

      this.formattedCost = () => {
        return $('<td>').text('$' + Number(this.cost).toFixed(2)).addClass('dark-grey table-text-large text-align-right right')
      }
    }
});


account.PersonalAPIKeys = twentyc.cls.define(
  "PersonalAPIKeys",
  {
    PersonalAPIKeys: function() {
      this.element = $('.personal-keys');
      this.rest_api_list = new twentyc.rest.List(this.element);

      this.rest_api_list.formatters.created = function(value, data){
        var d = new Date(value);
        return d.toDateString().split(' ').slice(1).join(' ')
      }


      $(this.rest_api_list).on("insert:after", (e, row, data) => {
        this.enableShowButton(row, data);
        this.enableCopyButton(row);
      })

      this.rest_api_list.formatters.readonly = function(value) {

        if(value)
          return "read-only"
        return ""
      };

      // Modal
      var key_form = $('form.create_key');
      if ( key_form.length ){
        this.rest_key_form = new twentyc.rest.Form(key_form);
        $(this.rest_key_form).on("api-write:success", function() {
          $('#personalApiKeyModal').modal('toggle');
          this.rest_api_list.load();
        }.bind(this));
      }


      this.rest_api_list.load();
    },
    enableShowButton: function(row, data) {
      var key = data.key;
      var redacted_key = key.replace(key.slice(2,-2), '*'.repeat(key.length-4));
      var keybox_redacted = row.find('.personal-key-box-redacted');
      var keybox_display = row.find('.personal-key-box');
      var show_button = row.find('.show-button');

      keybox_redacted.val(redacted_key);
      keybox_display.val(key);

      show_button.click(() => {
        keybox_redacted.toggleClass('d-none');
        keybox_display.toggleClass('d-none');
      })
    },
    enableCopyButton: function(row) {
      var copy_button = row.find('.copy-button');
      var keybox_redacted = row.find('.personal-key-box-redacted');
      var keybox_display = row.find('.personal-key-box');
      copy_button.click(() => {
          if ( keybox_display.hasClass('d-none') ){
            keybox_redacted.addClass('d-none');
            keybox_display.removeClass('d-none');
            keybox_display.select();
            document.execCommand("copy");
            keybox_redacted.removeClass('d-none');
            keybox_display.addClass('d-none');
            keybox_redacted.select();
          } else {
            keybox_display.select();
            document.execCommand("copy");
          }
      })
    }
})

account.PersonalInvites = twentyc.cls.define(
  "PersonalInvites",
  {
    PersonalInvites: function() {
      this.element = $('.personal-invites');
      this.rest_api_list = new twentyc.rest.List(this.element);

      $(this.rest_api_list).on("api-get:success", (ev, e, d, response) => {
        if(response.content.data.length > 0)
          $('#count-invites').text("("+response.content.data.length+")");
      });

      this.rest_api_list.formatters.row = (row, data) => {
        var button_accept = new twentyc.rest.Button(row.find('button.accept-invite'));
        var button_reject = new twentyc.rest.Button(row.find('button.reject-invite'));

        button_accept.format_request_url = (url) => {
          return url.replace(/invite_id/g, data.id);
        }

        button_reject.format_request_url = (url) => {
          return url.replace(/invite_id/g, data.id);
        }

        $(button_reject).on("api-write:success", () => {
          this.rest_api_list.load();
        });

        $(button_accept).on("api-write:success", () => {
          this.rest_api_list.load();
          window.controlpanel.loadDropDown();
          window.controlpanel.styleDropDown();
        });

      };

      this.rest_api_list.load();
    }
  }
)



account.PendingUsers = twentyc.cls.define(
  "PendingUsers",
  {
    PendingUsers: function() {
      this.elements = {}
      this.elements.pending_user_listing = $('.pending-user-listing');
      this.rest_api_list = new twentyc.rest.List(this.elements.pending_user_listing);


      this.rest_api_list.formatters.created = function(value, data){
        var d = new Date(value);
        return d.toDateString().split(' ').slice(1).join(' ')
      }

      this.rest_api_list.formatters.user_name = function(value, data){
        let content = value;

        if ( value === '' ) {
          content += '<span class="user-badge ub-pending">Pending</span>';
        } else {
          content += '<span class="user-badge ub-pending ms-2">Pending</span>';
        }

        if (data.role == "admin") {
          content += '<span class="user-badge ub-admin">admin</span>';
        }

        return content
      }

      $(this.rest_api_list).on("insert:after", (e, row, data) => {
        var client = new twentyc.rest.Client("/api/account");
        const invite = row.data('apiobject');
        if ( invite.user_name === '' ) {
          row.find('.name-column').addClass('text-center');
        }

        var payload = {
          email: data.email,
          service: "",
        }

        // wire resend invite button

        var a = row.find('.resend-invite');
        if ( a.length ){
          var endpoint = `org/${data.slug}/invite`;
          a.click(() => client.post(endpoint, payload));
          $(client).on('api-write:success', () => {
            // Initialize popover
            a.popover({
              trigger: 'manual',
              content: `Invite re-sent to ${data.email}`
            })
            a.popover('show');
            setTimeout(() => {
              a.popover('hide');
              a.popover('dispose');
            }, 2000);
          })
          $(client).on('api-write:error', (event, endpoint, data, response) => {
            // Initialize popover
            var error_message = response.http_status_text();
            a.popover({
              trigger: 'manual',
              html: true,
              content: `<p style="color:red;">${error_message}</p>`,
            })
            a.popover('show');
            setTimeout(() => {
              a.popover('hide');
              a.popover('dispose');
            }, 6000);

          });
        }

      })

      // Modal
      this.elements.invitation_form = $('form.invite');
      if ( this.elements.invitation_form.length ){
        this.rest_invite_form = new twentyc.rest.Form(this.elements.invitation_form);
        $(this.rest_invite_form).on("api-write:success", function() {
          this.rest_invite_form.reset();
          $('#inviteModal').modal('toggle');
          this.rest_api_list.load();
        }.bind(this));
      }

      this.rest_api_list.load();
    }
})


account.expand_user_info = () => {
  // only run if the user info section is present
  // TODO: don't load this file at places where this doesn't exist
  if ($('#userInfoCollapse').length == 0) {
    return
  }

  $('#userInfoCollapse').addClass('show');
  $('#userInfoCollapse').parent(".accordion-item").find(".collapsed").removeClass("collapsed");
  $('#userInformation').get(0).scrollIntoView();
}

/**
 * Expand account edit if account is the edit parameter in the URL
 *
 * @method account.handleEditUrlParameter
 */
account.handleEditUrlParameter = () => {
  const urlSearchParams = new URLSearchParams(window.location.search);
  const editParameter = urlSearchParams.get("edit");
  if (editParameter) {
    if (editParameter == "account") {
      account.expand_user_info();
    } else if (editParameter == "new-org") {
      $('#createOrgModal').modal('show');
    }
  }
}

$(document).ready(() => {
  account.handleEditUrlParameter();
});

})();
