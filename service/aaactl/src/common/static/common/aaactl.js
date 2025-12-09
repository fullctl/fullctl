(function() {

window.aaactl = {}

aaactl.api_client = new twentyc.rest.Client("/api/account")

aaactl.Header = twentyc.cls.define(
  "Header",
  {
    Header : function(org_branding={}) {
      this.elements = {}
      this.elements.app_switcher = $('[data-element="app_switcher"]');

      const others = this.elements.app_switcher.find('.others')
      const selected = this.elements.app_switcher.find('.selected')
      selected.click(() => {
        others.toggle();
        selected.toggleClass('app_bg muted');
      });
      $(document.body).click(function(e) {
        if (
          !( $(e.target).is(selected) || $(e.target).parent().hasClass('selected') )
        ) {
          others.hide();
          selected.removeClass('app_bg muted');
        }
      });

      this.app_switcher = new twentyc.rest.List(this.elements.app_switcher);

      this.app_switcher.formatters.row = (row, data) => {
        // hide if service is aaactl (current service)
        if (data.slug == "aaactl") {
          row.hide();
          return;
        }

        const redirect_url = data.service_url.replace("{org.slug}", account.org.slug)
        const img =  row.find("img.app-logo")

        row.attr("href", redirect_url);

        if (org_branding.show_logo === "true") {
          if(!data.logo) {
            img.attr("src", img.data("logo-url").replace("svc_slug", data.slug));
          } else {
            img.attr("src", data.logo);
          }
        } else {
          const span = $('<span class="name"></span>').text(data.name);
          img.replaceWith(span);
        }
      };

      // order app switcher elements
      $(this.app_switcher).on("load:after", () => {
        const service_list_order = ["ixctl", "peerctl", "devicectl", "prefixctl", "pdbctl", "aclctl", "aaactl"];
        const service_list = {};
        this.app_switcher.list_body.find(".list-item").each(function() {
          service_list[$(this).data("apiobject").slug] = $(this);
        })

        service_list_order.reverse().forEach((value, index) => {
          this.app_switcher.list_body.prepend(service_list[value]);
        });
      });

      this.app_switcher.load();
    },
  }
);

})(jQuery, twentyc.cls);