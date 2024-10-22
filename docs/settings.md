## Settings

- `MEMBER_CASE_NUMBERS_ENABLED` (default: `False`): Enable case numbers for members. When turned on a case number field will be added to member forms that will be required to be entered. It will be stored in a `case_number` list inside the member's `meta` field.
- `PORT_SIZES` (default, `[1,10,100]`): The list of port sizes that can be selected when creating a new member. Set by providing a comma separated list of integers.
- `DEFAULT_PORT_SIZE` (default: `1`): The default port size that will be selected when creating a new member.
- `PORT_LIMIT_MAX` (default: `8`): The maximum number of ports that a member can have.
- `MAC_LIMIT_MAX` (default: `9`): The maximum number of MAC addresses a member can limit to.