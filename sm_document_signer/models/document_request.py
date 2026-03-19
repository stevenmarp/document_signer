# -*- coding: utf-8 -*-
# Copyright 2026 Steven Marp

import base64
import hashlib
import uuid
import logging
from datetime import timedelta

from odoo import api, fields, models, _, Command
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)


class DocumentRequest(models.Model):
    """A document signing request containing one PDF and one or more signers."""

    _name = "sm.document.request"
    _description = "Document Signing Request"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"
    _rec_name = "display_name"

    # === Fields ===
    name = fields.Char(
        string="Reference",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _("New"),
    )
    subject = fields.Char(
        string="Subject",
        required=True,
        tracking=True,
    )
    message = fields.Html(
        string="Message",
        help="Message to include in the signing request email.",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("sent", "Sent"),
            ("partial", "Partially Signed"),
            ("signed", "Fully Signed"),
            ("expired", "Expired"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        required=True,
        tracking=True,
        copy=False,
    )

    # Document
    document_file = fields.Binary(
        string="Document (PDF)",
        required=True,
        attachment=True,
        copy=True,
    )
    document_filename = fields.Char(string="Filename")
    signed_document = fields.Binary(
        string="Signed Document",
        attachment=True,
        readonly=True,
        copy=False,
    )
    signed_filename = fields.Char(string="Signed Filename", copy=False)

    # Signers
    signer_ids = fields.One2many(
        "sm.document.signer",
        "request_id",
        string="Signers",
        copy=True,
    )
    signer_count = fields.Integer(
        string="Signer Count",
        compute="_compute_signer_stats",
        store=True,
    )
    signed_count = fields.Integer(
        string="Signed",
        compute="_compute_signer_stats",
        store=True,
    )

    # Settings
    sender_id = fields.Many2one(
        "res.users",
        string="Sent By",
        default=lambda self: self.env.user,
        tracking=True,
    )
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company,
    )
    expiration_date = fields.Date(
        string="Expiration Date",
        help="After this date, signers can no longer sign the document.",
        tracking=True,
    )
    signing_order = fields.Selection(
        [
            ("simultaneous", "All signers at once"),
            ("sequential", "One by one (in order)"),
        ],
        string="Signing Order",
        default="simultaneous",
        required=True,
    )
    send_reminders = fields.Boolean(
        string="Send Reminders",
        default=True,
        help="Automatically send reminder emails for pending signatures.",
    )
    reminder_days = fields.Integer(
        string="Remind After (Days)",
        default=3,
        help="Send reminder after this many days if not signed.",
    )

    # Source document (optional link)
    res_model = fields.Char(string="Source Model")
    res_id = fields.Integer(string="Source ID")

    # Computed
    progress = fields.Float(
        string="Progress",
        compute="_compute_signer_stats",
        store=True,
    )

    # === Computes ===
    @api.depends("signer_ids", "signer_ids.state")
    def _compute_signer_stats(self):
        for rec in self:
            signers = rec.signer_ids
            rec.signer_count = len(signers)
            rec.signed_count = len(signers.filtered(lambda s: s.state == "signed"))
            rec.progress = (
                (rec.signed_count / rec.signer_count * 100)
                if rec.signer_count
                else 0.0
            )

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.name} - {rec.subject}" if rec.name != _("New") else rec.subject or _("New")

    # === CRUD ===
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", _("New")) == _("New"):
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "sm.document.request"
                ) or _("New")
        return super().create(vals_list)

    # === Constraints ===
    @api.constrains("document_filename")
    def _check_pdf(self):
        for rec in self:
            if rec.document_filename and not rec.document_filename.lower().endswith(".pdf"):
                raise ValidationError(_("Only PDF files are supported."))

    @api.constrains("signer_ids")
    def _check_signers(self):
        for rec in self:
            if rec.state != "draft" and not rec.signer_ids:
                raise ValidationError(_("At least one signer is required."))

    # === Actions ===
    def action_send(self):
        """Send the signing request to all signers."""
        self.ensure_one()
        if not self.document_file:
            raise UserError(_("Please upload a PDF document first."))
        if not self.signer_ids:
            raise UserError(_("Please add at least one signer."))

        # Generate access tokens for each signer
        for signer in self.signer_ids:
            if not signer.access_token:
                signer.access_token = str(uuid.uuid4())

        # Send emails
        self._send_signing_emails()
        self.write({"state": "sent"})

        self.message_post(
            body=_("📤 Signing request sent to %d signer(s).") % len(self.signer_ids),
            message_type="notification",
        )
        return True

    def action_cancel(self):
        """Cancel the signing request."""
        self.ensure_one()
        if self.state == "signed":
            raise UserError(_("Cannot cancel a fully signed document."))
        self.write({"state": "cancelled"})
        # Cancel pending signers
        self.signer_ids.filtered(lambda s: s.state != "signed").write(
            {"state": "cancelled"}
        )
        self.message_post(
            body=_("❌ Signing request cancelled."),
            message_type="notification",
        )

    def action_reset_to_draft(self):
        """Reset cancelled/expired request to draft."""
        self.ensure_one()
        if self.state not in ("cancelled", "expired"):
            raise UserError(_("Can only reset cancelled or expired requests."))
        self.write({"state": "draft"})
        self.signer_ids.write({"state": "pending", "access_token": False})

    def action_resend(self):
        """Resend emails to pending signers."""
        self.ensure_one()
        pending = self.signer_ids.filtered(lambda s: s.state in ("pending", "sent"))
        if not pending:
            raise UserError(_("No pending signers to resend to."))
        self._send_signing_emails(signers=pending)
        self.message_post(
            body=_("🔄 Resent signing request to %d signer(s).") % len(pending),
            message_type="notification",
        )

    def action_view_signed_document(self):
        """Download the signed document."""
        self.ensure_one()
        if not self.signed_document:
            raise UserError(_("No signed document available yet."))
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content?model=sm.document.request&id={self.id}"
                   f"&field=signed_document&filename_field=signed_filename&download=true",
            "target": "new",
        }

    # === Email Sending ===
    def _send_signing_emails(self, signers=None):
        """Send signing request emails to signers."""
        if signers is None:
            signers = self.signer_ids

        template = self.env.ref(
            "sm_document_signer.mail_template_signing_request",
            raise_if_not_found=False,
        )
        for signer in signers:
            if not signer.email:
                continue
            if template:
                template.send_mail(signer.id, force_send=True)
            signer.write({
                "state": "sent",
                "sent_date": fields.Datetime.now(),
            })

    # === Signer Completion Check ===
    def _check_completion(self):
        """Check if all signers have signed and update request state."""
        self.ensure_one()
        pending = self.signer_ids.filtered(lambda s: s.state != "signed")
        if not pending:
            self._finalize_signed_document()
            self.write({"state": "signed"})
            self.message_post(
                body=_("✅ All signers have signed! Document is complete."),
                message_type="notification",
            )
            # Notify sender
            self._notify_sender_complete()
        elif self.signed_count > 0:
            self.write({"state": "partial"})

    def _finalize_signed_document(self):
        """Generate the final signed PDF with signature overlays."""
        # For now, copy the original as signed document
        # In production, use reportlab/PyPDF2 to overlay signatures
        self.write({
            "signed_document": self.document_file,
            "signed_filename": f"signed_{self.document_filename or 'document.pdf'}",
        })

    def _notify_sender_complete(self):
        """Notify the sender that all signatures are collected."""
        template = self.env.ref(
            "sm_document_signer.mail_template_signing_complete",
            raise_if_not_found=False,
        )
        if template:
            template.send_mail(self.id, force_send=True)

    # === Cron Jobs ===
    @api.model
    def _cron_expire_requests(self):
        """Expire requests past their expiration date."""
        expired = self.search([
            ("state", "in", ("sent", "partial")),
            ("expiration_date", "<", fields.Date.today()),
        ])
        for request in expired:
            request.write({"state": "expired"})
            request.signer_ids.filtered(
                lambda s: s.state != "signed"
            ).write({"state": "expired"})
            request.message_post(
                body=_("⏰ Signing request expired."),
                message_type="notification",
            )
        if expired:
            _logger.info("Expired %d signing request(s).", len(expired))

    @api.model
    def _cron_send_reminders(self):
        """Send reminder emails to pending signers."""
        requests = self.search([
            ("state", "in", ("sent", "partial")),
            ("send_reminders", "=", True),
        ])
        now = fields.Datetime.now()
        for request in requests:
            for signer in request.signer_ids.filtered(
                lambda s: s.state == "sent" and s.sent_date
            ):
                days_since = (now - signer.sent_date).days
                if days_since >= request.reminder_days and days_since % request.reminder_days == 0:
                    if signer.reminder_count < 5:  # Max 5 reminders
                        request._send_signing_emails(signers=signer)
                        signer.reminder_count += 1
                        _logger.info(
                            "Sent reminder #%d to %s for %s",
                            signer.reminder_count, signer.email, request.name,
                        )

    # === Dashboard Stats ===
    @api.model
    def get_dashboard_stats(self):
        """Get dashboard statistics for the OWL dashboard."""
        user = self.env.user
        all_requests = self.search([])

        # My requests (sent by me)
        my_requests = all_requests.filtered(lambda r: r.sender_id == user)

        return {
            "stats": {
                "draft": len(my_requests.filtered(lambda r: r.state == "draft")),
                "sent": len(my_requests.filtered(lambda r: r.state in ("sent", "partial"))),
                "signed": len(my_requests.filtered(lambda r: r.state == "signed")),
                "expired": len(my_requests.filtered(lambda r: r.state == "expired")),
                "totalRequests": len(my_requests),
            },
            "recentRequests": [
                {
                    "id": r.id,
                    "name": r.name,
                    "subject": r.subject,
                    "state": r.state,
                    "signer_count": r.signer_count,
                    "signed_count": r.signed_count,
                    "progress": r.progress,
                    "create_date": r.create_date.strftime("%Y-%m-%d %H:%M") if r.create_date else "",
                }
                for r in my_requests.sorted("create_date", reverse=True)[:10]
            ],
            "pendingSigners": [
                {
                    "id": s.id,
                    "request_id": s.request_id.id,
                    "request_name": s.request_id.name,
                    "subject": s.request_id.subject,
                    "signer_name": s.partner_id.name or s.name,
                    "email": s.email,
                    "state": s.state,
                    "sent_date": s.sent_date.strftime("%Y-%m-%d") if s.sent_date else "",
                }
                for s in self.env["sm.document.signer"].search([
                    ("request_id.sender_id", "=", user.id),
                    ("state", "in", ("pending", "sent")),
                ], limit=10, order="sent_date desc")
            ],
        }
