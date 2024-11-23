(function($) {
  $.fn.show_metric_list = function(metrics_url, row, member) {
    if (!member.port && !member.port_id && !member.virtual_port) return;
    const port_id = member.port ?? member.port_id ?? member.virtual_port;

    $.ajax({
      url: metrics_url.replace("/0/", `/${port_id}/`)
    }).done(({data = []}) => {
      const light_level_stat = row.find('[data-element="light_level_stat"]');

      $.each(data, (_, {status, device_name, metric = {}}) => {
        const result = {};
        $.each(metric, (metric_index, value) => {
          if (metric_index.includes('optics')) {
            const segments = metric_index.split('.');
            const port = segments[3];
            const metric_data = segments.slice(-2).join(".");
            if (!result[port]) {
              result[port] = {};
            }
            result[port][metric_data] = value;
          }
        });

        $.each(result, (port, metric) => {
          // Tooltip
          const tootlip_div = $('<div>')
          .attr("data-bs-toggle", "tooltip")
          .attr("data-bs-placement", "top")
          .attr("data-bs-html", true);

          let tooltip_data = `${device_name} ${port}<br>`;
          const allowed_metrics = {
            "input_power.instant": "TX Power",
            "output_power.instant": "RX Power",
            "laser_bias_current.instant": "Bias Current",
          };
          const allowed_metrics_keys = Object.keys(allowed_metrics);
          $.each(metric, (key, data) => {
            if (allowed_metrics_keys.indexOf(key) !== -1) {
              tooltip_data = `${tooltip_data}${allowed_metrics[key]}: ${data}<br>`;
            }
          });
          tootlip_div.attr("title", tooltip_data);

          // Tooltip Container
          const node = $('<div class="d-flex align-items-center">');
          node.append($('<span class="dotted-underline">').text(`${device_name} ${port}`));
          if (status == "ok") {
            node.append($('<span class="icon icon-triangle-fill-up">'));
            node.addClass("up");
          } else {
            node.append($('<span class="icon icon-triangle-fill-down">'));
            node.addClass("down");
          }
          tootlip_div.html(node);
          new bootstrap.Tooltip(tootlip_div);
          light_level_stat.append(tootlip_div);
        });
      });
    });
  };

  $.fn.show_metric_table = function(url, member) {
    if ((member.port == null || member.port.virtual_port == null) && !member.port_id) return;
    const port_id = member.port_id ?? member.port.virtual_port;

    $('#metric_table').DataTable({
      // https://datatables.net/manual/options
      destroy: true,
      paging: false,
      searching: false,
      info: false,
      autoWidth:false,
      processing: true,
      responsive: true,
      language: {"emptyTable": "No port assigned"},
      scrollCollapse: true,
      scrollY: '200px',

      ajax: {
        url: url.replace("/0/", `/${port_id}/`)
      },

      columns: [
        { data: "device" },
        { data: "interface" },
        { data: "subject" },
        { data: "value" }
      ],
    });
  };

  $.fn.reset_metric_table = function(url, member) {
    // Clean metric table.

    $('#metric_table').DataTable().clear();
    $('#metric_table').DataTable().destroy();
    $('#metric_table').DataTable({
      destroy: true,
      paging: false,
      searching: false,
      info: false,
      autoWidth:false,
      processing: true,
      responsive: true,
      language: {"emptyTable": "No port assigned"}
    });

    return true;
  };

})(jQuery);
