copy `config.example.yaml` contents to `Ctl/config.yaml` of your target repository

copy `tmplvars.example.yaml` to `Ctl/tmplvars.yaml` in your target repository and added as necessary.

Then in your target repostiroy

```
pip install ctl tmpl jinja2 
ctl sync_tmpl
```
