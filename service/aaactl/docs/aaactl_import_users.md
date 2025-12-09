# aaactl_import_users Command Usage Documentation

The `aaactl_import_users` command is a utility command that allows you to import users from a CSV file into the system. 

## Command Syntax

The command takes one argument, which is the path to the CSV file that contains the user data.

```sh
python manage.py aaactl_import_users <csv_file>
```

Where `<csv_file>` is the path to the CSV file.

## CSV File Format

The CSV file should contain the following fields:

- username
- email
- name
- asn
- org_name

Here is an example of the CSV file format:

```csv
username,email,name,asn,org_name
jdoe,jdoe@example.com,John Doe,12345,Example Organization
asmith,asmith@example.com,Alice Smith,67890,Another Organization
bclark,bclark@example.com,Bob Clark,11122,Third Organization
```

## Flags

The `--commit` flag needs to be passed for the command to actually run for real. If this flag is not passed, the command will run in pretend mode, showing what would happen without actually making any changes.

```sh
python manage.py aaactl_import_users <csv_file> --commit
```

## Notes

- If the user already exists in the system, the command will not create a new user but will update the existing user's organization and permissions.
- If the organization does not exist, the command will create a new organization.
- The command will also grant the user the necessary permissions for the specified ASN.