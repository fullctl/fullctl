# White-labeling aaactl

All white-labeling for aaactl is done through template and static file overrides managed in a dedicated django application.

This django application should be started with the `django-admin startapp` command and can either live in the `src` directory of your aaactl installation, or be installed as a python module in your virtual environment.

## Create application 

```
cd src
django-admin startapp whitelabel
```

Note that the name `whitelabel` is not of consequence and can be substituted by something else if it makes more sense. If you do name it differently you will need to adjust it in the instructions below as well though.

## Add to INSTALLED_APPS for your environment

```
vim aaactl/settings/dev_append.py
```

```py
app_index = INSTALLED_APPS.index("account")

# whitelabel needs to be inserted before `account`
INSTALLED_APPS.insert(app_index, "whitelabel")
```

## Create directories

```
cd whitelabel
mkdir -p templates/account
mkdir -p static/account 
```

**note** - aaactl needs to be restarted in order to recognize these directories.

### Header override - replacing the logo

```
cp logo.png static/account/logo.png
vim templates/account/header.html
```

```html
{% extends "account/header.html" %}
{% load static i18n %}
{% block header %}
<div class="row">
  <div class="col-xs-12">
      <a href="/"><img src="{% static "whitelabel/logo.png" %}" class="logo"></a>
  </div>
</div>
{% endblock %}
```

#### Add secondary logo to app_switcher header
```
cp logo.png static/account/logo.png
vim templates/account/header-switcher.html
```

```html
{% extends "account/header-switcher.html" %}
{% load static i18n %}
{% block secondary_logo %}
  <div class="col-auto ms-auto">
      <a href="/"><img src="{% static "whitelabel/logo.png" %}" class="app-logo"></a>
  </div>
{% endblock %}
```

### Footer override - copyright / contact / legal / developed-by

```
vim templates/account/footer.html
```

```html
{% extends "account/footer.html" %}
{% load static i18n %}
{% block developer %}{% endblock %}
{% block contactus %}<a href="mailto:contact@whitelabel">Contact us</a>{% endblock %}
{% block copyright %}2020-{% now "Y" %} Whitelabel, LLC{% endblock %}  
{% block legal %}<a href="legal.pdf">Legal</a>{% endblock %}
```


