# -*- coding: utf-8 -*-
# Copyright 2016 Simone Orsi
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openerp import models
from openerp import fields
# from openerp import _

import json
# import werkzeug.urls
import inspect


IGNORED_FORM_FIELDS = (
    '__last_update',
    'display_name',
    'id',
)


def m2o_to_form(item, value, **req_values):
    # important: return False if no value
    # otherwise you will compare an empty recordset with an id
    # in a select input in form widget template.
    if isinstance(value, basestring) and value.isdigit():
        # number as string
        return int(value)
    elif isinstance(value, models.BaseModel):
        return value and value.id or None
    return None


def x2many_to_form(item, value, display_field='display_name', **req_values):
    value = [{'id': x.id, 'name': x[display_field]} for x in value]
    value = json.dumps(value)
    return value


def form_to_integer(value, **req_values):
    try:
        return int(value)
    except ValueError:
        return 0


def form_to_float(value, **req_values):
    try:
        return float(value)
    except ValueError:
        return 0.0


def form_to_x2many(value, **req_values):
    _value = False
    if value:
        ids = [int(rec_id) for rec_id in value.split(',')]
        _value = [(6, False, ids)]
    return _value


DEFAULT_LOADERS = {
    'many2one': m2o_to_form,
    'one2many': x2many_to_form,
    'many2many': x2many_to_form,
}
DEFAULT_EXTRACTORS = {
    'integer': form_to_integer,
    'float': form_to_float,
    'many2one': form_to_integer,
    'one2many': form_to_x2many,
    'many2many': form_to_x2many,
}


class CMSForm(models.AbstractModel):
    """Base abstract CMS form."""
    _name = 'cms.form'
    _description = 'CMS Form'  # TODO

    # model tied to this form
    _form_model = ''
    # model's fields to load
    _form_model_fields = []
    _form_required_fields = ()
    _form_fields_attributes = [
        'type', 'string', 'domain', 'required', 'readonly',
    ]
    _form_fields_whitelist = ()
    _form_fields_blacklist = ()
    _form_extractors = DEFAULT_EXTRACTORS
    _form_loaders = DEFAULT_LOADERS

    def form_init(self, request, **kw):
        """Initalize a form.

        @param request: an odoo-wrapped werkeug request
        @parm kw: pass any override for `_form_` attributes
            ie: `fields_attributes` -> `_form_fields_attributes`
        """
        self.o_request = request  # odoo wrapped request
        self.request = request.httprequest  # werkzeug request, the "real" one
        # override `_form_` parameters
        for k, v in kw.iteritems():
            if not inspect.ismethod(getattr(self, '_form_' + k)):
                setattr(self, '_form_' + k, v)

    @property
    def form_model(self):
        return self.env[self._form_model]

    def form_fields(self):
        """Retrieve form fields ready to be used."""
        _all_fields = {}
        # load model fields
        _model_fields = self.form_model.fields_get(
            self._form_model_fields, attributes=self._form_fields_attributes)
        _form_fields = self.fields_get(attributes=self._form_fields_attributes)
        # remove unwanted fields
        for fname in IGNORED_FORM_FIELDS:
            _form_fields.pop(fname, None)
        _all_fields.update(_model_fields)
        # form fields override model fields
        _all_fields.update(_form_fields)
        # exclude blacklisted
        for fname in self._form_fields_blacklist:
            # make it fail if passing wrong field name
            _all_fields.pop(fname)
        # include whitelisted
        _all_whitelisted = {}
        for fname in self._form_fields_whitelist:
            _all_whitelisted[fname] = _all_fields[fname]
        _all_fields = _all_whitelisted or _all_fields
        # update fields attributes
        self._form_update_fields_attributes(_all_fields)
        return _all_fields

    def _form_update_fields_attributes(self, fields):
        """Manipulate fields attributes."""
        for fname in self._form_required_fields:
            # be defensive here since we can remove fields via blacklist
            if fname in fields:
                fields[fname]['required'] = True

    @property
    def form_file_fields(self):
        """File fields."""
        return {
            k: v for k, v in self.form_fields().iteritems()
            if v['type'] == 'binary'
        }

    def _form_get_request_values(self):
        return {k: v for k, v in self.request.form.iteritems()
                if k not in ('csrf_token', )}

    def form_load_defaults(self, main_object, request_values=None):
        """Load default values.

        Values lookup order:

        1. `main_object` fields' values (if an existing main_object is passed)
        2. request parameters (only parameters matching form fields names)
        """
        request_values = request_values or self._form_get_request_values()
        defaults = request_values.copy()
        form_fields = self.form_fields()
        for fname, field in form_fields.iteritems():
            value = None
            # we could have form-only fields (like `custom` in test form below)
            if main_object and fname in main_object:
                value = main_object[fname]
            # maybe a POST request with new values: override item value
            # TODO: load particular fields too (file, image, etc)
            value = request_values.get(fname, value)
            # 1nd lookup for a default type handler
            value_handler = self._form_loaders.get(field['type'], None)
            # 2nd lookup for a specific type handler
            value_handler = getattr(
                self, '_form_load_' + field['type'], value_handler)
            # 3rd lookup and override by named handler if any
            value_handler = getattr(
                self, '_form_load_' + fname, value_handler)
            if value_handler:
                value = value_handler(main_object, value, **request_values)
            defaults[fname] = value
        # add `has_*` flags for file fields
        # so in templates we really know if a file field is valued.
        for fname in self.form_file_fields.iterkeys():
            defaults['has_' + fname] = bool(main_object[fname])
        return defaults

    def form_extract_values(self, **request_values):
        """Extract values from request form."""
        request_values = request_values or self._form_get_request_values()
        values = {}
        for fname, field in self.form_fields().iteritems():
            value = request_values.get(fname)
            # 1nd lookup for a default type handler
            value_handler = self._form_extractors.get(field['type'], None)
            # 2nd lookup for a specific type handler
            value_handler = getattr(
                self, '_form_extract_' + field['type'], value_handler)
            # 3rd lookup and override by named handler if any
            value_handler = getattr(
                self, '_form_extract_' + fname, value_handler)
            if value_handler:
                value = value_handler(value, **request_values)
            values[fname] = value
        return values

    # def form_do_edit(self, reference=None, **post):
    #     countries = self.env['res.country'].sudo().search([])
    #     values = {
    #         'reference': reference,
    #         'errors': {},
    #         'error_messages': {},
    #         'countries': countries,
    #     }
    #     if self.request.method == 'GET':
    #         values.update(self.load_defaults(reference))
    #     elif self.request.method == 'POST':
    #         msg = False
    #         errors, errors_message = self.details_form_validate(post)
    #         if not errors:
    #             values = self.extract_values(post)
    #             if reference:
    #                 reference.write(values)
    #                 msg = _('Reference updated.')
    #             else:
    #                 reference = self.env['project.reference'].create(values)
    #                 # TODO: handle this better with some hook
    #                 # and with proper mgmt of partner profile
    #                 partner = request.env.user.partner_id
    #                 if partner.profile_state == 'step-2':
    #                     partner.profile_state = 'step-3'
    #                 msg = _('Reference created.')
    #             if msg and request.website:
    #                 request.website.add_status_message(msg)
    #             return werkzeug.utils.redirect(reference.website_url)
    #
    #         values.update({
    #             'errors': errors,
    #             'errors_message': errors_message,
    #         })
    #         values.update(self.load_defaults(reference), **post)
    #         if self.o_request.website:
    #             msg = _('Some errors occurred.')
    #             self.o_request.website.add_status_message(msg, mtype='danger')
    #     return self.o_request.website.render(
    #         "specific_project.reference_form", values)


class TestPartnerForm(models.AbstractModel):
    """A test model form."""

    _name = 'cms.form.test_partner'
    _inherit = 'cms.form'
    _form_model = 'res.partner'
    _form_model_fields = ('name', 'country_id')
    _form_required_fields = ('name', 'country_id')

    custom = fields.Char()

    def _form_load_custom(self, item, value, **req_values):
        return req_values.get('custom', 'oh yeah!')


class TestFieldsForm(models.AbstractModel):
    """A test model form."""

    _name = 'cms.form.test_fields'
    _inherit = 'cms.form'

    a_char = fields.Char()
    a_number = fields.Integer()
    a_float = fields.Float()
    # fake relation fields
    a_many2one = fields.Char()
    a_one2many = fields.Char()
    a_many2many = fields.Char()

    def form_fields(self):
        _fields = super(TestFieldsForm, self).form_fields()
        # fake fields' types
        _fields['a_many2one']['type'] = 'many2one'
        _fields['a_many2many']['type'] = 'many2many'
        _fields['a_one2many']['type'] = 'one2many'
        return _fields
