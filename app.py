import json
import streamlit as st
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

st.set_page_config(page_title="Invoice-GR Matcher", layout="wide")
st.title("🏗️ Invoice-GR Matching POC (LangChain + GPT)")

# --- LAYOUT: Left (inputs) and Right (output) columns ---
left_col, right_col = st.columns([1.2, 1.5])

# === LEFT COLUMN (Inputs) ===
with left_col:
    st.header("1️⃣ Input Data")

    invoice_example = """[
    {"invLineId": "INV1", "poItem": "PO123", "qty": 100},
    {"invLineId": "INV2", "poItem": "PO456", "qty": 50},
    {"invLineId": "INV3", "poItem": "PO123", "qty": 150}
    ]"""

    invoice_data = st.text_area("🧾 Invoice Lines (JSON)", value=invoice_example, height=160)

    gr_example = """[
    {"grNo": "GR001", "grItemNo": "10", "poItem": "PO123", "qty": 100},
    {"grNo": "GR002", "grItemNo": "11", "poItem": "PO123", "qty": 50},
    {"grNo": "GR003", "grItemNo": "12", "poItem": "PO789", "qty": 75}
    ]"""

    gr_data = st.text_area("🚛 GR Lines (JSON)", value=gr_example, height=160)

    st.subheader("2️⃣ API Configuration")
    openai_key = st.text_input("🔑 OpenAI API Key", type="password")

    run_button = st.button("🚀 Match Invoice to GR")

# === RIGHT COLUMN (Output) ===
with right_col:
    st.header("📊 Matching Output")

    # If run button is clicked
    if run_button:
        # Validate OpenAI key
        if not openai_key or not openai_key.startswith("sk-"):
            st.error("Please enter a valid OpenAI API key (starts with sk-).")
            st.stop()

        # Parse inputs
        try:
            invoice_lines = json.loads(invoice_data)
            gr_lines = json.loads(gr_data)
        except json.JSONDecodeError:
            st.error("⚠️ One of the input fields contains invalid JSON.")
            st.stop()

        # Meta Prompt
        meta_prompt = f"""
Your sole task is to match each invoice line item to the correct open Goods Receipt (GR) line(s), based on PO item and quantity logic. Return results in strictly-formatted JSON. No explanations, headings, or extra keys outside the JSON schema.

Domain Primer (Procure-to-Pay Context):
Invoice Line: A line item from a vendor’s invoice, referencing a PO item and quantity being billed.
GR Line (Goods Receipt): A line confirming the quantity of goods received for a specific PO item.
PO Item (poItem): The identifier linking invoices and GRs to the same purchase order line.

You are matching invoice lines to GR lines where items were received, ensuring quantities align. This logic is used in invoice reconciliation workflows.

Context Details:
You will be provided:
An array of invoice lines with: invLineId, poItem, and qty
An array of GR lines with: grNo, grItemNo, poItem, and qty

You will process each invoice line using the matching rules below.

Matching Rules (Apply in This Order):
1. PO Item Filter
Only consider GR lines where gr.poItem == invoice.poItem.

2. Exact Match
If exactly one eligible GR has qty <= invoice.qty, and no others fit better, select it.
Return matchType: "Exact" and one GR in matchedGRs.

3. Consolidated Match
If no exact match found, try combining two or more eligible GRs whose total qty == invoice.qty.
Return matchType: "Consolidated" and all matched GRs in matchedGRs.

4. Unmatched
If no GRs qualify using rules 2 or 3:
Return matchType: "Unmatched"
Return matchedGRs: []
Include a one-line matchFailureReason explaining why matching failed (e.g., “No GRs with matching PO item”, “Sum of GR quantities doesn't equal invoice quantity”).

Response Format (Strict JSON Only):
{{
"matches": [
{{
"invLineId": "string",
"poItem": "string",
"matchType": "Exact" | "Consolidated" | "Unmatched",
"matchedGRs": [
{{"grNo": "string", "grItemNo": "string", "qty": number}}
],
"matchFailureReason": "string (only present if matchType == 'Unmatched')"
]
}}

Return JSON only.

invoice_lines = {json.dumps(invoice_lines, indent=4)}
gr_lines = {json.dumps(gr_lines, indent=4)}
"""

        # LLM Call using LangChain + OpenAI
        try:
            llm = ChatOpenAI(api_key=openai_key, model="gpt-4", temperature=0)
            messages = [
                SystemMessage(content="You are a helpful assistant that only returns valid JSON."),
                HumanMessage(content=meta_prompt)
            ]
            llm_response = llm.invoke(messages)

            # Try to parse LLM JSON response
            try:
                data = json.loads(llm_response.content)
                st.json(data)
            except json.JSONDecodeError:
                st.warning("⚠ Could not parse LLM output as JSON. Check formatting.")
                st.code(llm_response.content)

        except Exception as e:
            st.error(f"❌ Error: {str(e)}")

    else:
        st.info("👈 Fill in the data and click 'Run Matching' to begin.")