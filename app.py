"""AI Sales Copilot - Streamlit app.

Run:  streamlit run app.py
"""

import os

import pandas as pd
import streamlit as st

import agent

st.set_page_config(page_title="AI Sales Copilot", page_icon="🎯", layout="wide")

# Demo presets: what you sell, who you sell to, and a matching sample lead list.
# Sample leads are fictional companies so no real person's data is used.
PRESETS = {
    "Sales intelligence (6sense-style)": {
        "offering": (
            "An AI revenue platform that uses buying-intent data to show sales and marketing teams "
            "which accounts are in-market right now, and helps reps reach the right buyers first."
        ),
        "icp": (
            "B2B SaaS companies with 50-1,000 employees in North America that are growing their "
            "sales team (hiring SDRs/AEs), recently raised funding, or launched a new product."
        ),
        "sample": "sample_leads.csv",
    },
    "AI data analytics (Hex-style)": {
        "offering": (
            "An AI-powered analytics platform where data teams and business users explore data with "
            "SQL, Python or plain English, and share trusted analyses and apps across the company."
        ),
        "icp": (
            "Mid-market and enterprise companies (200-5,000 employees) with a modern data stack "
            "(Snowflake, BigQuery, Databricks or dbt), a growing data/analytics team, and business "
            "teams waiting on analysts for answers. Strong signals: hiring data roles, new data "
            "leadership, or rolling out AI initiatives."
        ),
        "sample": "sample_leads_data.csv",
    },
}

# ---------- sidebar: setup ----------
with st.sidebar:
    st.header("Setup")
    # The key is never pre-filled or sent back to the browser, and it is used only for this session.
    user_key = st.text_input("Anthropic API key (optional)", type="password")
    api_key = user_key or os.getenv("ANTHROPIC_API_KEY")  # env var only for local runs
    st.caption("Live AI mode" if api_key else "No key: running in mock mode so you can still demo the flow.")
    preset_name = st.selectbox("Demo scenario", list(PRESETS))
    preset = PRESETS[preset_name]
    sender = st.text_input("Your name", value="Jade")
    offering = st.text_area("What you sell", value=preset["offering"], height=120, key=f"off_{preset_name}")
    icp = st.text_area("Ideal customer profile (ICP)", value=preset["icp"], height=150, key=f"icp_{preset_name}")
    use_web = st.checkbox("Agent reads each company's website", value=True)

st.title("🎯 AI Sales Copilot")
st.write("Upload leads → the agent researches, scores and drafts → **you approve** before anything is sent.")

# ---------- step 0: load leads ----------
uploaded = st.file_uploader("Leads CSV (columns: company, name, title, website, notes)", type="csv")
if uploaded is not None:
    leads_df = pd.read_csv(uploaded).fillna("")
elif st.button("Use sample leads"):
    leads_df = pd.read_csv(os.path.join(os.path.dirname(__file__), preset["sample"])).fillna("")
    st.session_state.pop("results", None)
else:
    leads_df = st.session_state.get("leads_df")

if leads_df is None:
    st.info("Upload a CSV or click **Use sample leads** to start.")
    st.stop()
st.session_state["leads_df"] = leads_df

# ---------- step 1-3: run the agent ----------
if st.button(f"Run agent on {len(leads_df)} leads", type="primary"):
    results = []
    progress = st.progress(0.0, text="Starting…")
    for i, lead in enumerate(leads_df.to_dict("records")):
        progress.progress(i / len(leads_df), text=f"Researching {lead.get('company')}…")
        try:
            out = agent.run_agent(lead, icp, offering, sender, use_web=use_web, api_key=api_key)
        except Exception as exc:  # keep going if one lead fails
            out = {"score": 0, "reason": f"Error: {exc}", "why_now": "", "pain_point": "",
                   "confidence": "low", "subject": "", "email": "", "call_opener": "",
                   "research": "", "status": "Error"}
        results.append({**lead, **out})
    progress.progress(1.0, text="Done")
    st.session_state["results"] = sorted(results, key=lambda r: r.get("score", 0), reverse=True)

results = st.session_state.get("results")
if not results:
    st.stop()

# ---------- activity summary ----------
statuses = [r["status"] for r in results]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Leads processed", len(results))
c2.metric("Approved", statuses.count("Approved"))
c3.metric("Skipped", statuses.count("Skipped"))
c4.metric("Avg fit score", round(sum(r.get("score", 0) for r in results) / len(results)))

# ---------- prioritized list ----------
st.subheader("Prioritized leads")
table = pd.DataFrame(results)[["score", "company", "name", "title", "why_now", "confidence", "status"]]
st.dataframe(table, width="stretch", hide_index=True)

# ---------- review queue (human in the loop) ----------
st.subheader("Review drafts")
for i, r in enumerate(results):
    label = f"{r.get('score', 0)} · {r.get('company')} · {r.get('name')} ({r.get('title')}) — {r['status']}"
    with st.expander(label, expanded=(i == 0 and r["status"] == "Needs review")):
        st.markdown(f"**Why this score:** {r.get('reason', '')}")
        st.markdown(f"**Why now:** {r.get('why_now', '')}  ·  **Likely pain:** {r.get('pain_point', '')}")
        r["subject"] = st.text_input("Subject", value=r.get("subject", ""), key=f"subj{i}")
        r["email"] = st.text_area("Email (edit before approving)", value=r.get("email", ""), height=170, key=f"email{i}")
        r["call_opener"] = st.text_area("Call opener", value=r.get("call_opener", ""), height=100, key=f"call{i}")
        a, s, _ = st.columns([1, 1, 4])
        if a.button("✅ Approve", key=f"ok{i}"):
            r["status"] = "Approved"
            st.rerun()
        if s.button("⏭ Skip", key=f"skip{i}"):
            r["status"] = "Skipped"
            st.rerun()
        if r.get("research"):
            with st.popover("What the agent read"):
                st.write(r["research"][:1500])

# ---------- export ----------
export_cols = ["company", "name", "title", "website", "score", "why_now", "pain_point",
               "subject", "email", "call_opener", "status"]
export = pd.DataFrame(results)[[c for c in export_cols if c in results[0]]]
st.download_button("Download results (CSV)", export.to_csv(index=False).encode("utf-8"),
                   file_name="copilot_results.csv", mime="text/csv")
