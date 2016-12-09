# -*- coding: utf-8 -*-
# Copyright 2016 Simone Orsi
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openerp import models
from openerp import fields


IGNORED_FORM_FIELDS = (
    '__last_update',
    'display_name',
    'id',
)


class CMSForm(models.AbstractModel):
    """Base abstract CMS form."""
    _name = 'cms.form'
    _description = 'CMS Form'  # TODO

    # model tied to this form
    _form_model = ''
    # model's fields to load
    _form_model_fields = []
    _form_required_fields = ()
    # TODO
    form_control_fields = ()
    _fields_attributes = [
        'type', 'string', 'domain', 'required', 'readonly',
    ]

    @property
    def form_model(self):
        return self.env[self._form_model]

    def form_fields(self):
        """Retrieve form fields ready to be used."""
        _all_fields = {}
        # load model fields
        _model_fields = self.form_model.fields_get(
            self._form_model_fields, attributes=self._fields_attributes)
        _form_fields = self.fields_get(attributes=self._fields_attributes)
        # remove unwanted fields
        for fname in IGNORED_FORM_FIELDS:
            _form_fields.pop(fname, None)
        _all_fields.update(_model_fields)
        # form fields override model fields
        _all_fields.update(_form_fields)
        # update fields attributes
        self._form_update_fields_attributes(_all_fields)
        return _all_fields

    def _form_update_fields_attributes(self, fields):
        """Manipulate fields attributes."""
        for fname in self._form_required_fields:
            fields[fname]['required'] = True

    @property
    def form_file_fields(self):
        """File fields."""
        return [f for f in self.form_fields() if f['type'] == 'binary']


class TestPartnerForm(models.AbstractModel):
    """A test model form."""

    _name = 'cms.form.partner_test'
    _inherit = 'cms.form'
    _form_model = 'res.partner'
    _form_model_fields = ('name', 'country_id')
    _form_required_fields = ('name', 'country_id')

    custom = fields.Char()
