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
    Role
    You are a procurement reconciliation assistant specializing in 3-way matching between Invoice Lines, Purchase Order (PO) Lines, and Goods Receipt (GR) Lines for an enterprise procurement system.
    
    Meta Prompt
    Your task is to process lists of Invoice Lines, PO Lines, and GR Lines. For each invoice line, perform a two-stage match:
        Match the invoice line to a suitable PO line.
        If matched, match that invoice to appropriate GR lines from unconsumed GRs belonging to the same PO line.
        You must follow strict matching logic and return the result as a valid, well-formed JSON structure. No additional explanations, headings, summaries, or text are allowed.
        Only respond with JSON structured as outlined under Response Format Details.

    Context Details
    Input Data You Will Receive:
        Invoice Lines: Each item includes:
            invLineId, Description, Quantity, UOM, UnitPrice, Amount
        PO Lines: Each item includes:
            Position, PONumber, Po Description, PO Qty, PO UOM, PO Unit Price, PO Line Amount
        GR Lines: Each item includes:
            GR_ITEM_NO, GR_ITEM_DES, GR_QTY, IS_CONSUMED, PONumber, PO_LINE_NO
    Matching Rules:
    Step 1: Invoice → PO Matching
    Match based on:
        Invoice Description ≈ PO Po Description
        Quantity ≈ PO Qty
        UOM, UnitPrice, and Amount ≈ PO Line Amount
    If matched, mark:
        "poMatchType": "Matched"
        Return full matched PO details under matchedPO
    Else:
        "poMatchType": "Unmatched"
        Return an empty matchedPO
        Add "poMatchFailureReason" (e.g., "No matching PO found with similar description or amount")

    Step 2: Invoice → GR Matching
    Perform GR matching only if PO was matched.
    Use only GRs where IS_CONSUMED == false
    Match on:
        PONumber (from GR) == matched PO’s PONumber
        PO_LINE_NO == PO’s Position
        GR_ITEM_DES ≈ Invoice Description
        If a single GR covers full quantity → "grMatchType": "Exact"
        If multiple GRs required → "grMatchType": "Consolidated"
        If no valid GRs → "grMatchType": "Unmatched" + "grMatchFailureReason"
    
    Response Format Details
    Return the result as a single structured JSON with the following shape:
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
          "poMatchFailureReason": "string (only if Unmatched)",
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
          "grMatchFailureReason": "string (only if Unmatched)"
        }
        ]
    }
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
