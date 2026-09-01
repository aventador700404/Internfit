from __future__ import annotations

from pathlib import Path
from tempfile import NamedTemporaryFile

import streamlit as st

from core.cv_parser import parse_cv
from core.job_parser import fetch_job_posting, job_from_text
from core.sample_jobs import SAMPLE_JOBS
from core.scoring import assess_fit


st.set_page_config(page_title="InternFit", page_icon="🎯", layout="wide")
st.title("InternFit")
st.caption("Upload one CV. Paste a job link. Get an evidence-based application priority.")

if "candidate" not in st.session_state:
    st.session_state.candidate = None

with st.sidebar:
    st.header("1. Candidate profile")
    uploaded_cv = st.file_uploader("Upload CV (.docx)", type=["docx"])
    if uploaded_cv and st.button("Read CV", use_container_width=True):
        with NamedTemporaryFile(suffix=".docx", delete=False) as temp_file:
            temp_file.write(uploaded_cv.getvalue())
            temp_path = Path(temp_file.name)
        st.session_state.candidate = parse_cv(temp_path)
        temp_path.unlink(missing_ok=True)
        st.success("CV parsed. This session keeps your candidate profile.")

    if st.session_state.candidate:
        candidate = st.session_state.candidate
        st.write("**Detected strengths**")
        st.write(", ".join(sorted(candidate.evidence_tags)))
        st.write("**Languages**")
        st.write(", ".join(sorted(candidate.languages)))

st.header("2. Job posting")
job_url = st.text_input("Paste a public job-posting URL")
sample_label = st.selectbox("Or test with a verified sample posting", ["None", *SAMPLE_JOBS.keys()])

with st.expander("Fallback when a site blocks automatic reading"):
    fallback_title = st.text_input("Role title", key="fallback_title")
    fallback_company = st.text_input("Company", key="fallback_company")
    fallback_text = st.text_area("Paste job description", height=180, key="fallback_text")

analyze = st.button("Analyze fit", type="primary", use_container_width=True)
if analyze:
    if not st.session_state.candidate:
        st.error("Upload a .docx CV first.")
        st.stop()

    if sample_label != "None":
        job = SAMPLE_JOBS[sample_label]
    elif job_url:
        with st.spinner("Reading the job page..."):
            job = fetch_job_posting(job_url)
        if job.source_status != "ok":
            st.warning("This page blocked automatic reading. Use the fallback field below.")
            st.stop()
    elif fallback_text:
        job = job_from_text(fallback_title, fallback_company, fallback_text)
    else:
        st.error("Paste a URL, pick a sample posting, or use the fallback text field.")
        st.stop()

    result = assess_fit(st.session_state.candidate, job)
    st.divider()
    st.subheader(job.title)
    col1, col2, col3 = st.columns(3)
    col1.metric("Fit score", f"{result.score}/100", result.grade)
    col2.metric("Recommendation", result.recommendation)
    col3.metric("Eligibility", result.eligibility)

    st.subheader("Score breakdown")
    st.bar_chart(result.breakdown)

    left, right = st.columns(2)
    with left:
        st.subheader("Matched strengths")
        st.write(result.strengths or "No strong evidence match found yet.")
        st.subheader("CV evidence used")
        for line in (result.match_explanations or result.evidence):
            st.write(f"- {line}")
    with right:
        st.subheader("Gaps to address")
        st.write(result.gap_details or result.gaps or "No material gap detected.")
        if result.blockers:
            st.subheader("Eligibility blockers")
            for blocker in result.blockers:
                st.error(blocker)
