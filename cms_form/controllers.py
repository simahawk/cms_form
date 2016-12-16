# -*- coding: utf-8 -*-

from openerp import http
from openerp.http import request
import werkzeug
# from werkzeug.exceptions import NotFound


class FormControllerMixin(object):

    # default template
    template = ''

    def get_template(self, form, **kw):
        """Retrieve rendering template."""
        template = self.template

        if getattr(form, 'form_wrapper_template', None):
            template = form.form_wrapper_template

        if not template:
            raise NotImplementedError("You must provide a template!")
        return template

    def get_render_values(self, main_object, **kw):
        """Retrieve rendering values.

        You can override this to inject more values.
        """
        parent = None
        if getattr(main_object, 'parent_id', None):
            # get the parent if any
            parent = main_object.parent_id

        kw.update({
            'main_object': main_object,
            'parent': parent,
            'controller': self,
        })
        return kw

    def _can_create(self, main_object):
        """Override this to protect the view or the item by raising errors."""
        return main_object.check_access_rights('create', raise_exception=False)

    def _can_edit(self, main_object):
        return main_object.check_access_rights('write', raise_exception=False)

    def get_form(self, model, main_object=None, **kw):
        """Retrieve form for given model or object and initialize it."""
        form = request.env['cms.form.' + model].new()
        form.form_init(request, main_object=main_object)
        return form

    def make_response(self, model, model_id=None, **kw):
        main_object = None
        if model_id:
            main_object = request.env[model].browse(model_id)
        form = self.get_form(model, main_object=main_object)
        form.form_process()
        if form.form_redirect:
            # anything went fine
            return werkzeug.utils.redirect(form.form_next_url())
        values = self.get_render_values(main_object, **kw)
        values['form'] = form
        return request.website.render(
            self.get_template(main_object, **kw),
            values,
        )


class CMSFormController(http.Controller, FormControllerMixin):
    """CMS form controller."""

    template = 'cms_form.form_wrapper'

    @http.route([
        '/cms/<string:model>/create',
        '/cms/<string:model>/<int:model_id>/edit',
    ], type='http', auth='user', website=True)
    def cms_form(self, model, model_id=None, **kw):
        """Handle a `form` route.
        """
        return self.make_response(model, model_id=model_id, **kw)
