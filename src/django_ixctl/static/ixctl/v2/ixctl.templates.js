// This contains logic for the templates tab pane
// Templates available are:
//     - Email Templates

(function ($, $tc, $ctl) {
    // The Email template logic which includes
    //     - Loading the templates list
    //     - Loading the template form on change of the template type
    //     - Loading the template form on editting a template
    //     - Loading of template preview
    $ctl.application.Ixctl.EmailTemplates = $tc.extend(
        "EmailTemplates",
        {
            EmailTemplates: function () {
                this.tag = "email_template";
                this.Tool("email_templates");
                this.preview_timeout = new twentyc.util.SmartTimeout(() => { }, 100);
            },

            load_template_list: function() {
                const list = this.widget("list", ($e) => {
                    return new twentyc.rest.List(
                        this.template("template_list", $e.list_container)
                    );
                });
                list.format_request_url = this.format_request_url;
                list.load();
                return list;
            },

            load_form_template: function() {
                const form = this.widget("form", ($e) => {
                    return new twentyc.rest.Form(
                        this.template("form_template", $e.editor)
                    );
                });
                form.format_request_url = this.format_request_url;
                return form;
            },

            load_select_type_dropdown: function(form) {
                const select_type = this.widget("select_type", ($e) => {
                    return new $ctl.application.Ixctl.EmailTemplateTypeSelect(form.element.find('#type'));
                });
                select_type.format_request_url = this.format_request_url;
                this.handle_select_type_dropdown_change(select_type, form);
                return select_type;
            },

            handle_select_type_dropdown_change: function (select_type, form) {
                $(select_type.element).on("change", () => {
                    let val = select_type.element.val();

                    if (!val) {
                        return;
                    }

                    this.exit_edit_mode();
                    let url = select_type.element.data("api-default-template");
                    url = this.format_request_url(url).replace("/default/", `/${val}/`);

                    $.ajax({
                        method: 'get',
                        url: url
                    }).done(({ data }) => {
                        this.reset_form();
                        const template = data[0]
                        form.fill(template);
                        this.preview();

                        if (template.id != 0) {
                            this.enter_edit_mode(template);
                        }
                    });
                });
            },

            enter_edit_mode: function(template) {
                this.$e.editor.removeClass("create");
                this.$w.form.form_action = template.id;
                this.$w.form.method = "put";
                this.$e.editor_title.text("Edit template");
                this.edit_mode = true;
                this.$w.form.element.find(":input:not(#preview)").on("input", (e) => {
                    // might be out of edit mode when the listener fires
                    if (this.edit_mode) {
                        this.active_changes = true;
                    }
                });
            },

            exit_edit_mode: function() {
                this.edit_mode = false;
                this.$e.editor.addClass("create");
                this.$w.form.form_action = "";
                this.$w.form.method = "post";
                this.$w.form.reset();
                this.$e.editor_title.text("Create new template");
                this.$w.form.element.find('#preview, #body, #name').val("");
            },

            init: function () {
                this.edit_mode = false;
                this.active_changes = false;

                const list = this.load_template_list();
                const form = this.load_form_template();
                const select_type = this.load_select_type_dropdown(form);

                this.preview_client = new twentyc.rest.Client(
                    this.format_request_url(form.element.find("#preview").data("api-preview"))
                );


                list.local_actions.edit_template = (template) => {
                    form.fill(template);
                    this.preview(template.id);
                    this.enter_edit_mode(template);
                };

                this.$e.menu.find(`[data-element="button_new_${this.tag}"]`).click(() => {
                    if (this.edit_mode && this.active_changes &&
                        !confirm("You have unsaved edits, are you sure you want to discard them?")) {
                        return;
                    }
                    this.reset_form();
                    form.element.find(":input").first().focus();
                });

                form.element.find('a.btn.btn-secondary').click(() => {
                    this.reset_form()
                });

                $(form).on("api-write:success", () => {
                    this.active_changes = false;
                    if (!this.edit_mode) {
                        this.reset_form();
                    }
                    this.$w.list.load();
                });

                $(form).on("api-write:before", (form, _, data) => {
                    data["ix"] = fullctl.ixctl.ix_object().id;
                });

                form.element.find("#body").on("input", () => {
                    this.preview();
                });

            },

            format_request_url: function (url) {
                return url.replace("ix_tag", fullctl.ixctl.ix_object().slug);
            },

            sync: function () {
                this.$w.list.load();
            },

            reset_form: function () {
                this.$e.editor.addClass("create");
                this.$w.form.form_action = "";
                this.$w.form.method = "post";
                this.$w.form.reset();
                this.$e.editor_title.text("Create new template");
                this.$w.form.element.find('#preview, #body, #name').val("");
                this.edit_mode = false;
            },

            preview: function (id = null) {
                const type = this.$w.select_type.element.val();
                const preview_textarea = this.$w.form.element.find('#preview');
                const loading_shim = this.$w.form.element.find('.loading-shim');

                preview_textarea.prop("disabled", true).val("");
                loading_shim.show();
                const data = this.$w.form.payload();

                if (id) {
                    this.preview_client.base_url = this.preview_client.base_url.replace("/0/", `/${id}/`);
                }

                this.preview_timeout.set(() => {
                    this.preview_client.post(null, {
                        type: type,
                        body: data.body,
                        ix: fullctl.ixctl.ix_object().id
                    }).then((response) => {
                        preview_textarea
                            .val(response.first().body);
                    }).finally(() => {
                        loading_shim.hide();
                    });
                }, 500);
            }
        },
        $ctl.application.Tool
    );

    // The Email Template Type dropdown
    // Initializes the template type select dropdown
    $ctl.application.Ixctl.EmailTemplateTypeSelect = $tc.extend(
        "EmailTemplateTypeSelect",
        {
            EmailTemplateTypeSelect: function (jq) {
                this.Select(jq);
            }
        },
        twentyc.rest.Select
    );

    $($ctl).on("init_tools", (e, app) => {

        app.tool("email_templates", () => {
            return new $ctl.application.Ixctl.EmailTemplates();
        });

        app.$t.email_templates.activate();
    });

})(jQuery, twentyc.cls, fullctl);
