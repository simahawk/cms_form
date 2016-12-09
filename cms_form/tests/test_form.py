# -*- coding: utf-8 -*-
# Copyright 2016 Simone Orsi
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from openerp.tests.common import TransactionCase


class TestForm(TransactionCase):

    at_install = False
    post_install = True

    def setUp(self):
        super(TestForm, self).setUp()

    def test_fields(self):
        form = self.env['cms.form.partner_test']
        fields = form.form_fields()
        self.assertEqual(len(fields), 3)
        self.assertTrue('name' in fields.keys())
        self.assertTrue('country_id' in fields.keys())
        self.assertTrue('custom' in fields.keys())

    def test_fields_attributes(self):
        form = self.env['cms.form.partner_test']
        fields = form.form_fields()
        # fields from partner model
        self.assertTrue(fields['name']['required'])
        self.assertTrue(fields['country_id']['required'])
