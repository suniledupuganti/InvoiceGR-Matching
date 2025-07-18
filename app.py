import json
import random
import streamlit as st
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_openai import ChatOpenAI

st.set_page_config(page_title="Invoice → PO → GR Matcher", layout="wide")
st.title("📦 Invoice → PO → GR Line Matching App")

left_col, right_col = st.columns([1, 1])

# ---------- Data Generation Functions ----------

def generate_random_line(line_type):
    desc = random.choice([
        "Asphalt Mix - PG 64-22",
        "Ready Mix Concrete, 4,000 psi",
        "Epoxy-Coated Rebar, #6, 20ft",
        "LED Streetlight Fixture 150W",
        "Galvanized Steel Guardrail 12.5 ft"
    ])
    qty = random.randint(50, 150)
    price = random.randint(40, 120)
    uom = random.choice(["TON", "YRD", "EA", "FT"])

    if line_type == "INV":
        return {
            "invLineId": f"INV{random.randint(1000, 9999)}",
            "Description": desc,
            "Quantity": qty,
            "UOM": uom,
            "UnitPrice": price,
            "Amount": qty * price
        }

    elif line_type == "PO":
        return {
            "Position": f"{random.randint(1, 99)}",
            "PONumber": f"PO{random.randint(1000, 9999)}",
            "Po Description": desc,
            "PO Qty": qty,
            "PO UOM": uom,
            "PO Unit Price": price,
            "PO Line Amount": qty * price
        }

    elif line_type == "GR":
        return {
            "GR_ITEM_NO": f"GR{random.randint(1000, 9999)}",
            "GR_ITEM_DES": desc,
            "GR_QTY": random.randint(10, qty),
            "IS_CONSUMED": random.choice([True, False]),
            "PONumber": f"PO{random.randint(1000, 9999)}",
            "PO_LINE_NO": f"{random.randint(1, 10) * 10}"
        }

    return {}

def generate_random_data(lines=3):
    inv = [generate_random_line("INV") for _ in range(lines)]
    po = [generate_random_line("PO") for _ in range(lines)]
    gr = [generate_random_line("GR") for _ in range(lines * 2)]
    return json.dumps(inv, indent=4), json.dumps(po, indent=4), json.dumps(gr, indent=4)

# ---------- LEFT COLUMN (Inputs) ----------
with left_col:
    st.header("1️⃣ Input Data")

    if st.button("🔄 Generate Random Data"):
        inv, po, gr = generate_random_data()
        st.session_state.invoice_data = inv
        st.session_state.po_data = po
        st.session_state.gr_data = gr

    invoice_data = st.text_area("📑 Invoice Lines (JSON Array)", value=st.session_state.get("invoice_data", ""), height=180)
    po_data = st.text_area("📄 PO Lines (JSON Array)", value=st.session_state.get("po_data", ""), height=180)
    gr_data = st.text_area("🚛 GR Lines (JSON Array)", value=st.session_state.get("gr_data", ""), height=180)

    st.subheader("2️⃣ OpenAI API Key")
    openai_key = st.text_input("🔐 OpenAI API Key", type="password")

    run_button = st.button("🚀 Run Matching")

# ---------- RIGHT COLUMN (Prompt + Result) ----------
with right_col:
    st.header("3️⃣ Prompt Configuration")

    template_prompt = """
    **Role**

You are a procurement reconciliation assistant specializing in 3-way matching between:
- Invoice Lines
- Purchase Order (PO) Lines
- Goods Receipt (GR) Lines

Your role is to automate invoice verification and ensure consistency between what was ordered (PO), what was received (GR), and what was invoiced (Invoice Line).

---

**Meta Prompt**

You will:
1. Match an Invoice Line to one PO Line.
2. If matched, match that Invoice Line to one or more GR Lines linked to the same PO Line, using only unconsumed GR entries.

Output only valid JSON as described below. Do not return explanations, summaries, or plain text. Follow the matching rules precisely.

---

**Context Details**

### Input Objects

1. **Invoice Lines**
   - `invLineId: string`
   - `Description: string`
   - `Quantity: number`
   - `UOM: string`
   - `UnitPrice: number`
   - `Amount: number`

2. **PO Lines**
   - `Position: string`
   - `PONumber: string`
   - `Po Description: string`
   - `PO Qty: number`
   - `PO UOM: string`
   - `PO Unit Price: number`
   - `PO Line Amount: number`

3. **GR Lines**
   - `GR_ITEM_NO: string`
   - `GR_ITEM_DES: string`
   - `GR_QTY: number`
   - `IS_CONSUMED: boolean`
   - `PONumber: string`
   - `PO_LINE_NO: string`

---

**Matching Rules**

### Step 1: Invoice → PO Matching

Match an invoice line to a PO line based on the following criteria:

- `Description` ≈ `Po Description` using semantic or fuzzy match.
- `UOM` must match exactly.
- `UnitPrice` must be within ±5% of the `PO Unit Price`.
- `Amount` (computed as `Quantity × UnitPrice`) must be within ±5% of `PO Line Amount`.

 If all conditions result in a valid match:
- `"poMatchType": "Matched"`
- Include the full PO line fields under `"matchedPO"`.

 If no PO line matches:
- `"poMatchType": "Unmatched"`
- Leave `"matchedPO": {}` empty
- Include `"poMatchFailureReason"` (e.g., "No PO found with matching UOM or price")

---

### Step 2: Invoice → GR Matching

Only perform if `poMatchType === "Matched"`.

From the GR lines:
- Only include entries where `IS_CONSUMED == false`.
- Only select GR lines where both `PONumber` and `PO_LINE_NO` match the PO.
- `GR_ITEM_DES` ≈ `Description` from the Invoice.

Then:
- If a single GR line fully covers the invoice quantity:  
  `"grMatchType": "Exact"`
- If multiple GR lines together exactly fulfill the quantity:  
  `"grMatchType": "Consolidated"` (include all components in `"matchedGRs"`)
- If no combination of GR lines satisfies the match logic:  
  `"grMatchType": "Unmatched"` and include `"grMatchFailureReason"`

---

**Response Format Details**

Respond with a single root JSON object shaped like this:
{
"matches": [
{
"invLineId": "string",
"poMatchType": "Matched" | "Unmatched",
"matchedPO": {
"Position": "string",
"PONumber": "string",
"Po Description": "string",
"PO Qty": number,
"PO UOM": "string",
"PO Unit Price": number,
"PO Line Amount": number
},
"poMatchFailureReason": "string (only present if Unmatched)",
  "grMatchType": "Exact" | "Consolidated" | "Unmatched",
  "matchedGRs": [
    {
      "GR_ITEM_NO": "string",
      "GR_ITEM_DES": "string",
      "GR_QTY": number,
      "PONumber": "string",
      "PO_LINE_NO": "string"
    }
  ],
  "grMatchFailureReason": "string (only present if Unmatched)"
}
]
}

- Do not return explanations or messages outside this JSON structure.
- Do not include unnecessary whitespace, comments, or metadata.
- All fields must use correct casing and types.

---

**User Prompt**
invoice_lines = {invoice_lines}
po_lines = {po_lines}
gr_lines = {gr_lines}

Apply the matching logic and return only the structured JSON response.


"""

    editable_prompt = st.text_area("✏️ Prompt (Edit if needed)", value=template_prompt, height=600)

    st.divider()
    st.header("📊 Matching Results")

    if run_button:
        if not openai_key or not openai_key.startswith("sk-"):
            st.error("Please provide a valid OpenAI key (starts with 'sk-').")
            st.stop()

        try:
            invoice_lines = json.loads(invoice_data)
            po_lines = json.loads(po_data)
            gr_lines = json.loads(gr_data)
        except json.JSONDecodeError:
            st.error("❌ One or more inputs are not valid JSON arrays.")
            st.stop()

        # Inject arrays into prompt placeholders
        final_prompt = editable_prompt \
            .replace("{invoice_lines}", json.dumps(invoice_lines, indent=4)) \
            .replace("{po_lines}", json.dumps(po_lines, indent=4)) \
            .replace("{gr_lines}", json.dumps(gr_lines, indent=4))

        try:
            with st.spinner("🔄 Matching in progress..."):
                llm = ChatOpenAI(model="gpt-4", temperature=0, api_key=openai_key)
                response = llm.invoke([
                    SystemMessage(content="Return only valid JSON, no explanations."),
                    HumanMessage(content=final_prompt)
                ])

            try:
                parsed = json.loads(response.content)
                st.success("✅ Matching complete!")
                st.json(parsed)
            except json.JSONDecodeError:
                st.error("⚠️ Invalid JSON in LLM response")
                st.code(response.content)

        except Exception as e:
            st.error(f"❌ LLM call failed: {str(e)}")
    else:
        st.info("👈 Enter/generate data & hit 'Run Matching'")
