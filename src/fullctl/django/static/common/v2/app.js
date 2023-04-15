(function($, $tc) {


window.fullctl = {
  urlparam : new URLSearchParams(window.location.search)
}
var fullctl = window.fullctl;

fullctl.template = function(name) {
  return $('[data-template="'+name+'"]').clone().attr("data-template",null);
}

fullctl.application = {}
fullctl.widget = {}
fullctl.formatters = {}
fullctl.modals = {}
fullctl.util = {}
fullctl.help_box = {}
fullctl.static_path = "/s/0.0.0-dev/"


fullctl.util.slugify = (txt) => {
  return txt.toLowerCase().replace(/\s/g, "-").replace(/_/g, "-").replace(/[^a-zA-Z0-9-]/g,"").replace(/-+/g, '-');
};

/**
 * Works similarly to the django `static` template tag and will
 * return the full path to a static file
 * @param {String} path path to file
 * @returns {String} full path to file
 */

fullctl.util.static = (path) => {
  return fullctl.static_path+path;
};

fullctl.formatters.pretty_speed = (value) => {
  if(value >= 1000000)
    value = parseInt(value / 1000000)+"T";
  else if(value >= 1000)
    value = parseInt(value / 1000)+"G";
  else
    value = value+"M";
  return value
}

fullctl.formatters.monitor_status = (value) => {
  if(value == "ok") {
     return $('<span>').addClass('active').text('Active');
  } else if(value == "deactivated") {
     return $('<span>').addClass('inactive').text('Stopped');
  }
  return value
}

fullctl.formatters.meta_data = (value) => {
  if(!value)
    return;

  var k, node = $('<div>');
  for(k in value) {
    node.append($('<div>').addClass("badge").text(k+": "+value[k]));
  }
  return node;
}

/**
 * Formats `True` and `False` as checkmark and cross
 * @method pretty_bool
 * @param {String} value value of cell
 * @param {Object} data object literal of row data
 * @param {Object} cell jQuery object for container
 */

fullctl.formatters.yesno = (value, data, cell) => {
  var path;
  if(value && value !== "") {
    path = fullctl.util.static("common/icons/Indicator/Check-Ind/Check.svg");
  } else {
    path = fullctl.util.static("common/icons/Indicator/X-Ind/X.svg");
  }
  return $('<img>').attr("src", path).addClass("indicator");
}

fullctl.loading_animation = () => {
  var anim = $('<div class="spinner loadingio-spinner-bars-k879i8bcs9"><div class="ldio-a9ruqenne8l"><div></div><div></div><div></div><div></div></div></div>');
  return $('<div>').addClass("loading-anim").append(anim);
}

fullctl.widget.Wizard = $tc.define(
  "Wizard",
  {
    Wizard : function(jq) {
      this.element = jq;
      this.step = 1;
      this.element.addClass("wiz-step wiz-step-1");

      var wizard = this;

      this.element.find('button[data-wizard-step]').click(function() {
        wizard.set_step($(this).data("wizard-step"));
      });
    },

    set_step : function(n) {
      this.element.removeClass("wiz-step-"+this.step);
      this.element.addClass("wiz-step-"+n);
      this.step = n;
    }
  }

);

fullctl.widget.StatusBadge = $tc.extend(
  "StatusBadge",
  {

    StatusBadge : function(base_url, jq, refresh_values) {
      this.row_id = jq.data("row-id")
      this.field_name = jq.data("name")
      this.refresh_time = parseInt(jq.data("refresh") || 1000);
      this.loading_shim_disabled = true;
      this.refresh_timer = new twentyc.util.SmartTimeout(()=>{},1000);
      this.refresh_values = refresh_values;
      this.Widget(base_url, jq);
    },


    spinner : function() {
			return $('<div class="spinner loadingio-spinner-bars-k879i8bcs9"><div class="ldio-a9ruqenne8l"><div></div><div></div><div></div><div></div></div></div>');
    },

    load : function() {
      return this.get().then((response) => {
        response.rows((row) => {
          if(row.id == this.row_id) {
            var value = row[this.field_name];
            this.render(value, row);
          }
        })
      });
    },

    refresh : function() {
      this.refresh_timer.set(
        ()=>{this.load()},
        this.refresh_time
      );
    },

    render : function(value, row) {
      this.element.removeClass().addClass("status-badge "+value)
      this.element.empty().append($('<span>').text(value));
      if(this.refresh_values && $.inArray(value, this.refresh_values) == -1) {
          this.element.append(this.spinner());
          this.refresh();
      }

    }
  },
  twentyc.rest.Widget
);

fullctl.widget.OrganizationSelect = $tc.extend(
  "OrganizationSelect",
  {
    OrganizationSelect : function(jq) {
      this.Select(jq);
    }
  },
  twentyc.rest.Select
);

// v2 - list witch checkboxes and a delete selected button
fullctl.widget.SelectionList = $tc.extend(
  "SelectionList",
  {
    SelectionList : function(jq, jq_delete_selected_button) {
      this.List(jq);
      this.delete_selected_button = jq_delete_selected_button;

      this.list_head.find('tr').first().prepend(
        '<th class="center checkbox-cell">'+
          '<input type="checkbox" value="all">'+
        '</th>'
      );

      $(this).on("load:after", () => {
        this.set_delete_selected_button();
        this.unselect_select_all_checkbox();
      });

      // select checkbox by clicking on th
      this.list_head.find('th.checkbox-cell ').click(function(e) {
        let checkbox = $(this).find('input[type="checkbox"][value="all"]');
        if(!$(e.target).is(checkbox)) {
          checkbox.prop('checked', !checkbox.prop('checked')).change();
        }
      })

      let selection_list = this;
      this.list_head.find('th input[type="checkbox"][value="all"]').change(function() {
        if ($(this).prop("checked")) {
          selection_list.select_all();
        } else {
          selection_list.unselect_all();
        }
        selection_list.set_delete_selected_button();
      });
    },

    build_row : function(data) {
      return this.template('row').prepend(
        '<td class="select-checkbox checkbox-cell center">'+
          '<input type="checkbox" class="row-chbx" name="list-row">'+
        '</td>');
    },

    insert : function(data) {
      var row_element;

      row_element = this.build_row(data);

      this.apply_data(data, row_element);

      if(this.formatters.row) {
        this.formatters.row(row_element, data)
      }

      // select checkbox by clicking on td
      row_element.find('.checkbox-cell').click(function(e) {
        let checkbox = row_element.find('.row-chbx');
        if(!$(e.target).is(checkbox)) {
          checkbox.prop('checked', !checkbox.prop('checked')).change();
        }
      });

      row_element.find('.row-chbx').change(() => {
        this.set_delete_selected_button();
        this.unselect_select_all_checkbox();
      });

      row_element.data("apiobject", data);
      row_element.addClass("row-"+data[this.id_field])

      this.list_body.append(row_element)
      this.wire(row_element)

      $(this).trigger("insert:after", [row_element, data]);

      return row_element
    },

    unselect_select_all_checkbox : function() {
      this.list_head.find('th input[type="checkbox"][value="all"]:checked').prop("checked", false);
    },

    set_delete_selected_button : function() {
      if(this.get_selected_rows().length > 0) {
        this.show_delete_selected_button();
      } else {
        this.hide_delete_selected_button();
      }
    },

    show_delete_selected_button : function () {
      this.delete_selected_button.removeClass("js-hide");
    },

    hide_delete_selected_button : function() {
      this.delete_selected_button.addClass("js-hide");
    },

    select_all : function() {
      this.list_body.find('td.select-checkbox input.row-chbx').prop('checked', true);
    },

    unselect_all : function() {
      this.list_body.find('td.select-checkbox input.row-chbx').prop('checked', false);
    },

    delete_selected_list : function(endpoint="id") {
      let selected_rows = this.get_selected_rows();
      let list = this;
      let promises = new Array();
      let apiobj;
      selected_rows.each(function() {
        apiobj = $(this).data("apiobject");
        promises.push(
          list.delete_api_obj(apiobj, endpoint).then((request) => {
            list.remove(request.content.data[0]);
          })
        );
      });
      Promise.all(promises).then(() => {list.set_delete_selected_button()});
    },

    delete_api_obj : function(apiobj, endpoint) {
      let delete_url = this.element.data('api-delete-url');
      if (delete_url) {
        delete_url = delete_url.replace(/0\//, apiobj[endpoint]);
        return this.write(null, apiobj, "delete", delete_url);
      }

      return this.delete(apiobj[endpoint], apiobj);
    },

    get_selected_rows : function() {
      return $(this.list_body.find("tr .row-chbx:checked")).parentsUntil("tbody", "tr");
    },
  },
  twentyc.rest.List
);

fullctl.application.Component = $tc.define(
  "Component",
  {
    Component : function(name) {
      this.name = name;
      this.jquery = $('[data-component="'+name+'"]')
      var elements = this.elements = this.$e = {}
      var templates = this.templates = this.$t = {}

      this.widgets = this.$w = {};

      this.jquery.find('[data-element]').each(function(idx) {
        elements[$(this).data("element")] = $(this);
      });

      this.jquery.find('[data-template]').each(function(idx) {
        templates[$(this).data("template")] = $(this);
      });

      this.wire_elements();
    },

    template : function(name, appendTo) {
      var element = this.$t[name].clone().attr('data-template',null);
      if(appendTo)
        element.appendTo(appendTo)
      return element;
    },

    widget : function(name, fn) {
      fn = fn.bind(this);
      var widget = this.$w[name] = fn(this.$e, this.$t);
      return widget;
    },

    wire_elements : function() {
    }
  }
);

/**
 * Modal widget
 *
 * @class Modal
 * @extends fullctl.application.Component
 * @namespace fullctl.application
 * @constructor
 * @param {string} type type of modal
 * @param {string} title title to use for modal
 * @param {jQuery result} content jquery result holding the element to insert into modal body
 */

fullctl.application.Modal = $tc.extend(
  "Modal",
  {
    Modal : function(type, title, content) {
      this.Component("modal_"+type)
      this.set_title(title);
      this.set_content(content);

      var modal = this;

      content.find('.modal-action-note-text').each(function() {
        $(this).appendTo(modal.jquery.find('.modal-action-note'))
      });

      this.show();
    },
    show : function() {
      this.jquery.modal('show');
    },
    hide : function() {
      this.jquery.modal('hide');
    },
    set_title : function(title) {
      this.jquery.find('.modal-title').text(title);
    },
    set_content : function(content) {
      this.jquery.find('.modal-body').empty().append(content);
    }
  },
  fullctl.application.Component
);

fullctl.application.Tool = $tc.extend(
  "Tool",
  {
    Tool : function(name) {
      this.Component(name);
      this.init();
      this.menu();
      if (this.$t["bottom-menu"]) {
        this.bottom_menu();
      };
      this.active = false;
    },

    init : function() {
    },

    sync : function() {

    },

    hide : function() {
      this.$e.body.parents(".tool").hide();
    },

    show : function() {
      this.$e.body.parents(".tool").show();
    },

    menu : function() {
      let menu = this.template("menu")
      this.$e.menu.append(menu);
      return menu
    },

    // v2 - add bottom menu
    bottom_menu : function() {
      let bottom_menu = this.template("bottom-menu");
      this.$e.bottom_menu.append(bottom_menu);
      return bottom_menu
    },

    activate : function() {
      this.active = true
    },

    deactivate : function() {
      this.active = false
    },

    apply_ordering: function() {
      //deprecated
      return;
    },

    initialize_sortable_headers: function() {
      //deprecated
      return;
    },

    custom_dialog : function(title) {
      this.$e.body.empty();
      var custom_dialog = $('<div>').addClass("tool-custom")
      custom_dialog.append($('<h4>').addClass("tool-title").text(title));
      this.$e.body.append(custom_dialog);
      return custom_dialog;
    },

  },
  fullctl.application.Component
);

fullctl.application.TabbedTool = $tc.extend(
  "TabbedTool",
  {
    "TabbedTool" : function(name) {
      this.Tool(name)
    },

    menu : function() {
      var menu = this.Tool_menu()

      var tool = this;
      var urlparam = this.urlparam

      if(urlparam) {
        var preselect = fullctl.urlparam.get(urlparam)
      } else {
        var preselect = false;
      }

      this.widget('tabs_fetcher', ($e) => {
        var w = new twentyc.rest.List(menu)

        w.formatters.row = (row, data) => {
          if(!w.element.find(".active").length) {
            if(!preselect || preselect == ""+data[urlparam])
              tool.tab(row, data);
          }

          row.click(function() {
            tool.tab(row, data);
            if(urlparam)
              window.history.replaceState({}, document.title, "?"+urlparam+"="+data[urlparam])
          });
        }

        $(w).on("api-read:success", (event, endpoint, payload, response) => {
          if(!response.content.data.length) {
            this.hide();
          } else {
            this.show();
          }
        });
        $(w).on("api-read:error", ()=> {
          this.hide();
        })

        w.load()
        return w;
      })

      return menu
    },

    tab : function(tab, data) {
      tab.siblings().removeClass("active")
      tab.addClass("active")
    }


  },
  fullctl.application.Tool
);

fullctl.application.Header = $tc.extend(
  "Header",
  {
    Header : function() {
      this.Component("header");

    },

    wire_elements : function() {

      this.widget('select_org', ($e) => {
        var w = new twentyc.rest.List($e.select_org);
        var org = $e.select_org.data('org')
        $(w).on("insert:after", (e, row, data) => {
          if(org == data.slug) {
            row.addClass('selected')
            row.find('.manage').click(() => {
              window.location = fullctl.aaactl_urls.manage_org;
            });
          } else {
            row.find('.manage').hide();
            row.click(() => {
              window.location.href = "/"+data.slug+"/";
            })
          }
        });
        w.load()

        this.wire_app_switcher();
        this.wire_stop_impersonation();

        return w;
      });
    },

    /**
     * wires the service application switcher in the header
     * @method wire_app_switcher
     * @return {void}
     */

    wire_app_switcher : function() {
      this.widget("app_switcher", ($e) => {
        var others = $e.app_switcher.find('.others')
        const selected = $e.app_switcher.find('.selected')
        selected.click(() => {
          others.show();
          selected.addClass('app_bg muted');
        });
        $(document.body).click(function(e) {
          if (
            !( $(e.target).is(selected) || $(e.target).parent().hasClass('selected') )
          ) {
            others.hide();
            selected.removeClass('app_bg muted');
          }
        });
        return {};
      });
    },

    /**
     * wires the stop impersonation button in the header
     * @method wire_stop_impersonation
     */

    wire_stop_impersonation : function() {

      var stop_impersonation = $('[data-element="stop_impersonation"]')
      if(!stop_impersonation.length)
        return;

      this.widget("stop_impersonation", ($e) => {
        var button = new twentyc.rest.Button(stop_impersonation);
        $(button).on("api-write:success", (event, endpoint, payload, response) => {
          window.location.href = "/";
        });
      });
    }


  },
  fullctl.application.Component
);

fullctl.application.Pages = $tc.extend(
  "Pages",
  {
    Pages : function() {
      this.Component("pages");
    }
  },
  fullctl.application.Component
);


fullctl.application.Toolbar = $tc.extend(
  "Toolbar",
  {
    Toolbar : function() {
      this.Component("toolbar");
    }
  },
  fullctl.application.Component
);

/**
 * Start-Trial button widget
 *
 * @class TrialButton
 * @extends twentyc.rest.Button
 * @constructor
 * @param {Object} element - the element to attach the widget to
 */

fullctl.application.TrialButton = $tc.extend(
  "TrialButton",
  {
    TrialButton : function(element) {
      this.Button(element);
      // set service id from data-service-id attribute, if present
      // otherwise use fullctl.service.id

      this.service_id = this.element.data("service-id") || fullctl.service_info.id;
    },

    payload : function() {
      return {
        service_id : this.service_id
      }
    }
  },
  twentyc.rest.Button
);


fullctl.application.Application = $tc.define(
  "Application",
  {
    Application : function(id) {
      this.id = id;
      this.components = this.$c = {
        header : new fullctl.application.Header(),
        toolbar : new fullctl.application.Toolbar(),
        main : new fullctl.application.Component("main")
      }
      this.tools = this.$t = {}
      $(fullctl.application).trigger("initialized", [this, id]);
      $('[data-grainy-remove]').each(function() {
        $(this).grainy_toggle($(this).data("grainy-remove"), "r");
      });


      $('[data-bs-toggle="tab"]').on('show.bs.tab', function() {
        window.history.replaceState({}, document.title, $(this).attr("href"));
      });

      fullctl[id] = this;

      // wire start trial button for current service

      var trial_button_element = $('[data-element=btn_start_trial]')
      if(trial_button_element.length) {
        var trial_button = new fullctl.application.TrialButton(trial_button_element);
        $(trial_button).on("api-write:success", () => {
          window.location.reload();
        });
      }

      // wire start trial buttons for cross promoted services

      var crosspromo_trial_button_element = $('[data-element=btn_start_trial_crosspromo]');
      crosspromo_trial_button_element.each(function(idx,button) {
        var trial_button = new fullctl.application.TrialButton($(button));
        $(trial_button).on("api-write:success", () => {
          $(button).parents(".alert").find('.msg-start-trial').hide();
          $(button).parents(".alert").find('.msg-trial-started').show();
        });
      });


      this.application_access_granted = grainy.check("service."+this.id+"."+fullctl.org.id, "r");

    },

    autoload_page : function() {
      var hash = window.location.hash;
      if(hash) {
        hash = hash.substr(1);

        parts = hash.split(";");
        hash = parts[0];

        this.autoload_args = parts;

        if(this.get_page(hash)) {
          this.page(hash);
        }
      }
    },

    autoload_arg : function(idx) {
      if(this.autoload_args) {
        var value = this.autoload_args[idx];
        if(value) {
          this.autoload_args[idx] = null;
        }
        return value;
      }
      return null;
    },

    tool : function(name, fn) {
      fn = fn.bind(this);
      var tool = this.$t[name] = fn()
      return tool;
    },

    sync : function() {
      var i, app = this;
      for(i in this.$t) {
        if(this.$t[i].active) {
          this.$t[i].sync(app);
        }
      }

    },

    /**
     * Gets the element representing the page in the pages menu.
     *
     * @method get_page
     * @param {String} page Value set for aria-controls
     */
    get_page : function(page) {
      return $('[data-component="pages"]').find('[aria-controls="'+page+'"]');
    },

    page : function(page) {
      this.get_page(page).tab('show');
    },

    /**
     * Makes visible the page in the pages menu so you can navigate to the tab
     *
     * @method show_page
     * @param {String} page Value set for aria-controls
     */
    show_page : function(page) {
      this.get_page(page).show();
    },

    /**
     * Hides the page in the pages menu so you can't navigate to the tab
     *
     * @method hide_page
     * @param {String} page Value set for aria-controls
     */
    hide_page : function(page) {
      this.get_page(page).hide();
    }
  }
);

fullctl.application.ContainerApplication = $tc.extend(
	"ContainerApplication",
	{
    init_container : function(ref_tag, ref_tag_p) {
      this[ref_tag_p] = this.containers = {}
      this[ref_tag+"_slugs"] = this.container_slugs = {}

      var selector_name = "select_"+ref_tag;

      this.selector_name = selector_name;
      this.title_base = window.document.title;

      this.$c.toolbar.widget(selector_name, ($e) => {
        var e = $e[selector_name];
        var w = new twentyc.rest.Select(e);
        $(w).on("load:after", (event, element, data) => {
          var i;
          for(i = 0; i < data.length; i++) {
            this.containers[data[i].id] = data[i];
            this.container_slugs[data[i].id] = data[i].slug;
          }

          if(data.length == 0) {
            e.attr('disabled', true);
            $(this).trigger("no-containers", []);
            this.permission_ui();
          } else {
            e.attr('disabled', false)
            this.permission_ui();
          }
        });
        return w
      });

      $(this.$c.toolbar.$w[selector_name]).one("load:after", () => {

        if(this["preselect_"+ref_tag]) {
          this[selector_name](this["preselect_"+ref_tag])
        } else {
          this.sync();
          this.sync_url(this.$c.toolbar.$e[selector_name].val());
          this.sync_title(this.$c.toolbar.$e[selector_name].val());
        }
      });

      $(this.$c.toolbar.$e[selector_name]).on("change", () => {
        this.sync();
        this.sync_url(this.$c.toolbar.$e[selector_name].val())
        if(this.$t.settings) { this.$t.settings.sync(); }
      });

      this[ref_tag] = function() { return this.container(); }.bind(this);
      this[ref_tag+"_slug"] = function() { return this.container_slug(); }.bind(this);
      this[ref_tag+"_object"] = function() { return this.container_object(); }.bind(this);
      this["unload_"+ref_tag] = function() { return this.unload_container(); }.bind(this);
      this["select_"+ref_tag] = function(id){ return this.select_container(id); }.bind(this);
      this["refresh_select_"+ref_tag] = function() { return this.refresh_select_container(); }.bind(this);
    },

    permission_ui : function () { return; },

    container : function() {
      return this.$c.toolbar.$w[this.selector_name].element.val();
    },

    container_slug : function() {
      return this.container_slugs[this.container()];
    },

    container_object: function() {
      return this.containers[this.container()]
    },

    unload_container : function(id) {
      delete this.containers[id];
      delete this.container_slugs[id];
    },

    select_container : function(id) {
      if(id)
        this.$c.toolbar.$e[this.selector_name].val(id);
      else {
        id = this.$c.toolbar.$e[this.selector_name].find('option').val();
        this.$c.toolbar.$e[this.selector_name].val(id);
      }

      this.sync();
      this.sync_url(id);
      this.sync_title(id);
    },

    sync_title : function(id) {
      var container = this.containers[id];
      if(container)
        window.document.title = this.title_base + " / " + container.slug;
      else
        window.document.title = this.title_base;
    },

    sync_url: function(id) {
      var container = this.containers[id];
      var url = new URL(window.location)
      if(!container) {
        $('#no-container-notify').show();
        url.pathname = `/${fullctl.org.slug}/`
      } else {
        url.pathname = `/${fullctl.org.slug}/${container.slug}/`
        $('#no-container-notify').hide();
      }
      window.history.pushState({}, '', url);
    },

    refresh : function() {
      return this.refresh_select_container();
    },

    refresh_select_container : function() {
      return this.$c.toolbar.$w[this.selector_name].refresh();
    }




	},
	fullctl.application.Application
)


fullctl.application.Orgctl = $tc.extend(
  "Orgctl",
  {

  },
  fullctl.application.Tool
)

fullctl.application.Orgctl.Users = $tc.extend(

  "Users",
  {
    Users : function() {
      this.Component("user_listing");
    },

    wire_elements : function() {
      this.rest_api_list = new twentyc.rest.List(this.jquery);

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
          row.find('.btn-permissions').attr('disabled', true);
        else if(!data.manageable.match(/[ud]/))
          row.find('.btn-permissions').hide();
        else {
          row.find('.btn-permissions').click(function() {
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
  },
  fullctl.application.Component
);

fullctl.application.Orgctl.PermissionsModal = $tc.extend(
  "PermissionsModal",
  {
    PermissionsModal : function() {
      var user_listing = new fullctl.application.Orgctl.Users();
      this.Modal("manage", fullctl.org.name+" User Permissions", user_listing.jquery);
    }
  },
  fullctl.application.Modal
);

fullctl.TemplateSelect = $tc.extend(
  "TemplateSelect",
  {
    load_params : function() {
      //to override
    }
  },
  twentyc.rest.Select
)

fullctl.TemplatePreview = $tc.extend(
  "TemplatePreview",
  {
    TemplatePreview: function(jq, select_widget, type) {
      this.Form(jq);
      this.select = new select_widget(this.element.find('select'));
      this.editor = this.element.find('textarea');
      this.type = type;

      if(type) {
        this.select.filter = (tmpl) => {
          return tmpl.type == type;
        };
      }

      $(this.select).on("load:after", ()=>{ this.preview();});
      $(this.select.element).on("change", ()=>{ this.preview();});
      $(this).on("api-write:success", (ev,ep,data,response) => {
          this.editor.val(response.first().body);
      });

      this.select.load();
    },

    payload : function() {
      return { type: this.type }
    },

    preview : function() {
      var tmpl_id = parseInt(this.select.element.val())
      if(tmpl_id)
        var url = this.editor.data("api-preview").replace("tmpl_id", tmpl_id);
      else
        var url = this.editor.data("api-preview-default").replace("type", this.type);

      this.base_url = url;

      this.submit();
    }
  },
  twentyc.rest.Form
);

// v2 - Preview with codeblock with alternating colors
fullctl.ConfigPreview = $tc.extend(
  "ConfigPreview",
  {
    ConfigPreview: function(jq, select_widget, type) {
      this.Form(jq);
      this.select = new select_widget(this.element.find('select'));
      this.codeblock = this.element.find('pre.codeblock');
      this.type = type;

      if(type) {
        this.select.filter = (tmpl) => {
          return tmpl.type == type;
        };
      }

      $(this.select).on("load:after", ()=>{ this.preview();});
      $(this.select.element).on("change", ()=>{ this.preview();});
      $(this).on("api-write:success", (ev,ep,data,response) => {
          // create codeblock
          this.codeblock.html("");
          let lines = response.first().body.split(/\r?\n/);
          lines.forEach(line => {
            let code_line = document.createElement("code");
            code_line.innerText = line || " ";
            this.codeblock.append(code_line);
          });
      });

      this.select.load();
    },

    payload : function() {
      return { type: this.type }
    },
    preview : function() {
      let tmpl_id = parseInt(this.select.element.val())
      let url;
      if(tmpl_id)
        url = this.codeblock.data("api-preview").replace("tmpl_id", tmpl_id);
      else
        url = this.codeblock.data("api-preview-default").replace("type", this.type);

      this.base_url = url;

      this.submit();
    }
  },
  twentyc.rest.Form
);

/**
 * Special modal widget for handling new feature requests
 *
 * @class ModalFeatureRequest
 * @extends fullctl.application.Modal
 * @namespace fullctl.application
 * @constructor
 * @param {String} title
 * @param {String} message_type - the message type to use for example "support"
 */

fullctl.application.ModalFeatureRequest = $tc.extend(
  "ModalFeatureRequest",
  {
    ModalFeatureRequest: function (title, message_type) {
      var modal = this;

      // init form

      var form = this.form = new twentyc.rest.Form(
        fullctl.template("form_feature_request")
      );

      // close the model if the form is submitted successfully

      $(this.form).on("api-write:success", (ev, e, payload, response) => {
        modal.hide();
      });

      // append the message type to the payload
      // convert the messsage itself to dict containing `content`

      $(this.form).on("payload:after", (ev, payload) => {
        payload.type = message_type;
        payload.message = { content: payload.message };
      });

      // construct modal

      this.Modal("save", (!title ? "Feature Request" : title), form.element);

      // wire form to modal's submit button

      form.wire_submit(this.$e.button_submit);
    }
  },
  fullctl.application.Modal
);

fullctl.feature_request = document.addEventListener("DOMContentLoaded", () => {
  const feature_request_button = $('[data-element="feature_request_btn"]');

  feature_request_button.on('click', function() {
    let message_type = $(this).data("message-type");
    new fullctl.application.ModalFeatureRequest($(this).attr("title"), message_type);
  })
});

fullctl.help_box = document.addEventListener("DOMContentLoaded", () => {
  const help_button = document.querySelector(".help-btn");
  const box = document.querySelector(".help-box");

  help_button.addEventListener('click', () => {
    box.classList.toggle("js-hide");
    box.style.bottom = help_button.getBoundingClientRect().bottom - help_button.getBoundingClientRect().top + "px";

    document.addEventListener("click", (event) => {
      if (event.target.closest(".help-box")) return;
      if (event.target.closest(".help-btn")) return;
      box.classList.add("js-hide");
    })
  })
});

fullctl.theme_switching = document.addEventListener("DOMContentLoaded", () => {
  function toggle_theme() {
    if (detect_theme() === 'dark')
      set_theme('light');
    else
      set_theme('dark');
  }

  function set_theme(newTheme) {
    document.documentElement.setAttribute('data-theme', newTheme)
    localStorage.setItem('theme', newTheme)
  }

  function detect_theme() {
      var theme_override = localStorage.getItem('theme')
      if (theme_override == 'dark' || theme_override === 'light') {
        // Override the system theme
        return theme_override
      }
      // Use dark theme by default
      return 'dark';
  }

  document.documentElement.setAttribute('data-theme', detect_theme())

  $(".theme-switcher").click(() => {
      toggle_theme();
  });
});

$.fn.grainy_toggle = function(namespace, level) {
  if(grainy.check(namespace, level)) {
    this.show();
  } else {
    this.hide();
  }
};

})(jQuery, twentyc.cls);
