const SAMPLE_INVOICE = {
  invoice_number: "INV-1001",
  vendor_name: "Northstar Office Supply",
  po_reference: "PO-1001",
  currency: "USD",
  stated_total_cents: 210000,
  line_items: [
    {
      item_code: "PAPER-A4",
      description: "A4 paper cases",
      quantity: 10,
      unit_price_cents: 12000,
      stated_line_total_cents: 120000,
    },
    {
      item_code: "TONER-BK",
      description: "Black toner",
      quantity: 6,
      unit_price_cents: 15000,
      stated_line_total_cents: 90000,
    },
  ],
};

const form = document.getElementById("invoice-form");
const lineItemsContainer = document.getElementById("line-items");
const addLineItemButton = document.getElementById("add-line-item");
const submitButton = document.getElementById("submit-invoice");
const loadSampleButton = document.getElementById("load-sample");
const lookupForm = document.getElementById("lookup-form");

let lineItemCount = 1;

function createLineItem(values) {
  lineItemCount += 1;
  const index = lineItemCount;
  const item = document.createElement("div");
  item.className = "line-item";
  item.dataset.lineItem = "true";
  item.innerHTML = `
    <div class="field">
      <label for="item-code-${index}">Item code</label>
      <input id="item-code-${index}" name="item_code" type="text" required>
    </div>
    <div class="field">
      <label for="description-${index}">Description</label>
      <input id="description-${index}" name="description" type="text" required>
    </div>
    <div class="field">
      <label for="quantity-${index}">Quantity</label>
      <input id="quantity-${index}" name="quantity" type="number" required>
    </div>
    <div class="field">
      <label for="unit-price-${index}">Unit price in cents</label>
      <input id="unit-price-${index}" name="unit_price_cents" type="number" required>
    </div>
    <div class="field">
      <label for="line-total-${index}">Stated line total in cents</label>
      <input id="line-total-${index}" name="stated_line_total_cents" type="number" required>
    </div>
    <button type="button" class="remove-line-item">Remove line item</button>
  `;

  if (values) {
    item.querySelector('[name="item_code"]').value = values.item_code;
    item.querySelector('[name="description"]').value = values.description;
    item.querySelector('[name="quantity"]').value = values.quantity;
    item.querySelector('[name="unit_price_cents"]').value =
      values.unit_price_cents;
    item.querySelector('[name="stated_line_total_cents"]').value =
      values.stated_line_total_cents;
  }

  lineItemsContainer.appendChild(item);
}

function fillSampleInvoice() {
  document.getElementById("invoice-number").value = SAMPLE_INVOICE.invoice_number;
  document.getElementById("vendor-name").value = SAMPLE_INVOICE.vendor_name;
  document.getElementById("po-reference").value = SAMPLE_INVOICE.po_reference;
  document.getElementById("currency").value = SAMPLE_INVOICE.currency;
  document.getElementById("stated-total-cents").value =
    SAMPLE_INVOICE.stated_total_cents;
  lineItemsContainer.innerHTML = "";
  SAMPLE_INVOICE.line_items.forEach(createLineItem);
}

function collectInvoice() {
  const lineItems = [];
  lineItemsContainer.querySelectorAll("[data-line-item]").forEach(function (item) {
    lineItems.push({
      item_code: item.querySelector('[name="item_code"]').value,
      description: item.querySelector('[name="description"]').value,
      quantity: Number(item.querySelector('[name="quantity"]').value),
      unit_price_cents: Number(
        item.querySelector('[name="unit_price_cents"]').value
      ),
      stated_line_total_cents: Number(
        item.querySelector('[name="stated_line_total_cents"]').value
      ),
    });
  });

  return {
    invoice_number: document.getElementById("invoice-number").value,
    vendor_name: document.getElementById("vendor-name").value,
    po_reference: document.getElementById("po-reference").value,
    currency: document.getElementById("currency").value,
    stated_total_cents: Number(
      document.getElementById("stated-total-cents").value
    ),
    line_items: lineItems,
  };
}

function setStatusMessage(element, text, kind) {
  element.textContent = text;
  element.classList.remove("status-success", "status-warning", "status-error");
  if (kind) {
    element.classList.add("status-" + kind);
  }
}

function displayValue(value) {
  if (value === null || value === undefined || value === "") {
    return "None";
  }
  return String(value);
}

function renderIssues(issues) {
  const list = document.getElementById("result-issues");
  list.innerHTML = "";
  if (!Array.isArray(issues) || issues.length === 0) {
    return;
  }
  issues.forEach(function (issue) {
    const item = document.createElement("li");
    item.textContent = JSON.stringify(issue);
    list.appendChild(item);
  });
}

function statusKind(httpStatus) {
  if (httpStatus === 200) {
    return "success";
  }
  if (httpStatus === 409) {
    return "warning";
  }
  return "error";
}

function showResult(httpStatus, body) {
  const processing = body.processing_result || {};
  const message = document.getElementById("result-message");
  const summary = document.getElementById("result-summary");

  summary.hidden = false;
  document.getElementById("result-http-status").textContent = String(httpStatus);
  document.getElementById("result-status").textContent = displayValue(
    body.status || processing.status
  );
  document.getElementById("result-ingestion-id").textContent = displayValue(
    body.ingestion_id
  );
  document.getElementById("result-processing-id").textContent = displayValue(
    body.processing_result_id || processing.id
  );
  document.getElementById("result-vendor-id").textContent = displayValue(
    processing.vendor_id
  );
  document.getElementById("result-po-id").textContent = displayValue(
    processing.purchase_order_id
  );
  renderIssues(processing.issues || []);
  document.getElementById("result-json").textContent = JSON.stringify(
    body,
    null,
    2
  );

  let messageText = "Invoice submitted.";
  if (httpStatus === 409) {
    messageText = body.detail || "This invoice content has already been ingested.";
  } else if (httpStatus === 422) {
    messageText = "The invoice could not be submitted because some fields are invalid.";
  } else if (httpStatus >= 400) {
    messageText = body.detail || "The request failed.";
  }
  setStatusMessage(message, messageText, statusKind(httpStatus));
}

form.addEventListener("submit", async function (event) {
  event.preventDefault();
  submitButton.disabled = true;
  setStatusMessage(
    document.getElementById("result-message"),
    "Submitting invoice...",
    null
  );

  try {
    const response = await fetch("/invoices", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(collectInvoice()),
    });
    const body = await response.json();
    showResult(response.status, body);
  } catch (error) {
    document.getElementById("result-summary").hidden = true;
    document.getElementById("result-issues").innerHTML = "";
    document.getElementById("result-json").textContent = "";
    setStatusMessage(
      document.getElementById("result-message"),
      "The API is unavailable. Start the local server and try again.",
      "error"
    );
  } finally {
    submitButton.disabled = false;
  }
});

lookupForm.addEventListener("submit", async function (event) {
  event.preventDefault();
  const lookupId = document.getElementById("lookup-id").value;
  const message = document.getElementById("lookup-message");
  const jsonBox = document.getElementById("lookup-json");
  jsonBox.textContent = "";

  try {
    const response = await fetch("/processing-results/" + encodeURIComponent(lookupId));
    const body = await response.json();

    if (response.status === 404) {
      setStatusMessage(
        message,
        body.detail || "Processing result not found.",
        "error"
      );
      return;
    }

    if (!response.ok) {
      setStatusMessage(
        message,
        body.detail || "The lookup request failed.",
        "error"
      );
      jsonBox.textContent = JSON.stringify(body, null, 2);
      return;
    }

    setStatusMessage(message, "Processing result found.", "success");
    jsonBox.textContent = JSON.stringify(body, null, 2);
  } catch (error) {
    setStatusMessage(
      message,
      "The API is unavailable. Start the local server and try again.",
      "error"
    );
  }
});

lineItemsContainer.addEventListener("click", function (event) {
  const removeButton = event.target.closest(".remove-line-item");
  if (!removeButton) {
    return;
  }
  const item = removeButton.closest("[data-line-item]");
  const remaining = lineItemsContainer.querySelectorAll("[data-line-item]");
  if (item && remaining.length > 1) {
    item.remove();
  }
});

addLineItemButton.addEventListener("click", function () {
  createLineItem();
});

loadSampleButton.addEventListener("click", fillSampleInvoice);
