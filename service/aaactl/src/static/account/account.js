(function() {

window.account = {}

account.api_client = new twentyc.rest.Client("/api/account")

account.ControlPanel = twentyc.cls.define(
  "ControlPanel",
  {
    ControlPanel : function() {
      this.elements = {};
      this.elements.select_org = $('select.select-org');
      this.select_org = new twentyc.rest.Select(this.elements.select_org)
      $(this.select_org).on("api-post:success", function() {
        document.location.href = "/";
      });
    }
  }
);



account.ChangeInformation = twentyc.cls.define(
  "ChangeInformation",
  {
    ChangeInformation : function() {
      this.elements = {}
      this.elements.form = $('form.change-information');

      this.rest_api_form = new twentyc.rest.Form(this.elements.form);
      $(this.rest_api_form).on("api-write:success", function() {
        if(this.rest_api_form.redirect) {
          document.location.href = this.rest_api_form.redirect;
        } else {
          alert("User information updated!")
        }
      }.bind(this));
    }
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
          alert("User password updated!")
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


account.Invite = twentyc.cls.define(
  "Invite",
  {
    Invite : function() {
      this.elements = {}
      this.elements.form = $('form.invite');

      this.rest_api_form = new twentyc.rest.Form(this.elements.form);
      $(this.rest_api_form).on("api-write:success", function() {
        if(this.rest_api_form.redirect) {
          document.location.href = this.rest_api_form.redirect;
        } else {
          alert("Invitation sent")
        }
      }.bind(this));
    }
  }
);


account.UsersList = twentyc.cls.define(
  "UsersList",
  {
    UsersList : function() {
      this.element = $('.user-listing')
      this.rest_api_list = new twentyc.rest.List(this.element);

      this.rest_api_list.formatters.name = function(value, data) {
        return $('<span>').append(
          $('<span>').text(value),
          $('<strong>').text(data.you?" (You)":"")
        );
      }

      this.rest_api_list.formatters.permissions = function(value, data) {
        if(!data.manageable.match(/ud/))
          return;
        var component, editor, widget, container = $('<div>');
        for(component in value) {
          editor = this.template("permissions")
          editor.find('[data-field="component"]').text(component);
          widget = new twentyc.rest.PermissionsForm(editor);
          widget.fill(data);
          widget.fill({component:component});
          widget.set_flag_values(value[component]);
          container.append(editor)
        }
        return container;
      }.bind(this.rest_api_list)


      this.rest_api_list.formatters.row = function(row,data) {
        var manage_container = row.filter('.manage')
        if(data.you)
          row.find('.btn.manage').attr('disabled', true);
        else if(!data.manageable.match(/[ud]/))
          row.find('.btn.manage').hide();
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




})();
