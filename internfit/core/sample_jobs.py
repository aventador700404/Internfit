from __future__ import annotations

from .job_parser import JobPosting


SAMPLE_JOBS = {
    "SAP — Strategy & Operations Intern (high-fit expected)": JobPosting(
        title="Strategy & Operations Intern, SAP Labs East Asia Korea",
        company="SAP",
        url="https://jobs.sap.com/job/Seoul-Strategy-%26-Operations-Intern%2C-SAP-Labs-East-Asia-Korea-06578/1427409933/",
        text=(
            "Support location strategy and operations through planning, execution, process documentation, workflow improvement and follow-up actions. "
            "Coordinate ecosystem events, workshops, training and executive visits. Own topics end-to-end: logistics, communications and post-event reports. "
            "Requirements: third- or final-year Business Administration or related student with roughly 6-12 months to graduation. "
            "Strong organization, analysis and English communication. Excel, PowerPoint and AI collaboration tools. "
            "Interest in technology and experience in event coordination or student organizations is preferred."
        ),
        requirements={
            "responsibility_tags": {"strategy", "operations", "event_management", "stakeholder"},
            "domain_tags": {"technology", "operations"},
            "core_checks": {"business_degree", "english", "student"},
            "required_tools": {"excel", "powerpoint", "ai_tools"},
            "required_languages": {"english"},
        },
    ),
    "ING — Debt Capital Markets Intern (mid-fit expected)": JobPosting(
        title="(Securities) Debt Capital Markets Intern 2026 2H",
        company="ING",
        url="https://careers.ing.com/en/job_location/seoul/securities-debt-capital-markets-%C4%B1ntern-2026-2h/3121/40421619904/18174",
        text=(
            "Support origination and execution of Debt Capital Markets products and communicate with relevant desks and stakeholders. "
            "Monitor financial markets, conduct quantitative market-data analysis and prepare pitch marketing materials. "
            "The role requires interest in public-bond deal execution, financial markets, numerical analysis, attention to detail and professional communication."
        ),
        requirements={
            "responsibility_tags": {"capital_markets", "market_monitoring", "data_analysis", "stakeholder", "pitch_materials"},
            "domain_tags": {"finance", "capital_markets"},
            "core_checks": {"business_degree", "english", "capital_markets_knowledge"},
            "required_tools": {"excel", "powerpoint"},
            "required_languages": {"english"},
        },
    ),
    "RLWRLD — AI & Robotics Strategy Intern, Japanese (eligibility fail expected)": JobPosting(
        title="AI & Robotics Research and Strategy Intern (Japanese)",
        company="RLWRLD",
        url="https://realworld.career.greetinghr.com/en/o/168017",
        text=(
            "Research domestic and global AI and robotics markets. Assist with business strategy and reports on AI, deep tech and startups. "
            "Support robot-learning data collection including 3D scanning, dataset analysis, sensor setup, data labeling and post-processing. "
            "Japanese language capability is required."
        ),
        requirements={
            "responsibility_tags": {"research", "strategy", "technology", "robotics_data"},
            "domain_tags": {"technology", "robotics_data"},
            "core_checks": {"english", "japanese"},
            "required_tools": {"data_analysis"},
            "required_languages": {"japanese"},
        },
    ),
}
