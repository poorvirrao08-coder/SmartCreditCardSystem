"use strict";

async function api(path, options = {}) {
    const config = {
        method: options.method || "GET",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin"
    };
    if (options.body) config.body = typeof options.body === "string" ? options.body : JSON.stringify(options.body);
    try {
        const response = await fetch(path, config);
        return await response.json();
    } catch (error) {
        return { success: false, error: "Unable to contact the server: " + error.message };
    }
}

function money(value) {
    return "₹" + Number(value || 0).toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function escapeHtml(value) {
    return String(value === null || value === undefined ? "" : value)
        .replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
}

function notify(message, type = "success") {
    const box = document.getElementById("page-alert") || document.getElementById("auth-error");
    if (!box) return;
    box.className = "alert " + type;
    box.textContent = message;
    box.classList.remove("hidden");
    setTimeout(() => box.classList.add("hidden"), 5000);
}

let modalCallback = null;
function openModal(title, bodyHtml, callback) {
    document.getElementById("modal-title").textContent = title;
    document.getElementById("modal-body").innerHTML = '<form id="modal-form">' + bodyHtml + "</form>";
    modalCallback = callback;
    document.getElementById("modal-backdrop").classList.add("open");
}
function closeModal() {
    document.getElementById("modal-backdrop").classList.remove("open");
    modalCallback = null;
}
document.addEventListener("DOMContentLoaded", function () {
    const submit = document.getElementById("modal-submit");
    if (submit) {
        submit.addEventListener("click", async function () {
            if (!modalCallback) return;
            const form = document.getElementById("modal-form");
            if (!form.reportValidity()) return;
            const data = Object.fromEntries(new FormData(form).entries());
            const result = await modalCallback(data);
            if (result && result.success !== false) closeModal();
        });
    }
    document.getElementById("modal-backdrop").addEventListener("click", function (event) {
        if (event.target.id === "modal-backdrop") closeModal();
    });
});

function field(label, name, type = "text", value = "", extra = "") {
    return `<div class="field"><label>${escapeHtml(label)}</label><input name="${name}" type="${type}" value="${escapeHtml(value)}" ${extra}></div>`;
}

function bindAuthForm(formId, endpoint) {
    const form = document.getElementById(formId);
    form.addEventListener("submit", async function (event) {
        event.preventDefault();
        const payload = Object.fromEntries(new FormData(form).entries());
        const result = await api(endpoint, { method: "POST", body: payload });
        if (result.success) {
            window.location.href = "/dashboard";
        } else {
            notify(result.error || "Request failed", "error");
        }
    });
}

async function loadDashboard() {
    const result = await api("/api/dashboard");
    if (!result.success) { notify(result.error, "error"); return; }
    const data = result.data;

    document.getElementById("stat-cards").textContent = data.credit.card_count;
    document.getElementById("stat-limit").textContent = money(data.credit.total_limit);
    document.getElementById("stat-available").textContent = money(data.credit.available_credit);
    document.getElementById("stat-spend").textContent = money(data.spending.monthly_spending);
    document.getElementById("stat-txn-note").textContent = data.spending.monthly_transactions + " transactions this month";
    document.getElementById("stat-outstanding").textContent = money(data.outstanding);
    document.getElementById("stat-cards").parentElement.classList.add("accent");

    const utilization = Number(data.credit.utilization || 0);
    const utilLevel = utilization > 70 ? "high" : "";
    document.getElementById("utilization-box").innerHTML = `
        <div style="font-size:30px;font-weight:800;color:var(--navy);">${utilization}%</div>
        <div class="progress ${utilLevel}"><span style="width:${Math.min(utilization, 100)}%"></span></div>
        <p style="color:var(--muted);font-size:12px;margin-top:10px;">${money(data.credit.used_credit)} used of ${money(data.credit.total_limit)}</p>`;

    const maxTrend = Math.max(...data.spending_trend.map(row => Number(row.total_spent)), 1);
    document.getElementById("spending-trend").innerHTML = data.spending_trend.length
        ? data.spending_trend.map(row => `
            <div class="bar-row">
                <span>${row.spend_month}</span>
                <div class="bar-track"><div class="bar-fill" style="width:${(Number(row.total_spent) / maxTrend) * 100}%"></div></div>
                <span class="bar-value">${money(row.total_spent)}</span>
            </div>`).join("")
        : '<div class="empty-state">No spending recorded yet.</div>';

    document.getElementById("recent-txn").innerHTML = data.recent_transactions.length
        ? data.recent_transactions.map(row => `
            <tr><td><strong>${escapeHtml(row.merchant_name)}</strong></td><td>${escapeHtml(row.category_name)}</td>
            <td>${escapeHtml(row.card_name)}<br><small style="color:var(--muted);">${escapeHtml(row.card_number_masked)}</small></td>
            <td class="nowrap">${String(row.transaction_date).slice(0, 10)}</td>
            <td style="text-align:right;font-weight:700;">${money(row.amount)}</td></tr>`).join("")
        : '<tr><td colspan="5" class="empty-state">No transactions yet.</td></tr>';

    document.getElementById("upcoming-payments").innerHTML = data.upcoming_payments.length
        ? data.upcoming_payments.map(row => `
            <div style="padding:11px 0;border-bottom:1px solid #f0f3f8;">
                <div style="display:flex;justify-content:space-between;gap:8px;">
                    <strong>${escapeHtml(row.card_name)}</strong><span style="color:var(--red);font-weight:700;">${money(row.outstanding_amount)}</span>
                </div>
                <div style="color:var(--muted);font-size:12px;margin-top:4px;">Due ${row.due_date} · ${row.days_until_due} days</div>
            </div>`).join("")
        : '<div class="empty-state">No upcoming payments.</div>';

    const maxCategory = Math.max(...data.category_breakdown.map(row => Number(row.total_spent)), 1);
    document.getElementById("category-bars").innerHTML = data.category_breakdown.length
        ? data.category_breakdown.map(row => `
            <div class="bar-row"><span>${escapeHtml(row.category_name)}</span>
                <div class="bar-track"><div class="bar-fill" style="width:${(Number(row.total_spent) / maxCategory) * 100}%"></div></div>
                <span class="bar-value">${money(row.total_spent)}</span></div>`).join("")
        : '<div class="empty-state">Add transactions to see category insights.</div>';

    const categories = await api("/api/recommendation-categories");
    const select = document.getElementById("recommend-category");
    if (categories.success) {
        select.innerHTML = categories.data.map(row => `<option value="${escapeHtml(row.category_name)}">${escapeHtml(row.category_name)}</option>`).join("");
    }
    document.getElementById("recommend-form").addEventListener("submit", async function (event) {
        event.preventDefault();
        const payload = Object.fromEntries(new FormData(event.target).entries());
        const response = await api("/api/recommendations", { method: "POST", body: payload });
        const box = document.getElementById("recommend-result");
        if (!response.success) { box.innerHTML = `<div class="alert error">${escapeHtml(response.error)}</div>`; return; }
        const best = response.data.recommended;
        if (!best) {
            box.innerHTML = '<div class="alert error">No eligible card found for this purchase.</div>';
            return;
        }
        box.innerHTML = `
            <div style="border-left:4px solid var(--gold);background:#fffaf0;padding:15px;border-radius:9px;">
                <div style="font-size:11px;color:var(--muted);font-weight:800;letter-spacing:1px;">BEST CARD FOR THIS PURCHASE</div>
                <h3 style="color:var(--navy);margin:7px 0;">${escapeHtml(best.card_name)} · ${escapeHtml(best.bank_name)}</h3>
                <div style="font-size:22px;font-weight:800;color:var(--green);">${money(best.expected_value)} benefit</div>
                <div class="reason">${escapeHtml(best.reason)}</div>
            </div>
            <p style="margin-top:12px;font-size:12px;color:var(--muted);">${response.data.eligible_cards.length} eligible card(s) compared · ${response.data.ineligible_cards.length} excluded.</p>`;
    });
}

async function loadMyCards() {
    const result = await api("/api/cards");
    if (!result.success) { notify(result.error, "error"); return; }
    const cards = result.data;
    const themes = ["", "gold-card", "green-card"];
    document.getElementById("my-cards").innerHTML = cards.length
        ? cards.map((row, index) => `
            <div>
                <div class="bank-card ${themes[index % 3]}">
                    <div class="bank-card-top"><span>${escapeHtml(row.bank_name)}</span><span>${escapeHtml(row.card_type || "CARD")}</span></div>
                    <div class="bank-card-number">${escapeHtml(row.card_number_masked)}</div>
                    <div class="bank-card-bottom">
                        <div><span>AVAILABLE CREDIT</span><strong>${money(row.available_credit)}</strong></div>
                        <div style="text-align:right;"><span>LIMIT</span><strong>${money(row.credit_limit)}</strong></div>
                    </div>
                </div>
                <div style="padding:12px 2px;">
                    <strong style="color:var(--navy);">${escapeHtml(row.card_name)}</strong>
                    <span class="badge ${row.status === 'active' ? 'green' : 'orange'}" style="margin-left:6px;">${row.status}</span>
                    <div class="progress ${row.utilization_pct > 70 ? 'high' : ''}"><span style="width:${Math.min(row.utilization_pct, 100)}%"></span></div>
                    <small style="color:var(--muted);">${row.utilization_pct}% used · bill ${row.billing_day}, due ${row.due_day}</small>
                    <div style="margin-top:10px;display:flex;gap:7px;">
                        <button class="btn ghost small" onclick='editCard(${row.user_card_id})'>Edit</button>
                        <button class="btn danger small" onclick='deleteCard(${row.user_card_id})'>Delete</button>
                    </div>
                </div>
            </div>`).join("")
        : '<div class="card empty-state">No cards added yet. Click “Add card”.</div>';
}

async function openAddCard() {
    const catalogue = await api("/api/cards/catalogue");
    const options = catalogue.success
        ? catalogue.data.map(row => `<option value="${row.card_id}">${escapeHtml(row.bank_name)} — ${escapeHtml(row.card_name)}</option>`).join("")
        : "";
    openModal("Add a credit card", `
        <div class="field"><label>Catalogue card</label><select name="card_id"><option value="">Create a new card</option>${options}</select></div>
        <div class="form-grid">
            ${field("Card name (new card)", "card_name")}
            ${field("Bank name (new card)", "bank_name")}
        </div>
        ${field("Card number", "card_number", "text", "", 'inputmode="numeric" placeholder="4111 1111 1111 1111" required')}
        <div class="form-grid">
            ${field("Credit limit", "credit_limit", "number", "100000", "min=1 step=0.01 required")}
            ${field("Cardholder name", "cardholder_name")}
            ${field("Billing day", "billing_day", "number", "5", "min=1 max=28 required")}
            ${field("Due day", "due_day", "number", "25", "min=1 max=28 required")}
        </div>
        <p style="font-size:11px;color:var(--muted);margin-top:8px;">Only the masked number (last 4 digits) is stored.</p>`,
        async function (data) {
            const result = await api("/api/cards", { method: "POST", body: data });
            notify(result.success ? result.message : result.error, result.success ? "success" : "error");
            if (result.success) loadMyCards();
            return result;
        });
}

async function editCard(id) {
    const response = await api("/api/cards/" + id);
    if (!response.success) { notify(response.error, "error"); return; }
    const row = response.data;
    openModal("Update card", `
        <div class="form-grid">
            ${field("Credit limit", "credit_limit", "number", row.credit_limit, "min=1 step=0.01 required")}
            ${field("Cardholder name", "cardholder_name", "text", row.cardholder_name || "")}
            ${field("Billing day", "billing_day", "number", row.billing_day, "min=1 max=28")}
            ${field("Due day", "due_day", "number", row.due_day, "min=1 max=28")}
        </div>
        <div class="field"><label>Status</label><select name="status">
            ${["active", "frozen", "closed"].map(value => `<option value="${value}" ${row.status === value ? "selected" : ""}>${value}</option>`).join("")}
        </select></div>`,
        async function (data) {
            const result = await api("/api/cards/" + id, { method: "PUT", body: data });
            notify(result.success ? result.message : result.error, result.success ? "success" : "error");
            if (result.success) loadMyCards();
            return result;
        });
}

async function deleteCard(id) {
    if (!confirm("Delete this card and all of its transactions and payments?")) return;
    const result = await api("/api/cards/" + id, { method: "DELETE" });
    notify(result.success ? result.message : result.error, result.success ? "success" : "error");
    if (result.success) loadMyCards();
}

async function loadTransactions() {
    const params = new URLSearchParams();
    const month = document.getElementById("filter-month").value;
    const category = document.getElementById("filter-category").value;
    const card = document.getElementById("filter-card").value;
    if (month) params.set("month", month);
    if (category) params.set("category", category);
    if (card) params.set("card_id", card);

    const [listResult, summaryResult, cardsResult, categoriesResult] = await Promise.all([
        api("/api/transactions?" + params.toString()),
        api("/api/transactions/summary?" + params.toString()),
        api("/api/cards"),
        api("/api/recommendation-categories")
    ]);
    if (!listResult.success) { notify(listResult.error, "error"); return; }

    if (cardsResult.success) {
        const current = card;
        document.getElementById("filter-card").innerHTML = '<option value="">All cards</option>' +
            cardsResult.data.map(row => `<option value="${row.user_card_id}" ${String(current) === String(row.user_card_id) ? "selected" : ""}>${escapeHtml(row.card_name)} · ${escapeHtml(row.card_number_masked)}</option>`).join("");
    }
    if (categoriesResult.success) {
        const current = category;
        document.getElementById("filter-category").innerHTML = '<option value="">All categories</option>' +
            categoriesResult.data.map(row => `<option value="${escapeHtml(row.category_name)}" ${current === row.category_name ? "selected" : ""}>${escapeHtml(row.category_name)}</option>`).join("");
    }

    document.getElementById("transaction-list").innerHTML = listResult.data.length
        ? listResult.data.map(row => `
            <tr><td class="nowrap">${String(row.transaction_date).slice(0, 10)}</td>
            <td><strong>${escapeHtml(row.merchant_name)}</strong></td><td>${escapeHtml(row.category_name)}</td>
            <td>${escapeHtml(row.card_name)}<br><small style="color:var(--muted);">${escapeHtml(row.card_number_masked)}</small></td>
            <td><span class="badge ${row.status === 'posted' ? 'green' : 'orange'}">${row.status}</span></td>
            <td style="text-align:right;font-weight:700;">${money(row.amount)}</td>
            <td class="nowrap"><button class="btn ghost small" onclick='editTransaction(${row.transaction_id})'>Edit</button>
            <button class="btn danger small" onclick='deleteTransaction(${row.transaction_id})'>Delete</button></td></tr>`).join("")
        : '<tr><td colspan="7" class="empty-state">No transactions found.</td></tr>';

    if (summaryResult.success) {
        const rows = summaryResult.data;
        const max = Math.max(...rows.map(row => Number(row.total_spent)), 1);
        document.getElementById("txn-summary").innerHTML = rows.length
            ? rows.map(row => `<div class="bar-row"><span>${escapeHtml(row.category_name)}</span>
                <div class="bar-track"><div class="bar-fill" style="width:${(Number(row.total_spent) / max) * 100}%"></div></div>
                <span class="bar-value">${money(row.total_spent)}</span></div>`).join("")
            : '<div class="empty-state">No summary available.</div>';
        const total = rows.reduce((sum, row) => sum + Number(row.total_spent), 0);
        const count = rows.reduce((sum, row) => sum + Number(row.transactions), 0);
        document.getElementById("txn-totals").innerHTML = `
            <div class="stat"><div class="stat-label">TOTAL SPENDING</div><div class="stat-value">${money(total)}</div></div>
            <div class="stat" style="margin-top:12px;"><div class="stat-label">TRANSACTIONS</div><div class="stat-value">${count}</div></div>
            <div class="stat" style="margin-top:12px;"><div class="stat-label">AVERAGE TRANSACTION</div><div class="stat-value">${money(count ? total / count : 0)}</div></div>`;
    }
}

async function openAddTransaction() {
    const [cardsResult, categoriesResult] = await Promise.all([api("/api/cards"), api("/api/recommendation-categories")]);
    const cards = cardsResult.success ? cardsResult.data : [];
    const categories = categoriesResult.success ? categoriesResult.data : [];
    openModal("Record a transaction", `
        <div class="field"><label>Card</label><select name="user_card_id" required>${cards.map(row => `<option value="${row.user_card_id}">${escapeHtml(row.card_name)} · ${escapeHtml(row.card_number_masked)}</option>`).join("")}</select></div>
        <div class="field"><label>Category</label><select name="category" required>${categories.map(row => `<option value="${escapeHtml(row.category_name)}">${escapeHtml(row.category_name)}</option>`).join("")}</select></div>
        <div class="form-grid">
            ${field("Merchant", "merchant_name", "text", "", "required")}
            ${field("Amount", "amount", "number", "", "min=0.01 step=0.01 required")}
            ${field("Date", "transaction_date", "date", new Date().toISOString().slice(0, 10))}
        </div>
        ${field("Description", "description")}`,
        async function (data) {
            const result = await api("/api/transactions", { method: "POST", body: data });
            notify(result.success ? result.message : result.error, result.success ? "success" : "error");
            if (result.success) loadTransactions();
            return result;
        });
}

async function editTransaction(id) {
    const cards = await api("/api/cards");
    const list = await api("/api/transactions");
    const row = list.success ? list.data.find(item => item.transaction_id === id) : null;
    if (!row) { notify("Transaction not found", "error"); return; }
    openModal("Update transaction", `
        <div class="field"><label>Card</label><select name="user_card_id">${cards.data.map(card => `<option value="${card.user_card_id}" ${card.user_card_id === row.user_card_id ? "selected" : ""}>${escapeHtml(card.card_name)}</option>`).join("")}</select></div>
        <div class="form-grid">
            ${field("Merchant", "merchant_name", "text", row.merchant_name, "required")}
            ${field("Amount", "amount", "number", row.amount, "min=0.01 step=0.01 required")}
        </div>
        ${field("Description", "description", "text", row.description || "")}`,
        async function (data) {
            const result = await api("/api/transactions/" + id, { method: "PUT", body: data });
            notify(result.success ? result.message : result.error, result.success ? "success" : "error");
            if (result.success) loadTransactions();
            return result;
        });
}

async function deleteTransaction(id) {
    if (!confirm("Delete this transaction? Available credit will be restored.")) return;
    const result = await api("/api/transactions/" + id, { method: "DELETE" });
    notify(result.success ? result.message : result.error, result.success ? "success" : "error");
    if (result.success) loadTransactions();
}

async function loadPayments() {
    const [upcoming, history] = await Promise.all([api("/api/payments/upcoming"), api("/api/payments")]);
    if (!upcoming.success || !history.success) { notify("Unable to load payments", "error"); return; }

    document.getElementById("upcoming-cards").innerHTML = upcoming.data.length
        ? upcoming.data.map(row => `
            <div class="card" style="border-top:4px solid var(--gold);">
                <strong style="color:var(--navy);">${escapeHtml(row.card_name)}</strong>
                <div style="font-size:24px;font-weight:800;margin:10px 0;">${money(row.outstanding_amount)}</div>
                <div style="color:var(--muted);font-size:12px;">Due ${row.due_date} · ${row.days_until_due} days remaining</div>
                <span class="badge ${row.days_until_due < 0 ? 'red' : 'orange'}" style="margin-top:10px;">${escapeHtml(row.status)}</span>
            </div>`).join("")
        : '<div class="card empty-state">No upcoming dues.</div>';

    document.getElementById("payment-list").innerHTML = history.data.length
        ? history.data.map(row => `
            <tr><td class="nowrap">${row.payment_date}</td>
            <td>${escapeHtml(row.card_name)}<br><small style="color:var(--muted);">${escapeHtml(row.card_number_masked)}</small></td>
            <td>${escapeHtml(row.payment_method)}</td><td>${escapeHtml(row.reference_number || "—")}</td>
            <td><span class="badge ${row.status === 'completed' ? 'green' : 'orange'}">${row.status}</span></td>
            <td style="text-align:right;font-weight:700;">${money(row.amount)}</td>
            <td class="nowrap"><button class="btn ghost small" onclick='markPayment(${row.payment_id})'>Toggle</button>
            <button class="btn danger small" onclick='deletePayment(${row.payment_id})'>Delete</button></td></tr>`).join("")
        : '<tr><td colspan="7" class="empty-state">No payments recorded.</td></tr>';
}

async function openAddPayment() {
    const cards = await api("/api/cards");
    openModal("Record a payment", `
        <div class="field"><label>Card</label><select name="user_card_id" required>${(cards.data || []).map(row => `<option value="${row.user_card_id}">${escapeHtml(row.card_name)} · ${escapeHtml(row.card_number_masked)}</option>`).join("")}</select></div>
        <div class="form-grid">
            ${field("Amount", "amount", "number", "", "min=0.01 step=0.01 required")}
            ${field("Payment date", "payment_date", "date", new Date().toISOString().slice(0, 10))}
        </div>
        <div class="field"><label>Method</label><select name="payment_method">
            ${["upi", "net_banking", "card", "cash", "other"].map(value => `<option value="${value}">${value.replace("_", " ")}</option>`).join("")}
        </select></div>
        <div class="form-grid">
            ${field("Reference number", "reference_number")}
            ${field("Notes", "notes")}
        </div>`,
        async function (data) {
            const result = await api("/api/payments", { method: "POST", body: data });
            notify(result.success ? result.message : result.error, result.success ? "success" : "error");
            if (result.success) loadPayments();
            return result;
        });
}

async function markPayment(id) {
    const result = await api("/api/payments/" + id, {
        method: "PUT",
        body: { status: "pending" }
    });
    notify(result.success ? "Payment status updated" : result.error, result.success ? "success" : "error");
    if (result.success) loadPayments();
}

async function deletePayment(id) {
    if (!confirm("Delete this payment?")) return;
    const result = await api("/api/payments/" + id, { method: "DELETE" });
    notify(result.success ? result.message : result.error, result.success ? "success" : "error");
    if (result.success) loadPayments();
}
