# -*- coding: utf-8 -*-

{
    'name': 'Recurring Documents Plus',
    'version': '1.5',
    'category': 'Customization',
    'summary': '',
    'description': """
            Subscription Extended Module for Odoo V8

    """,
    'author' : 'ZedeS Technologies',
    'website' : 'http://www.zedestech.com',
    'depends': ['subscription', 'sale'],
    'data': [],
    'demo': [],
    'test': [],
    'update_xml': [
                    'subscription_view.xml',
                    'sale_template_view.xml',

                    'security/ir.model.access.csv',
                    
        ],
    'installable': True,
    'auto_install': False,
}
