/**
 * Utilities and functions for django-admin aaactl billing views
 */

document.addEventListener('DOMContentLoaded', function() {
    // Get the table that contains the product and component_object_id fields
    var first_product_feld = document.querySelector('select[name$="-product"]');
    var table = first_product_feld.closest('table');
    

    // Attach an event listener to the table
    table.addEventListener('change', function(event) {
        // Check if the event target was a product field
        if (event.target.name.endsWith('-product')) {
            // Get the corresponding component_object_id field
            var row = event.target.closest('.form-row');
            var componentObjectIdField = row.querySelector('select[name$="-component_object_id"]');
            var org_select_field = document.querySelector('select[name="org"]');
            var org_id = org_select_field.options[org_select_field.selectedIndex].value;
            var xhr = new XMLHttpRequest();
            xhr.open('GET', '/admin/billing/subscription/component-entities/?product_id=' + event.target.value + `&org_id=${org_id}`, true);
            xhr.onload = function() {
                if (this.status >= 200 && this.status < 400) {
                    // Success!
                    var data = JSON.parse(this.response);
                    // Clear the component_object_id field
                    while (componentObjectIdField.firstChild) {
                        componentObjectIdField.removeChild(componentObjectIdField.firstChild);
                    }
                    // Add the new options to the component_object_id field
                    data.forEach(function(item) {
                        var option = document.createElement('option');
                        option.value = item.id;
                        option.text = item.name;
                        componentObjectIdField.appendChild(option);
                    });
                } else {
                    // We reached our target server, but it returned an error
                    console.error('Server returned an error');
                }
            };
            xhr.onerror = function() {
                // There was a connection error of some sort
                console.error('Connection error');
            };
            xhr.send();
        }
    });


    // Attach an event listener to the org field
    var orgField = document.querySelector('select[name="org"]');
    orgField.addEventListener('change', function(event) {
        // Get the payment_method field
        var paymentMethodField = document.querySelector('select[name="payment_method"]');
        var xhr = new XMLHttpRequest();
        xhr.open('GET', '/admin/billing/subscription/payment-methods/?org_id=' + event.target.value, true);
        xhr.onload = function() {
            if (this.status >= 200 && this.status < 400) {
                // Success!
                var data = JSON.parse(this.response);
                // Clear the payment_method field
                while (paymentMethodField.firstChild) {
                    paymentMethodField.removeChild(paymentMethodField.firstChild);
                }
                // Add the new options to the payment_method field
                data.forEach(function(item) {
                    var option = document.createElement('option');
                    option.value = item.id;
                    option.text = item.name;
                    paymentMethodField.appendChild(option);
                });
            } else {
                // We reached our target server, but it returned an error
                console.error('Server returned an error');
            }
        };
        xhr.onerror = function() {
            // There was a connection error of some sort
            console.error('Connection error');
        };
        xhr.send();
    });


});