# -*- coding: utf-8 -*-
# Copyright 2026 Steven Marp

import base64
import hashlib
import uuid
import logging

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class DocumentSigner(models.Model):
    """An individual signer on a document signing request."""

    _name = "sm.document.signer"
    _description = "Document Signer"
    _inherit = ["mail.thread"]
    _order = "sequence, id"
    _rec_name = "display_name"

    # === Fields ===
    request_id = fields.Many2one(
        "sm.document.request",
        string="Signing Request",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(string="Order", default=10)

    # Signer info
    partner_id = fields.Many2one(
        "res.partner",
        string="Contact",
        help="Select a contact or enter name and email manually.",
    )
    name = fields.Char(
        string="Signer Name",
        required=True,
    )
    email = fields.Char(
        string="Email",
        required=True,
    )
    role = fields.Char(
        string="Role",
        help="e.g., Customer, Vendor, Manager, Witness",
    )

    # State
    state = fields.Selection(
        [
            ("pending", "Pending"),
            ("sent", "Sent"),
            ("viewed", "Viewed"),
            ("signed", "Signed"),
            ("declined", "Declined"),
            ("expired", "Expired"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="pending",
        required=True,
        tracking=True,
    )

    # Signature data
    signature = fields.Binary(
        string="Signature",
        help="The digital signature image.",
    )
    signature_type = fields.Selection(
        [
            ("draw", "Drawn"),
            ("type", "Typed"),
            ("upload", "Uploaded"),
        ],
        string="Signature Type",
    )
    signed_date = fields.Datetime(
        string="Signed Date",
        readonly=True,
    )
    signed_ip = fields.Char(
        string="IP Address",
        readonly=True,
        help="IP address of the signer when signing.",
    )
    signed_user_agent = fields.Char(
        string="User Agent",
        readonly=True,
    )

    # Access
    access_token = fields.Char(
        string="Access Token",
        copy=False,
        index=True,
    )
    signing_url = fields.Char(
        string="Signing URL",
        compute="_compute_signing_url",
    )

    # Email tracking
    sent_date = fields.Datetime(string="Sent Date")
    viewed_date = fields.Datetime(string="Viewed Date")
    reminder_count = fields.Integer(string="Reminders Sent", default=0)

    # Decline
    decline_reason = fields.Text(string="Decline Reason")

    # Related
    request_state = fields.Selection(
        related="request_id.state",
        string="Request Status",
    )
    document_subject = fields.Char(
        related="request_id.subject",
        string="Subject",
    )
    company_id = fields.Many2one(
        related="request_id.company_id",
        string="Company",
        store=True,
    )

    # === Computes ===
    def _compute_signing_url(self):
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url")
        for rec in self:
            if rec.access_token:
                rec.signing_url = f"{base_url}/sign/{rec.access_token}"
            else:
                rec.signing_url = False

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.name} ({rec.email})"

    # === Onchange ===
    @api.onchange("partner_id")
    def _onchange_partner_id(self):
        if self.partner_id:
            self.name = self.partner_id.name
            self.email = self.partner_id.email

    # === Actions ===
    def action_sign(self, signature_data, signature_type="draw", ip_address=None, user_agent=None):
        """Record a signature from the portal."""
        self.ensure_one()
        if self.state == "signed":
            raise UserError(_("This document has already been signed."))
        if self.state in ("expired", "cancelled"):
            raise UserError(_("This signing request is no longer active."))

        # Check expiration
        if self.request_id.expiration_date and fields.Date.today() > self.request_id.expiration_date:
            self.request_id._cron_expire_requests()
            raise UserError(_("This signing request has expired."))

        self.write({
            "signature": signature_data,
            "signature_type": signature_type,
            "signed_date": fields.Datetime.now(),
            "signed_ip": ip_address or "",
            "signed_user_agent": user_agent or "",
            "state": "signed",
        })

        self.request_id.message_post(
            body=_("✍️ %s (%s) has signed the document.") % (self.name, self.email),
            message_type="notification",
        )

        # Check if all signers are done
        self.request_id._check_completion()

        # If sequential, send to next signer
        if self.request_id.signing_order == "sequential":
            self._send_next_in_sequence()

        return True

    def action_decline(self, reason=None):
        """Decline to sign the document."""
        self.ensure_one()
        if self.state == "signed":
            raise UserError(_("Cannot decline — already signed."))

        self.write({
            "state": "declined",
            "decline_reason": reason or _("No reason provided."),
        })

        self.request_id.message_post(
            body=_("🚫 %s (%s) declined to sign. Reason: %s") % (
                self.name, self.email, reason or _("No reason provided.")
            ),
            message_type="notification",
        )

    def action_mark_viewed(self):
        """Mark the document as viewed by the signer."""
        self.ensure_one()
        if self.state == "sent":
            self.write({
                "state": "viewed",
                "viewed_date": fields.Datetime.now(),
            })
            self.request_id.message_post(
                body=_("👁️ %s (%s) viewed the document.") % (self.name, self.email),
                message_type="notification",
            )

    def _send_next_in_sequence(self):
        """In sequential mode, send to the next unsigned signer."""
        request = self.request_id
        next_signer = request.signer_ids.filtered(
            lambda s: s.state in ("pending",) and s.id != self.id
        ).sorted("sequence")[:1]
        if next_signer:
            next_signer.access_token = str(uuid.uuid4())
            request._send_signing_emails(signers=next_signer)

    # === Audit Hash ===
    def _generate_audit_hash(self):
        """Generate a SHA-256 hash for audit trail integrity."""
        self.ensure_one()
        data = f"{self.request_id.name}|{self.name}|{self.email}|{self.signed_date}|{self.signed_ip}"
        return hashlib.sha256(data.encode()).hexdigest()
