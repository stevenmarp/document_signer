# -*- coding: utf-8 -*-
# Copyright 2026 Steven Marp

import base64
import json
import logging

from odoo import http, _, fields
from odoo.http import request
from odoo.exceptions import AccessError

_logger = logging.getLogger(__name__)


class DocumentSignerPortal(http.Controller):
    """Portal controllers for document signing."""

    def _get_signer_by_token(self, token):
        """Find signer by access token and validate."""
        signer = request.env["sm.document.signer"].sudo().search([
            ("access_token", "=", token),
        ], limit=1)
        if not signer:
            return None
        return signer

    # === Signing Page ===
    @http.route("/sign/<string:token>", type="http", auth="public", website=True)
    def signing_page(self, token, **kwargs):
        """Public page where signer can view and sign the document."""
        signer = self._get_signer_by_token(token)
        if not signer:
            return request.render("sm_document_signer.portal_invalid_link", {})

        # Check states
        if signer.state == "signed":
            return request.render("sm_document_signer.portal_already_signed", {
                "signer": signer,
            })
        if signer.state in ("expired", "cancelled"):
            return request.render("sm_document_signer.portal_expired", {
                "signer": signer,
            })
        if signer.request_id.expiration_date and fields.Date.today() > signer.request_id.expiration_date:
            return request.render("sm_document_signer.portal_expired", {
                "signer": signer,
            })

        # Mark as viewed
        if signer.state == "sent":
            signer.action_mark_viewed()

        # Get PDF as base64
        doc_request = signer.request_id
        pdf_base64 = doc_request.document_file.decode("utf-8") if doc_request.document_file else ""

        return request.render("sm_document_signer.portal_signing_page", {
            "signer": signer,
            "doc_request": doc_request,
            "pdf_base64": pdf_base64,
            "company": doc_request.company_id or request.env.company,
        })

    # === Submit Signature ===
    @http.route("/sign/<string:token>/submit", type="json", auth="public", methods=["POST"])
    def submit_signature(self, token, signature=None, signature_data=None, signature_type="draw", **kwargs):
        """Submit a signature via AJAX."""
        signer = self._get_signer_by_token(token)
        if not signer:
            return {"success": False, "error": "Invalid signing link."}

        sig_data = signature or signature_data
        if not sig_data:
            return {"success": False, "error": "No signature provided."}

        try:
            # Get IP and user agent
            ip_address = request.httprequest.remote_addr
            user_agent = request.httprequest.user_agent.string

            # Clean base64 data (remove data:image/png;base64, prefix)
            if "," in sig_data:
                sig_data = sig_data.split(",")[1]

            signer.action_sign(
                signature_data=sig_data,
                signature_type=signature_type,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            return {
                "success": True,
                "message": "Document signed successfully! Thank you.",
            }
        except Exception as e:
            _logger.exception("Error signing document: %s", str(e))
            return {"success": False, "error": str(e)}

    # === Decline ===
    @http.route("/sign/<string:token>/decline", type="json", auth="public", methods=["POST"])
    def decline_signature(self, token, reason=None, **kwargs):
        """Decline to sign via AJAX."""
        signer = self._get_signer_by_token(token)
        if not signer:
            return {"success": False, "error": "Invalid signing link."}

        try:
            signer.action_decline(reason=reason)
            return {
                "success": True,
                "message": "You have declined to sign this document.",
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # === View PDF Inline (for iframe preview) ===
    @http.route("/sign/<string:token>/view", type="http", auth="public")
    def view_document(self, token, **kwargs):
        """View the PDF inline in an iframe."""
        signer = self._get_signer_by_token(token)
        if not signer:
            return request.not_found()

        doc_request = signer.request_id
        if not doc_request.document_file:
            return request.not_found()

        pdf_content = base64.b64decode(doc_request.document_file)
        filename = doc_request.document_filename or "document.pdf"

        return request.make_response(
            pdf_content,
            headers=[
                ("Content-Type", "application/pdf"),
                ("Content-Disposition", f'inline; filename="{filename}"'),
            ],
        )

    # === Download Original PDF ===
    @http.route("/sign/<string:token>/download", type="http", auth="public")
    def download_document(self, token, **kwargs):
        """Download the original PDF document."""
        signer = self._get_signer_by_token(token)
        if not signer:
            return request.not_found()

        doc_request = signer.request_id
        if not doc_request.document_file:
            return request.not_found()

        pdf_content = base64.b64decode(doc_request.document_file)
        filename = doc_request.document_filename or "document.pdf"

        return request.make_response(
            pdf_content,
            headers=[
                ("Content-Type", "application/pdf"),
                ("Content-Disposition", f'attachment; filename="{filename}"'),
            ],
        )
