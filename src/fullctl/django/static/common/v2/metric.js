(function($) {
  $.fn.show_metric_list = function(url, row, data) {
    // Metrics list for port tables in summary pages.

    // console.log("metric:row:", row);
    // console.log("metric:data:", data);

    row.find('[data-action="show_port_metrics"]').on("click", () => {
      var member = row.data("apiobject");

      // ixCtl and peerCtl are not reciving the same data structure
      // So we have to check both
      if(!member.port && !member.port_id) {
        // If there is no port, we have nothing to do here
        // console.log("metric: no port found");
        return null;
      }
      let port_id = member.port ?? member.port_id;
      let port_name = member.port_name ?? data.port_display_name;
      // console.log("metric: port found", port_id);

      if($(row).find('[data-field="port_metric"]').children().length > 1){
        // We are displaying data, so user want to hide it
        $(row).find('[data-field="port_metric"]').empty().append(`<span class="btn" data-field="port">${port_name}</span> `);
      } else {
        // Only port name is displayed, so user wants to see details,
        // retrieve dome data from backend and display it

        $.ajax({
          url: url.replace(/0/g, port_id)
        }).done(function ( ports ) {
          $(row).find('[data-field="port_metric"]').empty().append(`<span class="btn" data-field="port">${port_name}</span> `);
          $.each(ports.data, function ( index, port ) {
            $(row).find('[data-field="port_metric"]').append(`<span class="btn">${port_name}.${port.device_name}.${port.name}</span> `);
            $.each(port.metric, function ( index, metric ) {
              // TODO <sergio>: make thresholds configurable
              if ( metric > 0 && metric < 10000 ) {
                $(row).find('[data-field="port_metric"]').append(`<span class="flex-container red"><span class="left">${index}&nbsp&nbsp</span><span class="right">${metric}</span></span>`);
              } else if ( metric > 10000 && metric < 100000 ) {
                $(row).find('[data-field="port_metric"]').append(`<span class="flex-container amber"><span class="left">${index}&nbsp&nbsp</span><span class="right">${metric}</span></span>`);
              } else if ( metric > 100000 ) {
                $(row).find('[data-field="port_metric"]').append(`<span class="flex-container green"><span class="left">${index}&nbsp&nbsp</span><span class="right">${metric}</span></span>`);
              } else {
                $(row).find('[data-field="port_metric"]').append(`<span class="flex-container"><span class="left">${index}&nbsp&nbsp</span><span class="right">${metric}</span></span>`);
              }
            });
          });
        });
      };
      return true;
    });
  };

  $.fn.show_metric_table = function(url, member) {
    // Metrics table for port details pages.

    // console.log("metric:member:", member);

    // ixCtl and peerCtl are not reciving the same data structure
    // So we have to check both
    if((member.port == null || member.port.virtual_port == null)
      && !member.port_id) {
      // $('#metric_table').DataTable().clear();
      // $('#metric_table').DataTable().destroy();
      // $('#metric_table').empty();
      // console.log("metric: no port found");
      return true;
    }

    let port_id = member.port_id ?? member.port.virtual_port;
    // console.log("metric: port found", port_id);

    let mt = $('#metric_table').DataTable({
      // https://datatables.net/manual/options
      destroy: true,
      paging: false,
      searching: false,
      info: false,
      autoWidth:false,
      processing: true,
      responsive: true,
      language: {"emptyTable": "No port assigned"},

      ajax: {
        url: url.replace(/0/g, port_id)
      },

      columns: [
        { data: "device" },
        { data: "resource" },
        { data: "value" }
      ],

      "rowCallback": function( row, data, dataIndex ) {
        if ( data.value > 0 && data.value < 10000 ) {
          $(row).addClass('red');
        } else if ( data.value > 10000 && data.value < 100000 ) {
          $(row).addClass('amber');
        } else if ( data.value > 100000 ) {
          $(row).addClass('green');
        } else {
          // default
        }
      }
    });
    return true;
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
