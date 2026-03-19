# -*- coding: utf-8 -*-
# Copyright 2026 Steven Marp
{
    "name": "Document Signer",
    "version": "18.0.1.0.0",
    "summary": "Digital document signing workflow — send, track, and sign documents online",
    "description": """
Document Signer — Digital Document Signing for Odoo
=====================================================

Send documents for digital signature directly from Odoo.
Track signing status in real-time with a beautiful OWL dashboard.

Key Features
------------
* Upload PDF documents for signing
* Send signature requests via email with secure portal link
* Multiple signers with signing order
* Draw, type, or upload signature
* Real-time tracking: Sent → Viewed → Signed
* Signed PDF with signature overlay stored as attachment
* OWL Dashboard with stats and activity feed
* Works with Sale Orders, Purchase Orders, Invoices, or standalone
* Complete audit trail with IP address and timestamp
* Expiration dates on signature requests
* Reminder emails for pending signatures

Author: Steven Marp
    """,
    "author": "Steven Marp",
    "website": "https://apps.odoo.com/apps/browse?repo_maintainer_id=512936",
    "category": "Productivity",
    "license": "OPL-1",
    "depends": ["base", "mail", "portal", "web"],
    "data": [
        # Security
        "security/signer_security.xml",
        "security/ir.model.access.csv",
        # Data
        "data/signer_sequence.xml",
        "data/signer_mail_templates.xml",
        "data/signer_cron.xml",
        # Views
        "views/document_request_views.xml",
        "views/document_signer_views.xml",
        "views/menu.xml",
        # Templates
        "templates/portal_templates.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "sm_document_signer/static/src/js/signer_dashboard.js",
            "sm_document_signer/static/src/xml/signer_dashboard.xml",
            "sm_document_signer/static/src/scss/signer_dashboard.scss",
        ],
        "web.assets_frontend": [
            "sm_document_signer/static/src/js/signing_portal.js",
            "sm_document_signer/static/src/scss/signing_portal.scss",
        ],
    },
    "images": ["static/description/banner.gif"],
    "installable": True,
    "application": True,
    "auto_install": False,
    "price": 299.00,
    "currency": "USD",
}
