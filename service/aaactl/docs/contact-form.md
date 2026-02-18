# Snippet to use aaactl's contact form

This are very basic snippet on how to wire up the aaactl contact backend at a site that is not
service bridge enabled, but still wants to facilitate support contact message posting through aaactl's contact backend.

The requesting host needs to be white-listed through the `CONTACT_ALLOWED_ORIGINS` setting in aaactl.

```sh
expose CONTACT_ALLOWED_ORIGINS=https://example.com,https://otherexample.com
```

In order to post to the backend

- an `ajax` request should be dispatched to `{AAACTL_URL}/api/account/contact/` with a `POST` method
- the content type should be `application/json`
- the content should be a json string with
    - `name` field (username or personal name)
    - `email` field
    - `type` field (can be `general`, `feature-request`, `support` or `demo-request`) - will default to `general` if not specified
    - `message` field (a `dict` containing any additional info to post)

```json
{
    "email" : "john@example.com",
    "name": "John",
    "message": {
        // the `messsage` sub fields are all arbitrary, and you can construct
        // it however you want, to include any additional information in your form
        "content": "my message",
        "orgnaziation": "20C"
    },
}
```

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Simple Contact Form</title>
    <script src="https://code.jquery.com/jquery-3.6.0.min.js"></script>
    <script>
        $(document).ready(function() {
            $('form').on('submit', function(event) {
                event.preventDefault();

                const AAACTL_URL = "https://account.fullctl.io"
        
                const formData = new FormData(event.target);

                const data = {
                    name: formData.get('name'),
                    email: formData.get('email'),
                    message: { content: formData.get('message') },
                };

                const jsonString = JSON.stringify(data);

                $.ajax({
                    url: AAACTL_URL + '/api/account/contact/',
                    type: 'POST',
                    contentType: 'application/json',
                    data: jsonString,
                    success: function(response) {
                        console.log('Form submitted successfully!', response);
                    },
                    error: function(jqXHR, textStatus, errorThrown) {
                        console.error('Form submission failed:', textStatus, errorThrown);
                    }
                });
            });
        });
    </script>
</head>
<body>
    <form>
        <label for="name">Name:</label>
        <input type="text" id="name" name="name" required><br><br>

        <label for="email">Email Address:</label>
        <input type="email" id="email" name="email" required><br><br>

        <label for="message">Message:</label><br>
        <textarea id="message" name="message" rows="4" cols="50" required></textarea><br><br>

        <button type="submit">Submit</button>
    </form>
</body>
</html>
```
