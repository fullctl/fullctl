# Stripe 

Stripe is currently the only billing processort supported by aaactl

Set up an account create an API key at https://stripe.com

Set the `STRIPE_SECRET_KEY` and `STRIPE_PUBLIC_KEY` variables in your docker .env

# Live vs Test

**IMPORTANT** Whether or not the key is a live production key or a sandbox testing key
is something you specify when setting it up in stripe. Chaning the `BILLING_ENV` value does
not affect this.

For dev instances it is recommended to set the `BILLING_ENV` variable to 'test'
For production instances it the `BILLING_ENV` variable should be 'live' or 'production' (basically anything but 'test')

# Managing products

All products are managed through the admin interface localated at `/admin`

Navigate to the section titled *Billing*

# Setting up recurring billing with fixed fee

## 1) Setup a product group 

The product group is a container that allows us to group certain product when presenting them to the user (and on invoices)

For example all fullctl service subscription could go into a `Fullctl` product group.

All recurring products need a group, even if there is only one product.

Create a product group at `/admin/billing/productgroup/add/`

### a) Name

Descriptive name - the customer will see this (example: "Fullctl Services")

### b) Subscription Cycle Anchor

Allows you to anchor the billing day for subscriptions created with in this group. Meaning regardless of when the subscription was started it will always be billed (e.g. 1st of the month)

If you dont specify it then the day of when the subscription was created will be the anchor day.

## 2) Set up service application (optional)

In order to be able to tie a product to a specific service (ixctl, devictl, etc.,) we need set that up.

If your product is not tied to a service application, you can skip this step

Go to `/admin/applications/service/` and see if you service exists already, if it does you can skip this step.

Go to `/admin/applications/service/add/` and add an entry for your service application.

## 3) Create the product

To create a product go to `/admin/billing/product/add/`

### a) Name

The intenral product name, this is not exposed to the customer and should be something standardized to your liking

Examples:

- `ixctl.members`
- `prefixctl.monitored_prefixes`

### b) Component (optional)

If your product is tied to a service application (see 2) specify it here

### c) Description

Short descriptive name of the product / service

This *is* exposed to the customer

Examples:

- `Managed members`
- `Monitored prefixes`

### d) Group

If you created a product group in 1) specify it here

### e) Price

Price charge on initial setup / purchase. For recurring pricing this could specify a setup fee. For non-recurring pricing, this is the product price.

This is *NOT* the recurring cost.

### f) Product Price Modifiers

Allows you to setup available price reduction modifiers for the product. 

This does *NOT* activate the modifications, it simply makes them available to attach to individual subscriptions later on.

Click `Add another Product Price Modifier` to create.

### g) Recurring Product Settings

This is where you create the billing cycle cost for your product.

Click `Add another Recurring Product Settings`

#### 1) Type

Choose `Recurring: Fixed Price` 

#### 2) Price

Price in the context of recurring charges. For fixed recurring pricing this would be the price charged each cycle. For metered pricing this would be the usage price per metered unit.

#### 3) Unit

Label for a unit in the context of usage

This *is* exposed to the user on their billing lines

Examples

- `Member`
- `Prefix`

#### 4) Unit plural

Label for multiple units in the context of usage

This *is* exposed to the user on their billing lines

Examples

- `Members`
- `Prefix`

# Setting up a subscription

Currently it is only possible to setup subscription programmatically or through the django-admin interface.

Go to `/admin/billing/subscription/add/`

## Org

Organization to be billed

## Group

Product group

## Cycle interval

Billing cycle (monthly, yearly)

## Cycle Start

when does the cycle start ?

Normally you will want to click `today` and `now`

## Payment method 

Billing contact to use for charges.

**IMPORTANT BUG NOTICE**: this currently does not seem to filter for the selected organization but will display
all payment methods in the database, be careful when selecting.

## Subscription Products

Which products are billed with this subscription

Add the product you created earlier

# Run the `billing_cycles` command

This will start the billing cycle for the subscription you just set up as well as charge and turn over any billing cycles that have ended.

Charges always happen at the end of a cycle.

```sh
python manage.py billing_cycles
```

This will run in pretend mode, check the output and make sure everything is in order, then run it
in committal mode.

```sh
python manage.py billing_cycles --commit
```

**This should still be considered to need heavy testing so it is always recommended to run non-committal first.**


# Setting up recurring billing with metered fee

Same as above but choose `Recurring: Metered price` in the Recurring Product Settings

Instructions on how to set up usage metering will follow here soon (TODO)


