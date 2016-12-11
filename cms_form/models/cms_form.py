# -*- coding: utf-8 -*-
# Copyright 2016 Simone Orsi
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openerp import models
from openerp import fields
from openerp import _
from openerp.http import request

import json
import werkzeug.urls
import inspect


IGNORED_FORM_FIELDS = (
    '__last_update',
    'display_name',
    'id',
)


def m2o_to_form(item, value, **req_values):
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


def form_to_integer(item, value, **req_values):
    try:
        return int(value)
    except ValueError:
        return 0.0


def form_to_float(item, value, **req_values):
    try:
        return float(value)
    except ValueError:
        return 0.0

DEFAULT_LOADERS = {
    # important: return False if no value
    # otherwise you will compare an empty recordset with an id
    # in a select input in form widget template.
    'many2one': m2o_to_form,
    'one2many': x2many_to_form,
    'many2many': x2many_to_form,
}
DEFAULT_EXTRACTORS = {
    'integer': form_to_integer,
    'many2one': form_to_integer,
    'float': form_to_float,
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
        self.request = request.httprequest  # werkzeug request
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


class TestPartnerForm(models.AbstractModel):
    """A test model form."""

    _name = 'cms.form.partner_test'
    _inherit = 'cms.form'
    _form_model = 'res.partner'
    _form_model_fields = ('name', 'country_id')
    _form_required_fields = ('name', 'country_id')

    custom = fields.Char()

    def _form_load_custom(self, item, value, **req_values):
        return req_values.get('custom', 'oh yeah!')
