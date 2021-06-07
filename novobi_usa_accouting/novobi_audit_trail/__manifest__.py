{
    'name': 'Novobi: Audit Trail',
    'summary': 'Novobi: Audit Trail',
    'author': 'Novobi',
    'website': 'https://www.novobi.com/',
    'depends': [
        'base',
        'sale',
        # 'account_voucher',
        'l10n_us_accounting',  # Remove this and update the data file if user not have this
    ],
    'data': [
        'security/ir.model.access.csv',
        
        'data/audit_trail_log_sequence.xml',
        'data/default_audit_rules.xml',
        
        'views/audit_trail_rule_views.xml',
        'views/audit_trail_log_views.xml',
    ],
    'application': False,
    'installable': True,
}
