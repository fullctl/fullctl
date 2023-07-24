(function() {

    fullctl.graphs = {}

    /**
     * Format the y-axis values using pretty_speed formatter
     * @param {number} value - The value to be formatted
     * @return {string} - The formatted value
     */
    function format_y_axis(value) {
        return fullctl.formatters.pretty_speed_bits(value);
    }

    /**
     * Calculate bps_in_peak and bps_out_peak from the data
     * @param {Array} data - The data array containing bps_in and bps_out values
     * @return {Object} - An object containing bps_in_peak and bps_out_peak values
     */
    function calculate_peak(data) {
        let bps_in_peak = 0;
        let bps_out_peak = 0;

        data.forEach(function(d) {
            bps_in_peak = Math.max(bps_in_peak, d.bps_in_max);
            bps_out_peak = Math.max(bps_out_peak, d.bps_out_max);
        });

        return {bps_in_peak, bps_out_peak};
    }

    fullctl.graphs.init_controls = function(container, tool, callback_reload = (end_date,duration) => {}, dp_id_prefix = "custom_") {

        container.find('.graph-controls').show();
        // Refresh traffic graph when clicked
        container.find('[data-element=refresh_traffic_graph]').click(function() {
            let { end_date, duration } = fullctl.graphs.calculate_end_date_and_duration(container, dp_id_prefix);
            callback_reload(end_date,duration);
        });

        console.log("DATEPICKERS", container, container.find(".datepicker"))

        // Initialize the datepicker
        container.find('.datepicker').datepicker({
            dateFormat: 'yy-mm-dd',
            onSelect: function() {
                // When a date is selected, check if both dates are selected
                if (container.find(`#${dp_id_prefix}start_date`).val() && container.find(`#${dp_id_prefix}end_date`).val()) {
                    // If both dates are selected, calculate the end date and duration and show the graphs
                    let { end_date, duration } = fullctl.graphs.calculate_end_date_and_duration(container, dp_id_prefix);
                    callback_reload(end_date,duration);
                }
            }
        });

        // Change event for date range select
        container.find('#date_range_select').change(function() {
            let selected_value = $(this).val();

            if (selected_value === 'custom') {
                // Show the date input fields
                container.find(`#${dp_id_prefix}date_range`).show();
            } else {
                // Hide the date input fields
                container.find(`#${dp_id_prefix}date_range`).hide();

                let { end_date, duration } = fullctl.graphs.calculate_end_date_and_duration(container, dp_id_prefix);
                callback_reload(end_date,duration);
            }
        });

    }

    fullctl.graphs.calculate_end_date_and_duration = function(container, dp_id_prefix = "custom_") {
      let end_date = Math.floor(new Date().getTime() / 1000);
      let duration;
      let selected_value = container.find('#date_range_select').val();

      if (selected_value === 'custom') {
        let start_date = new Date(container.find(`#${dp_id_prefix}start_date`).val()).getTime() / 1000;
        end_date = new Date(container.find(`#${dp_id_prefix}end_date`).val()).getTime() / 1000;
        duration = end_date - start_date;
      } else if (selected_value === 'current_month') {
        let now = new Date();
        let start_of_month = new Date(now.getFullYear(), now.getMonth(), 1);
        duration = end_date - start_of_month.getTime() / 1000;
      } else if (selected_value === 'last_month') {
        let now = new Date();
        let start_of_last_month = new Date(now.getFullYear(), now.getMonth() - 1, 1);
        let end_of_last_month = new Date(now.getFullYear(), now.getMonth(), 0);
        duration = end_of_last_month.getTime() / 1000 - start_of_last_month.getTime() / 1000;
        end_date = end_of_last_month.getTime() / 1000;
      } else {
        duration = selected_value * 60 * 60;
      }

      return { end_date, duration };
    }

    fullctl.graphs.render_graph = function(data, selector="#graph", titleLabel = "") {

        if (data && data.length && data[0].bps_in == null) {
            data.unshift();
        }

        if(!data || !data.length) {
            return;
        }

        // Set up dimensions and margins for the graph
        const margin = {top: 20, right: 20, bottom: 50, left: 80}; // Increase left margin for traffic numbers and bottom margin for legend
        // Get the width of the parent container
        const parentWidth = d3.select(selector).node().getBoundingClientRect().width;
        const parentHeight = (d3.select(selector).node().getBoundingClientRect().height || 250);

        // Adjust the width of the graph to the width of the parent container
        const width = parentWidth - margin.left - margin.right;
        //const height = parentHeight - margin.top - margin.bottom;
        const height = parentHeight - margin.top - margin.bottom;

        // Set up x and y scales
        const x = d3.scaleTime().range([0, width]);
        const y = d3.scaleLinear().range([height, 0]);

        // Calculate the number of ticks for the x and y axes based on the width of the graph
        const numXTicks = Math.max(Math.floor(width / 100), 2); // At least 2 ticks

        // Set up line generators for bps_in and bps_out
        const line_in = d3.line()
            .defined(d => d.bps_in !== null) // Ignore data points with null bps_in values
            .x(function(d) { return x(d.timestamp * 1000); }) // Multiply by 1000 to convert unix timestamp to JavaScript timestamp
            .y(function(d) { return y(d.bps_in); });

        const line_out = d3.line()
            .defined(d => d.bps_out !== null) // Ignore data points with null bps_out values
            .x(function(d) { return x(d.timestamp * 1000); }) // Multiply by 1000 to convert unix timestamp to JavaScript timestamp
            .y(function(d) { return y(d.bps_out); });

        // Calculate bps_in_peak and bps_out_low
        const {bps_in_peak, bps_out_peak} = calculate_peak(data);

        // Calculate the maximum data value
        const maxDataValue = d3.max(data, function(d) { return Math.max(d.bps_in, d.bps_out); });

        // Check if the peak values are within 300% of the maximum data value
        const adjustedBpsInPeak = bps_in_peak <= maxDataValue * 3 ? bps_in_peak : maxDataValue;
        const adjustedBpsOutPeak = bps_out_peak <= maxDataValue * 3 ? bps_out_peak : maxDataValue;


        // Calculate the range of the y-axis values
        const yAxisRange = d3.max([maxDataValue, adjustedBpsInPeak, adjustedBpsOutPeak]) * 1.1;

        // Calculate the minimum increment between ticks based on the range of the y-axis values
        let minTickIncrement;
        if (yAxisRange >= 1000000000000) {
            minTickIncrement = 1000000000000; // 1T
        } else if (yAxisRange >= 1000000000) {
            minTickIncrement = 1000000000; // 1G
        } else if (yAxisRange >= 1000000) {
            minTickIncrement = 1000000; // 1M
        } else if (yAxisRange >= 1000) {
            minTickIncrement = 1000; // 1K
        } else {
            minTickIncrement = 1;
        }
        const numYTicks = Math.min(Math.floor(yAxisRange / minTickIncrement), 4);

        // Set up SVG container for the graph
        const svg = d3.select(selector).append("svg")
            .attr("width", width + margin.left + margin.right)
            .attr("height", height + margin.top + margin.bottom)
            .append("g")
            .attr("transform", "translate(" + margin.left + "," + margin.top + ")");

        // Set up domains for x and y scales
        const extent = d3.extent(data, function(d) { return d.timestamp * 1000; }); // Multiply by 1000 to convert unix timestamp to JavaScript timestamp
        x.domain(extent);
        y.domain([0, d3.max([maxDataValue, adjustedBpsInPeak, adjustedBpsOutPeak]) * 1.1]); // Add 10% padding to the maximum value

        // Calculate the difference in hours between the maximum and minimum dates
        const diffHours = (extent[1] - extent[0]) / 1000 / 60 / 60;
        const diffDays = diffHours / 24;

        // Define date formats for different ranges
        const hourFormat = d3.timeFormat("%H:%M");
        const dayFormat = d3.timeFormat("%b %d");
        const weekFormat = d3.timeFormat("%b %d");
        const monthFormat = d3.timeFormat("%b %d");
        const quarterFormat = d3.timeFormat("%b '%y");
        const yearFormat = d3.timeFormat("%Y");

        // Choose the date format based on the range
        let dateFormat;
        if (diffHours <= 1) {
            dateFormat = hourFormat;
        } else if (diffHours <= 24) {
            dateFormat = hourFormat;
        } else if (diffDays <= 7) {
            dateFormat = dayFormat;
        } else if (diffDays <= 30) {
            dateFormat = weekFormat;
        } else if (diffDays <= 90) {
            dateFormat = monthFormat;
        } else if (diffDays <= 365) {
            dateFormat = quarterFormat;
        } else {
            dateFormat = yearFormat;
        }

        // Add x-axis to the graph
        svg.append("g")
            .attr("transform", "translate(0," + height + ")")
            .call(d3.axisBottom(x)
                .ticks(numXTicks)
                .tickFormat(dateFormat)); // Set the number of ticks on the x-axis and format the date

        // Add y-axis to the graph
        svg.append("g")
            .call(d3.axisLeft(y).tickFormat(format_y_axis).ticks(numYTicks)); // Format y-axis using pretty_speed formatter

        // Add area for bps_in
        const area_in = d3.area()
            .x(function(d) { return x(d.timestamp * 1000); }) // Multiply by 1000 to convert unix timestamp to JavaScript timestamp
            .y0(height)
            .y1(function(d) { return y(d.bps_in); });

        // Update the area_in definition to fill all the way to the bottom of the graph
        const area_in_updated = d3.area()
            .x(function(d) { return x(d.timestamp * 1000); }) // Multiply by 1000 to convert unix timestamp to JavaScript timestamp
            .y0(height)
            .y1(function(d) { return y(Math.max(d.bps_in, 0)); });

        // Add lines for bps_in and bps_out
        svg.append("path")
            .datum(data)
            .attr("fill", "none")
            .attr("stroke", "#d1ff27")
            .attr("stroke-width", 1.5)
            .attr("d", line_in);

        // Move the area_in plot to the bottom, so it doesn't cover the bps_out plot
        svg.append("path")
            .datum(data)
            .attr("fill", "#d1ff27")
            .attr("d", area_in_updated);

        // Add the bps_out path after the bps_in path to ensure it is rendered above the bps_in plot
        svg.append("path")
            .datum(data)
            .attr("fill", "none")
            .attr("stroke", "#0d6efd")
            .attr("stroke-width", 1.5)
            .attr("d", line_out);


        // Add horizontal lines for bps_in_peak and bps_out_peak
        svg.append("line")
            .attr("x1", 0)
            .attr("x2", width)
            .attr("y1", y(bps_in_peak))
            .attr("y2", y(bps_in_peak))
            .attr("stroke", "#20c997")
            .attr("stroke-width", 1);

        svg.append("line")
            .attr("x1", 0)
            .attr("x2", width)
            .attr("y1", y(bps_out_peak))
            .attr("y2", y(bps_out_peak))
            .attr("stroke", "#6f42c1")
            .attr("stroke-width", 1);


        // Add legend
        const legend = svg.append("g")
            .attr("font-family", "sans-serif")
            .style("font-size", "11px")
            .attr("text-anchor", "start") // Change text-anchor to "start" for left alignment
            .attr("transform", "translate(0," + (height + margin.bottom - 20) + ")") // Move legend to the bottom
            .selectAll("g")
            .data([
                {key: "bps_in", label: "Bps IN"},
                {key: "bps_out", label: "Bps OUT"},
                {key: "bps_in_peak", label: "IN Peak: " + format_y_axis(bps_in_peak)},
                {key: "bps_out_peak", label: "OUT Peak: " + format_y_axis(bps_out_peak)}
            ])
            .enter().append("g")
            .attr("transform", function(d, i) { return "translate(" + (i * 120) + ",0)"; }); // Make legend horizontal


        legend.append("rect")
            .attr("x", 0) // Change x position to 0 for left alignment
            .attr("width", 15)
            .attr("height", 15)
            .attr("fill", function(d) {
                switch (d.key) {
                    case "bps_in":
                        return "#d1ff27";
                    case "bps_out":
                        return "#0d6efd";
                    case "bps_in_peak":
                        return "#20c997";
                    case "bps_out_peak":
                        return "#6f42c1";
                }
            });

        legend.append("text")
            .attr("x", 24) // Change x position to 24 for left alignment
            .attr("y", 9.5)
            .attr("dy", "0.32em")
            .attr("fill", "#fff") // Set legend font color to #fff
            .text(function(d) { return d.label; });;

        // Add logo
        const logoPath = document.querySelector("img.app-logo").getAttribute("src");
        const logo = svg.append("image")
            .attr("xlink:href", logoPath)
            .attr("x", width) // Temporarily set x position to the width of the graph
            .attr("y", -((height * 0.15) * 0.5))
            .attr("height", height * 0.15); // Adjust height of the logo

        // Get the width of the logo after it has been appended to the SVG
        const logoWidth = logo.node().getBBox().width;

        // Update the x position of the logo to sit snug against the right border of the graph
        logo.attr("x", width - logoWidth - 10);

        // Add title label
        if (titleLabel) {
            svg.append("text")
                .attr("x", width / 2) // Center the label
                .attr("y", 0) // Move the label down to avoid being cut off
                .attr("text-anchor", "middle") // Center the text
                .attr("font-family", "sans-serif")
                .attr("font-size", 16)
                .attr("fill", "#fff") // Set the font color to white
                .text(titleLabel);
        }

    }

    fullctl.graphs.render_graph_from_file = function(path, selector="#graph", titleLabel = "") {
        return d3.json(path).then(function(data) {
            $(selector).empty();
            console.log($(selector))
            fullctl.graphs.render_graph(data.data, selector=selector, titleLabel);
        });
    }
})();