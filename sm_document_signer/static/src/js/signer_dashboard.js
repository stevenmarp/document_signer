/** @odoo-module **/
/* Copyright 2026 Steven Marp */

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class SignerDashboard extends Component {
    static template = "sm_document_signer.SignerDashboard";
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loading: true,
            stats: { draft: 0, sent: 0, signed: 0, expired: 0, totalRequests: 0 },
            recentRequests: [],
            pendingSigners: [],
        });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    async loadData() {
        try {
            const data = await this.orm.call(
                "sm.document.request", "get_dashboard_stats", [], {}
            );
            this.state.stats = data.stats;
            this.state.recentRequests = data.recentRequests;
            this.state.pendingSigners = data.pendingSigners;
            this.state.loading = false;
        } catch (error) {
            console.error("Dashboard load error:", error);
            this.state.loading = false;
        }
    }

    openRequests(domain = []) {
        return this.action.doAction({
            type: "ir.actions.act_window",
            name: "Signing Requests",
            res_model: "sm.document.request",
            views: [[false, "list"], [false, "kanban"], [false, "form"]],
            domain: domain,
            target: "current",
        });
    }

    openDraft() { this.openRequests([["state", "=", "draft"]]); }
    openSent() { this.openRequests([["state", "in", ["sent", "partial"]]]); }
    openSigned() { this.openRequests([["state", "=", "signed"]]); }
    openExpired() { this.openRequests([["state", "=", "expired"]]); }
    openAll() { this.openRequests([]); }

    openRequest(requestId) {
        return this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "sm.document.request",
            res_id: requestId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    createNew() {
        return this.action.doAction({
            type: "ir.actions.act_window",
            name: "New Signing Request",
            res_model: "sm.document.request",
            views: [[false, "form"]],
            target: "current",
        });
    }

    getStateLabel(state) {
        const labels = {
            draft: "Draft", sent: "Sent", partial: "Partial",
            signed: "Signed", expired: "Expired", cancelled: "Cancelled",
            pending: "Pending", viewed: "Viewed", declined: "Declined",
        };
        return labels[state] || state;
    }

    getStateBadgeClass(state) {
        const classes = {
            draft: "bg-secondary", sent: "bg-warning", partial: "bg-info",
            signed: "bg-success", expired: "bg-danger", cancelled: "bg-dark",
            pending: "bg-secondary", viewed: "bg-info", declined: "bg-danger",
        };
        return classes[state] || "bg-secondary";
    }
}

registry.category("actions").add("sm_signer_dashboard", SignerDashboard);
