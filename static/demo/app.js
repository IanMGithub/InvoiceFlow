const resultStatus = document.getElementById("result-status");
const resultCard = document.getElementById("result-card");
const buttons = document.querySelectorAll("[data-sample-id]");

function setStatus(text, kind) {
  resultStatus.textContent = text;
  resultStatus.className = "status" + (kind ? " status-" + kind : "");
}

function displayValue(value) {
  if (value === null || value === undefined || value === "") {
    return "None";
  }
  return String(value);
}

function formatCents(value) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "an unknown amount";
  }
  const negative = value < 0;
  const dollars = (Math.abs(value) / 100).toFixed(2);
  return (negative ? "-" : "") + "$" + dollars + " (" + value + " cents)";
}

function describeIssue(issue) {
  if (!issue || typeof issue !== "object") {
    return "An issue was recorded.";
  }
  const code = issue.code;
  if (code === "QUANTITY_MISMATCH") {
    return (
      "Quantity for " +
      displayValue(issue.item_code) +
      " does not match the purchase order. The purchase order quantity is " +
      displayValue(issue.expected_quantity) +
      " and the invoice quantity is " +
      displayValue(issue.observed_quantity) +
      "."
    );
  }
  if (code === "UNIT_PRICE_MISMATCH") {
    return (
      "Unit price for " +
      displayValue(issue.item_code) +
      " does not match the purchase order. The purchase order price is " +
      formatCents(issue.expected_cents) +
      " and the invoice price is " +
      formatCents(issue.observed_cents) +
      "."
    );
  }
  if (code === "PO_TOTAL_MISMATCH") {
    return (
      "The invoice total does not match the purchase order total. The purchase order total is " +
      formatCents(issue.expected_cents) +
      " and the invoice total is " +
      formatCents(issue.observed_cents) +
      "."
    );
  }
  if (code === "INVOICE_LINE_TOTAL_MISMATCH") {
    return (
      "A stated line total does not match quantity times unit price for " +
      displayValue(issue.item_code) +
      ". The calculated total is " +
      formatCents(issue.expected_cents) +
      " and the invoice states " +
      formatCents(issue.observed_cents) +
      "."
    );
  }
  if (code === "INVOICE_TOTAL_MISMATCH") {
    return (
      "The stated invoice total does not match the sum of its line totals. The line sum is " +
      formatCents(issue.expected_cents) +
      " and the invoice states " +
      formatCents(issue.observed_cents) +
      "."
    );
  }
  if (code === "ITEM_UNMATCHED") {
    return "Item " + displayValue(issue.item_code) + " is not on the purchase order.";
  }
  if (code === "PO_ITEM_MISSING_FROM_INVOICE") {
    return (
      "Purchase order item " +
      displayValue(issue.item_code) +
      " is missing from the invoice."
    );
  }
  if (typeof issue.message === "string" && issue.message !== "") {
    return issue.code ? issue.code + ": " + issue.message : issue.message;
  }
  if (issue.code) {
    return "Issue " + issue.code + " was recorded.";
  }
  return "An issue was recorded.";
}

function statusMeaning(status, issueCount) {
  if (status === "matched" && issueCount === 0) {
    return "No issues found by the implemented checks. Matched means the vendor and purchase order were found and the checks ran. It does not mean the invoice is approved or safe to pay.";
  }
  if (status === "matched") {
    return "The vendor and purchase order were found, and the checks recorded issues. Matched does not mean the invoice is approved or safe to pay.";
  }
  return (
    "Processing status: " +
    displayValue(status) +
    ". This demo does not approve invoices or send payments."
  );
}

function renderIssues(issues) {
  const list = document.getElementById("result-issues");
  list.replaceChildren();
  if (!Array.isArray(issues) || issues.length === 0) {
    const item = document.createElement("li");
    item.textContent = "No issues found by the implemented checks.";
    list.appendChild(item);
    return;
  }
  issues.forEach(function (issue) {
    const item = document.createElement("li");
    item.textContent = describeIssue(issue);
    list.appendChild(item);
  });
}

function showResult(body) {
  const processing = body.processing_result || {};
  const issues = Array.isArray(processing.issues) ? processing.issues : [];
  resultCard.hidden = false;
  document.getElementById("result-title").textContent = displayValue(body.title);
  document.getElementById("result-scenario").textContent = displayValue(
    body.scenario
  );
  document.getElementById("result-timing").textContent = body.computed_at_startup
    ? "This result was computed when the demo process started. Showing it did not create another invoice record."
    : "The demo returned a result.";
  document.getElementById("result-invoice-number").textContent = displayValue(
    processing.invoice_number
  );
  document.getElementById("result-processing-status").textContent = displayValue(
    processing.status
  );
  document.getElementById("result-vendor-id").textContent = displayValue(
    processing.vendor_id
  );
  document.getElementById("result-po-id").textContent = displayValue(
    processing.purchase_order_id
  );
  document.getElementById("result-meaning").textContent = statusMeaning(
    processing.status,
    issues.length
  );
  renderIssues(issues);
  document.getElementById("result-json").textContent = JSON.stringify(body, null, 2);
  setStatus(
    issues.length === 0
      ? "No issues found by the implemented checks."
      : "Checks finished with issues.",
    issues.length === 0 ? "ok" : "issues"
  );
  document.getElementById("result-heading").focus();
}

function setBusy(isBusy) {
  buttons.forEach(function (button) {
    button.disabled = isBusy;
  });
  resultStatus.setAttribute("aria-busy", isBusy ? "true" : "false");
}

async function runExample(sampleId) {
  setBusy(true);
  setStatus("Loading the stored sample result...", "loading");
  try {
    const response = await fetch("/api/examples", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ sample_id: sampleId }),
    });
    let body = {};
    try {
      body = await response.json();
    } catch (error) {
      body = {};
    }
    document.getElementById("result-json").textContent = JSON.stringify(
      body,
      null,
      2
    );
    document.getElementById("result-json-details").open = !response.ok;

    if (response.status === 429) {
      resultCard.hidden = true;
      const retryAfter = response.headers.get("retry-after");
      const waitText =
        retryAfter && /^[0-9]+$/.test(retryAfter)
          ? " Try again in " + retryAfter + " seconds."
          : "";
      setStatus(
        "This demo is receiving too many requests from your network." + waitText,
        "limit"
      );
      return;
    }

    if (!response.ok) {
      resultCard.hidden = true;
      setStatus("The demo could not load that example.", "error");
      return;
    }

    showResult(body);
  } catch (error) {
    resultCard.hidden = true;
    setStatus("The demo could not load that example.", "error");
  } finally {
    setBusy(false);
  }
}

function isHttpUrl(value) {
  if (typeof value !== "string" || value === "") {
    return false;
  }
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:";
  } catch (error) {
    return false;
  }
}

function addLink(list, href, label) {
  if (!isHttpUrl(href)) {
    return false;
  }
  const item = document.createElement("li");
  const anchor = document.createElement("a");
  anchor.href = href;
  anchor.textContent = label;
  item.appendChild(anchor);
  list.appendChild(item);
  return true;
}

async function loadLinks() {
  const list = document.getElementById("project-link-list");
  const note = document.getElementById("links-note");
  try {
    const response = await fetch("/api/config");
    if (!response.ok) {
      return;
    }
    const config = await response.json();
    const added = [
      addLink(list, config.source_url, "Source code"),
      addLink(list, config.walkthrough_url, "Walkthrough"),
      addLink(list, config.contact_url, "Contact"),
    ].some(Boolean);
    if (added) {
      note.hidden = true;
    }
  } catch (error) {
    note.textContent =
      "Project links are unavailable. The sample buttons still work.";
  }
}

buttons.forEach(function (button) {
  button.addEventListener("click", function () {
    runExample(button.getAttribute("data-sample-id"));
  });
});

loadLinks();
