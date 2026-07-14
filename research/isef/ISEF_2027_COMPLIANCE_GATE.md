# VERA ISEF 2027 Compliance Gate

Status: not cleared for an ISEF-affiliated fair

This is an internal compliance checklist, not a research plan, abstract, poster,
or bibliography. It must not be submitted as student-authored project material.

## Official Rules Checked July 14, 2026

- `https://www.societyforscience.org/isef/international-rules/`
- `https://www.societyforscience.org/isef/international-rules/rules-for-all-projects/`
- `https://www.societyforscience.org/isef/international-rules/human-participants/`
- `https://www.societyforscience.org/isef/affiliated-fair-guidelines/requirements/`
- `https://ruleswizard.societyforscience.org/`
- `https://ba-leeds.org/science-fair/`
- `https://ba-leeds.org/science-and-engineering-fair-deadlines/`

The Society for Science 2027 rules page is live as of July 14, 2026. The rules
require independent student research, accurate attribution, the current forms,
and all required approvals. They permit AI as an acknowledged resource, but
prohibit using generative AI to write the fair research plan, abstract, poster,
or citations. Those four materials are deliberately absent from this directory.

For Contra Costa County, the Bay Area LEEDS CCCSEF page says the fair is open
to students attending school in Contra Costa County in grades 7-12. No school
fair qualification is required for CCCSEF entry, but the student must still
follow ISEF and CCCSEF paperwork. The 2026 page lists Los Medanos College as
the venue and March 5-7, 2026 as the fair dates; 2027 dates were not yet posted
on that page when checked. CCCSEF also states that appropriate ISEF forms and
unique CCCSEF forms must be completed with required signatures, and that the SRC
reviews the research plan before experimentation when pre-approval is required.

The Society affiliated-fair requirements state that an SRC must have at least
three members: a biomedical scientist, a science educator, and another member.
They also state that students without the proper approvals or forms on the
proper timeline may not qualify for ISEF. This repository therefore cannot
declare ISEF eligibility until the Contra Costa SRC or Adult Sponsor records the
required determinations in `research/private/isef_compliance_registry.json`.

## Immediate Human Actions

1. Contact an Adult Sponsor and the Contra Costa affiliated-fair SRC now. Give
   them the project history, dates, public datasets, repository, and
   `AI_ASSISTANCE_LEDGER.md`. Do not backdate a form or approval.
2. Ask the SRC to rule in writing whether the five public, preexisting datasets
   qualify for the public-data exemption and whether any Form 4 or other human
   participant documentation is required.
3. Ask the SRC how work already performed before their review may be treated.
   Their answer, not this repository, determines local eligibility.
4. Complete the Rules Wizard with the Adult Sponsor and use only the current
   2027 forms. At minimum, all projects normally require the Adult Sponsor
   checklist, Student Checklist, Approval Form, research plan, and Student
   Support Disclosure Form; the SRC determines additions.
5. Create `research/private/isef_compliance_registry.json` from the template
   only after each statement is true and documented.

Suggested first email subject: `CCCSEF SRC guidance request for software-only AI project using public datasets`.

Suggested first email body:

> I am preparing a software-only AI research project for the Contra Costa County
> Science & Engineering Fair. It uses only preexisting public datasets and does
> not recruit participants, run surveys, collect private data, diagnose disease,
> or make clinical recommendations. I need written guidance on required ISEF and
> CCCSEF forms, whether the public-data exemption applies, whether Form 4 or
> other human-participant documentation is needed, and how to disclose work that
> began before SRC review. I will not backdate any form or approval.

## Student Ownership Gate

Before presenting VERA as a student project, the student must personally:

- explain the research question, LTT overlap, proposed novelty, assumptions,
  and limitations without relying on generated prose;
- derive the fixed-profile IUT argument, shift-envelope guarantee, and
  unsupported-cell impossibility result;
- inspect the upstream INLP, R-LACE, LEACE, TaCo, and MANCE++ code and explain
  how each adapter calls it;
- independently run the compact reproduction and a documented subset of the
  raw-data pipeline, inspect failures, and verify the row-level calculations;
- decide which claims the evidence supports and remove claims they cannot
  defend;
- write the ISEF research plan, abstract, poster, presentation, and citations
  independently and in their own words, without generative AI;
- disclose all adult, mentor, software, and AI assistance on the required forms
  and during judging.

Completing a checklist is not enough. The work shown to judges must genuinely
be the student's independent work. If the SRC concludes that the current level
of AI assistance is incompatible with eligibility, the project must not be
represented as ISEF-ready.

## Scope and Safety

VERA is software-only and uses preexisting public datasets. It does not recruit
participants, interact with patients, diagnose disease, or make clinical
recommendations. Camelyon17 is a reliability benchmark only. Any future survey,
user study, application testing, private dataset, or clinical claim changes the
rules analysis and requires review before that work begins.

For the 2027 eligibility window, only work within the permitted continuous
12-month period beginning no earlier than January 2026 may be judged. The
student and SRC must determine and document the official project start date.
