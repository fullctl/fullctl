class FullctlException(Exception):
    pass


class TemplateRenderError(FullctlException, ValueError):
    """Error that gets raised when template render fails"""

    def __init__(self, tmpl_exc):
        msg = f"Could not render template: {tmpl_exc}"
        super().__init__(msg)
