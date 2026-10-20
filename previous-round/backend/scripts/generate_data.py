"""Generate the fictional company used by the demo (backend/data/company.json).

All people and evidence are made up. The script is deterministic, so rerunning it
gives the same file. Hand-written patterns (Sarah, Tom, the opt-out, the knowledge
gap) are defined explicitly; the rest of the company is filled in with a seeded RNG.
"""

import json
import random
from datetime import date, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
REF = date(2026, 9, 30)  # hackathon day; dates are relative to this
rng = random.Random(42)

TOPICS = {t["id"]: t for t in json.loads((DATA_DIR / "topics.json").read_text(encoding="utf-8"))}

TEMPLATES = {
    "year_end_bonus_pc200": ["Year-end bonus pro rata for mid-year leaver", "Year-end bonus for part-time employee calculated", "Client question: year-end bonus after long-term sickness", "Checked year-end bonus reference period for PC 200 client"],
    "salary_indexation_pc200": ["January indexation PC 200 applied for client portfolio", "Question on indexation of fixed allowances", "Indexation correction after late wage scale update"],
    "part_time_work": ["Part-time schedule change mid-month", "Part-time worker minimum hours check", "Converted full-time contract to 4/5 part-time"],
    "notice_period_nl": ["Notice period for Dutch employee with 12-year tenure", "Client asked about opzegtermijn in collective agreement (NL)", "Checked notice period during probation, Netherlands"],
    "notice_period_be": ["Notice period calculation under the unified status (BE)", "Counter-notice question from Belgian employee", "Notice period for employee with seniority before 2014"],
    "company_car_bik": ["Benefit in kind company car recalculated with new CO2 value", "Company car policy question for hybrid vehicle", "Own contribution company car deducted from BIK"],
    "meal_vouchers": ["Meal voucher count wrong after sick days", "Eco vouchers pro rata for new hire", "Meal voucher employer contribution raise"],
    "telework_allowance": ["Home office allowance for structural teleworker", "Telework agreement template updated", "Telework allowance combined with internet allowance"],
    "cross_border_lux": ["Cross-border worker Luxembourg: 34-day tax threshold", "Frontalier social security question (LU/BE)"],
    "germany_payroll": ["German social security registration for new entity", "Lohnsteuer class change mid-year", "German payroll go-live checklist"],
    "france_payroll": ["DSN rejection resolved for French client", "Monthly DSN declaration checklist", "French payslip layout question"],
    "gdpr_employee_data": ["Retention period for payroll records", "Data subject access request from former employee", "GDPR review of HR export"],
    "sick_leave_be": ["Guaranteed salary after relapse within 14 days", "Medical certificate received late: impact on pay", "Sick leave during annual holiday"],
    "parental_leave": ["Parental leave 1/10 reduction set up", "Birth leave days for co-parent", "Maternity leave extension after hospitalisation"],
    "holiday_pay_be": ["Double holiday pay for leaver", "Holiday pay for white-collar worker changing employer", "Holiday pay calculation after part-time switch"],
    "overtime": ["Voluntary overtime hours limit check", "Overtime premium on Sunday work", "Overtime recuperation question"],
    "flexi_jobs": ["Flexi-job eligibility check for retiree", "Flexi-job wage minimum update", "Flexi-job contract in hospitality client"],
    "student_workers": ["Student worker 475 hours counter", "Student contract during summer holidays", "Student worker social contribution rate"],
    "payroll_close": ["Payslip correction after payroll close", "Monthly payroll cut-off moved for holiday", "Payroll run failed validation, fixed"],
    "expat_taxation": ["Inbound taxpayer regime application", "Expat cost allowance reimbursement", "Special tax regime eligibility check"],
    "pension_plans": ["Group insurance contribution on variable pay", "Supplementary pension entry for new hire", "Pension plan rules for part-timers"],
    "cafeteria_plan": ["Cafeteria plan budget for bike lease", "Flexible reward plan setup", "Cafeteria plan: converting holiday pay"],
    "dimona_onboarding": ["Dimona declaration for student", "New hire onboarding checklist update", "Dimona correction after start date change"],
    "time_credit": ["Time credit with motive: care for child", "Career break end-of-career (landingsbaan)", "Time credit application for 1/5"],
    "mobility_budget": ["Mobility budget: pillar 2 housing costs", "Employee switched company car to mobility budget", "Mobility budget cash-out at year end"],
    "bike_allowance": ["Bike allowance for speed pedelec", "Bike lease combined with bike allowance", "Bike allowance kilometre registration"],
    "ev_home_charging": ["Home charging reimbursement at quarterly kWh price", "Charging station at home installed via car policy", "EV charging logs missing for reimbursement"],
    "remote_work_abroad": ["A1 certificate for employee working from Spain", "Workation request: 3 weeks in Portugal", "Remote work abroad policy question"],
    "temporary_unemployment": ["Temporary unemployment notification for economic reasons", "Employer supplement during temporary unemployment", "Force majeure unemployment after flooding"],
    "holiday_entitlement_nl": ["Expiring statutory leave days (NL)", "Vakantiebijslag for part-timer", "Carry-over of extra-statutory leave (NL)"],
    "thirty_percent_ruling": ["30% ruling application for new hire from Spain", "30% ruling phase-down impact on net salary", "30% ruling salary threshold check"],
    "uk_payroll": ["UK starter checklist without P45", "PAYE RTI submission late", "National Insurance category question"],
    "social_elections": ["Protected employee status during social elections", "Social elections timeline 2028 planning", "Works council candidate list question"],
    "warrants_stock_options": ["Stock option grant accepted within 60 days", "RSU vesting taxed as salary", "Warrants bonus plan review"],
}
TYPES = ["ticket", "ticket", "ticket", "chat", "document"]

ROLES = ["Payroll consultant", "Senior payroll consultant", "HR advisor", "Legal expert", "Social security specialist", "Client service manager", "Payroll analyst", "Tax specialist"]


def day(days_ago: int) -> str:
    return (REF - timedelta(days=days_ago)).isoformat()


def ev(topic, text, days_ago, type_="ticket", vouched_by=(), author=False):
    item = {"type": type_, "topic": topic, "text": text, "date": day(days_ago), "vouched_by": list(vouched_by)}
    if author:
        item["author"] = True
    return item


# --- Hand-written patterns used in the demo ---------------------------------

people = [
    {"id": "emp_014", "name": "Sarah De Vos", "role": "Payroll consultant", "country": "BE", "opt_in": True, "hidden_topics": [],
     "evidence": [
         ev("year_end_bonus_pc200", "Year-end bonus for part-time employee calculated", 14, vouched_by=["emp_003", "emp_021"]),
         ev("year_end_bonus_pc200", "Year-end bonus pro rata for 4/5 part-timer", 21, vouched_by=["emp_007"]),
         ev("year_end_bonus_pc200", "Client question: year-end bonus after long-term sickness", 30),
         ev("year_end_bonus_pc200", "Checked year-end bonus reference period for PC 200 client", 38),
         ev("year_end_bonus_pc200", "Year-end bonus for mid-year leaver", 45, vouched_by=["emp_010"]),
         ev("year_end_bonus_pc200", "Explained year-end bonus rules to new team member", 52, "chat"),
         ev("year_end_bonus_pc200", "Year-end bonus for employee on time credit", 64),
         ev("year_end_bonus_pc200", "Year-end bonus: part-time schedule change mid-year", 80, vouched_by=["emp_003"]),
         ev("year_end_bonus_pc200", "Year-end bonus FAQ for PC 200 clients (2026 update)", 95, "document"),
         ev("year_end_bonus_pc200", "Year-end bonus correction after payroll close", 110),
         ev("year_end_bonus_pc200", "Year-end bonus: seniority condition check", 130),
         ev("year_end_bonus_pc200", "Year-end bonus for student converted to employee", 150),
         ev("part_time_work", "Part-time schedule change mid-month", 18),
         ev("part_time_work", "Converted full-time contract to 4/5 part-time", 60),
         ev("holiday_pay_be", "Holiday pay calculation after part-time switch", 70),
     ]},
    {"id": "emp_002", "name": "Tom Janssens", "role": "Senior payroll expert", "country": "BE", "opt_in": True, "hidden_topics": [],
     "evidence": [
         ev("year_end_bonus_pc200", "Wrote the original year-end bonus procedure for PC 200", 1340, "document", vouched_by=["emp_005"], author=True),
         ev("year_end_bonus_pc200", "Year-end bonus pro rata for mid-year leaver", 1200),
         ev("year_end_bonus_pc200", "Year-end bonus for part-time employee", 1100, vouched_by=["emp_011"]),
         ev("year_end_bonus_pc200", "Year-end bonus training for new consultants", 990, "document"),
         ev("year_end_bonus_pc200", "Year-end bonus reference period question", 900),
         ev("year_end_bonus_pc200", "Year-end bonus for long-term sickness", 850),
         ev("year_end_bonus_pc200", "Year-end bonus review of procedure", 932),
         ev("salary_indexation_pc200", "January indexation PC 200 applied for client portfolio", 640),
         ev("salary_indexation_pc200", "Indexation correction after late wage scale update", 700),
     ]},
    {"id": "emp_019", "name": "Lotte Maes", "role": "Payroll consultant", "country": "BE", "opt_in": False, "hidden_topics": [],
     "evidence": [  # opted out: must never be shown, even though she is an expert
         ev("year_end_bonus_pc200", "Year-end bonus for part-time employee", 5, vouched_by=["emp_003", "emp_007", "emp_010"]),
         ev("year_end_bonus_pc200", "Year-end bonus for mid-year leaver", 12),
         ev("year_end_bonus_pc200", "Year-end bonus: seniority condition check", 20),
         ev("part_time_work", "Part-time worker minimum hours check", 9),
     ]},
    {"id": "emp_008", "name": "Nina Peeters", "role": "Junior payroll consultant", "country": "BE", "opt_in": True, "hidden_topics": [],
     "evidence": [
         ev("year_end_bonus_pc200", "Year-end bonus for mid-year leaver", 26),
         ev("year_end_bonus_pc200", "Year-end bonus reference period question", 75),
         ev("year_end_bonus_pc200", "Year-end bonus for student converted to employee", 120),
         ev("student_workers", "Student worker 475 hours counter", 33),
         ev("student_workers", "Student contract during summer holidays", 90),
     ]},
    {"id": "emp_031", "name": "Anouk van Dijk", "role": "HR advisor Netherlands", "country": "NL", "opt_in": True, "hidden_topics": [],
     "evidence": [
         ev("notice_period_nl", "Notice period for Dutch employee with 12-year tenure", 6, vouched_by=["emp_033", "emp_021"]),
         ev("notice_period_nl", "Client asked about opzegtermijn in collective agreement (NL)", 19, "chat", vouched_by=["emp_034"]),
         ev("notice_period_nl", "Checked notice period during probation, Netherlands", 34),
         ev("notice_period_nl", "Notice period for Dutch fixed-term contract", 48),
         ev("notice_period_nl", "Notice period guide for NL clients (2026)", 61, "document", vouched_by=["emp_033"]),
         ev("notice_period_nl", "Termination by mutual consent: notice period question (NL)", 85),
         ev("notice_period_nl", "Notice period for Dutch employee on sick leave", 104),
         ev("notice_period_nl", "Opzegtermijn employer vs. employee (NL)", 140),
         ev("notice_period_nl", "Notice period after company transfer (NL)", 170),
     ]},
    {"id": "emp_033", "name": "Daan Bakker", "role": "Payroll consultant", "country": "NL", "opt_in": True, "hidden_topics": [],
     "evidence": [
         ev("notice_period_nl", "Notice period for Dutch fixed-term contract", 40),
         ev("notice_period_nl", "Notice period during probation, Netherlands", 160),
         ev("notice_period_nl", "Notice period question from NL client", 210),
         ev("pension_plans", "Pension plan rules for part-timers", 55),
     ]},
    {"id": "emp_027", "name": "Marc Lemmens", "role": "Tax specialist", "country": "BE", "opt_in": True, "hidden_topics": [],
     "evidence": [
         ev("cross_border_lux", "Cross-border worker Luxembourg: 24-day tax threshold", 1850, "document", author=True),
         ev("cross_border_lux", "Frontalier social security question (LU/BE)", 1720),
         ev("expat_taxation", "Inbound taxpayer regime application", 44),
         ev("expat_taxation", "Special tax regime eligibility check", 101),
     ]},
    {"id": "emp_022", "name": "Pieter Claes", "role": "Legal expert", "country": "BE", "opt_in": True, "hidden_topics": ["sick_leave_be"],
     "evidence": [  # hides sick leave: that topic must never surface him
         ev("sick_leave_be", "Guaranteed salary after relapse within 14 days", 10),
         ev("sick_leave_be", "Sick leave during annual holiday", 25),
         ev("notice_period_be", "Notice period calculation under the unified status (BE)", 15, vouched_by=["emp_010"]),
         ev("notice_period_be", "Notice period for employee with seniority before 2014", 58),
         ev("gdpr_employee_data", "Retention period for payroll records", 77),
     ]},
]

# Specialists for the extra demo topics.
people += [
    {"id": "emp_050", "name": "Joris Vandenberghe", "role": "Mobility & reward specialist", "country": "BE", "opt_in": True, "hidden_topics": [],
     "evidence": [
         ev("mobility_budget", "Employee switched company car to mobility budget", 8, vouched_by=["emp_003", "emp_045"]),
         ev("mobility_budget", "Mobility budget: pillar 2 housing costs", 23, vouched_by=["emp_010"]),
         ev("mobility_budget", "Mobility budget FAQ for clients (2026)", 47, "document", vouched_by=["emp_014"]),
         ev("mobility_budget", "Mobility budget cash-out at year end", 90),
         ev("mobility_budget", "Mobility budget eligibility check", 120),
         ev("bike_allowance", "Bike allowance for speed pedelec", 11, vouched_by=["emp_007"]),
         ev("bike_allowance", "Bike lease combined with bike allowance", 36),
         ev("bike_allowance", "Bike allowance kilometre registration", 70),
         ev("ev_home_charging", "Home charging reimbursement at quarterly kWh price", 4, vouched_by=["emp_021", "emp_005"]),
         ev("ev_home_charging", "Charging station at home installed via car policy", 29),
         ev("company_car_bik", "Benefit in kind company car recalculated with new CO2 value", 60),
     ]},
    {"id": "emp_051", "name": "Femke de Jong", "role": "Payroll consultant Netherlands", "country": "NL", "opt_in": True, "hidden_topics": [],
     "evidence": [
         ev("thirty_percent_ruling", "30% ruling application for new hire from Spain", 9, vouched_by=["emp_031", "emp_033"]),
         ev("thirty_percent_ruling", "30% ruling phase-down impact on net salary", 27, "document", vouched_by=["emp_034"]),
         ev("thirty_percent_ruling", "30% ruling salary threshold check", 55),
         ev("thirty_percent_ruling", "30% ruling for returning Dutch national", 88),
         ev("holiday_entitlement_nl", "Expiring statutory leave days (NL)", 16, vouched_by=["emp_031"]),
         ev("holiday_entitlement_nl", "Vakantiebijslag for part-timer", 41),
         ev("holiday_entitlement_nl", "Carry-over of extra-statutory leave (NL)", 77),
         ev("notice_period_nl", "Notice period question from NL client", 130),
     ]},
    {"id": "emp_052", "name": "Oliver Hughes", "role": "UK payroll lead", "country": "GB", "opt_in": True, "hidden_topics": [],
     "evidence": [
         ev("uk_payroll", "UK starter checklist without P45", 3, vouched_by=["emp_042"]),
         ev("uk_payroll", "PAYE RTI submission late", 19),
         ev("uk_payroll", "National Insurance category question", 44, vouched_by=["emp_040", "emp_003"]),
         ev("uk_payroll", "UK payroll go-live for Belgian client", 101, "document"),
     ]},
    {"id": "emp_053", "name": "Laura Gómez", "role": "Global mobility advisor", "country": "ES", "opt_in": True, "hidden_topics": [],
     "evidence": [
         ev("remote_work_abroad", "A1 certificate for employee working from Spain", 7, vouched_by=["emp_050", "emp_021", "emp_010"]),
         ev("remote_work_abroad", "Workation request: 3 weeks in Portugal", 18),
         ev("remote_work_abroad", "Remote work abroad policy review (2026)", 40, "document", vouched_by=["emp_045"]),
         ev("remote_work_abroad", "Permanent establishment risk check for remote worker", 66),
         ev("expat_taxation", "Expat cost allowance reimbursement", 58),
     ]},
    {"id": "emp_054", "name": "Kristof Hendrickx", "role": "HR policy advisor", "country": "BE", "opt_in": True, "hidden_topics": [],
     "evidence": [  # wrote the remote-work policy, but stopped working on it
         ev("remote_work_abroad", "Wrote the first remote work abroad policy", 1100, "document", vouched_by=["emp_005"], author=True),
         ev("remote_work_abroad", "A1 certificate question", 980),
         ev("remote_work_abroad", "Workation request review", 870),
         ev("social_elections", "Protected employee status during social elections", 25, vouched_by=["emp_022"]),
         ev("social_elections", "Social elections timeline 2028 planning", 60),
         ev("social_elections", "Works council candidate list question", 140),
     ]},
    {"id": "emp_055", "name": "Bram Desmet", "role": "Senior payroll consultant", "country": "BE", "opt_in": True, "hidden_topics": [],
     "evidence": [
         ev("temporary_unemployment", "Temporary unemployment notification for economic reasons", 13, vouched_by=["emp_014"]),
         ev("temporary_unemployment", "Employer supplement during temporary unemployment", 35),
         ev("temporary_unemployment", "Force majeure unemployment after flooding", 200, vouched_by=["emp_003"]),
         ev("warrants_stock_options", "Stock option grant accepted within 60 days", 22, vouched_by=["emp_027"]),
         ev("warrants_stock_options", "RSU vesting taxed as salary", 48),
         ev("warrants_stock_options", "Warrants bonus plan review", 150),
     ]},
]

# --- Rest of the company, generated -----------------------------------------

extra_names = [
    ("emp_003", "Jonas Wouters", "BE"), ("emp_005", "Eva Jacobs", "BE"), ("emp_007", "Kobe Mertens", "BE"),
    ("emp_010", "Hanne Willems", "BE"), ("emp_011", "Wout Goossens", "BE"), ("emp_021", "Elise Dubois", "BE"),
    ("emp_034", "Sanne de Boer", "NL"), ("emp_040", "Lukas Schneider", "DE"), ("emp_042", "Camille Laurent", "FR"),
    ("emp_045", "Ines Hermans", "BE"), ("emp_060", "Arne Coppens", "BE"), ("emp_061", "Charlotte Lambert", "BE"),
    ("emp_062", "Thijs Visser", "NL"), ("emp_063", "Yasmine El Amrani", "BE"), ("emp_064", "Stijn Verbeke", "BE"),
    ("emp_065", "Marie Dupont", "FR"), ("emp_066", "Hannah Weber", "DE"), ("emp_067", "Ruben Smit", "NL"),
    ("emp_068", "Lien Vermeersch", "BE"), ("emp_069", "Emma Clarke", "GB"),
]
all_ids = [p["id"] for p in people] + [e[0] for e in extra_names]

country_topics = {"DE": ["germany_payroll"], "FR": ["france_payroll"], "NL": ["notice_period_nl", "holiday_entitlement_nl"], "GB": ["uk_payroll"]}
country_only = ("germany_payroll", "france_payroll", "notice_period_nl", "holiday_entitlement_nl", "thirty_percent_ruling", "uk_payroll")
# Demo topics keep their hand-written experts on top, so generated people stay out of them.
demo_topics = ("cross_border_lux", "year_end_bonus_pc200", "mobility_budget", "remote_work_abroad", "bike_allowance", "ev_home_charging")
general = [t for t in TOPICS if t not in country_only + demo_topics]

for emp_id, name, country in extra_names:
    topics = country_topics.get(country, []) + rng.sample(general, 3)
    topics = topics[:4]
    evidence = []
    for topic in topics:
        for _ in range(rng.randint(1, 3)):
            vouchers = rng.sample([i for i in all_ids if i != emp_id], rng.choice([0, 0, 1, 2]))
            evidence.append(ev(topic, rng.choice(TEMPLATES[topic]), rng.randint(3, 320), rng.choice(TYPES), vouchers))
    people.append({"id": emp_id, "name": name, "role": rng.choice(ROLES), "country": country,
                   "opt_in": True, "hidden_topics": [], "evidence": evidence})

# Every topic except the deliberate knowledge gap needs at least one recent expert.
for topic in TOPICS:
    if topic == "cross_border_lux":
        continue
    recent = any(e["topic"] == topic and (REF - date.fromisoformat(e["date"])).days < 200
                 for p in people if p["opt_in"] and topic not in p["hidden_topics"] for e in p["evidence"])
    if not recent:
        owner = rng.choice([p for p in people if p["id"] in dict((e[0], 1) for e in extra_names)])
        for _ in range(3):
            owner["evidence"].append(ev(topic, rng.choice(TEMPLATES[topic]), rng.randint(5, 150), vouched_by=rng.sample(all_ids, 1)))

for p in people:
    assert all(e["topic"] in TOPICS for e in p["evidence"]), p["name"]
    p["evidence"].sort(key=lambda e: e["date"], reverse=True)

(DATA_DIR / "company.json").write_text(json.dumps({"employees": people}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"Wrote {len(people)} employees, {sum(len(p['evidence']) for p in people)} evidence items")
