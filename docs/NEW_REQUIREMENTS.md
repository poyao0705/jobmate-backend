# New Requirements

### Refactor Service
- skill service
    - add new skill
    - normalize skill
    - find similar skills
    - backfilling skill description (from the csv file)
    - backfilling skill embedding (from the populated description in the skill table)

- resume service
    - parse resume from PDF, DOCX, TXT
    - extract skills from resume (independent implementation)
    - save to db

- job service
    - get the job description from the job posting
    - extract skills from job description (independent implementation)
    - save to db

- enrichment service
    - get the job description using langchain wiki tool
    
### Agents
- gap analyst
    - gap analysis
- job hunter
    - suggest job
    - job search
- career coach
    - career planning
    - career development
- ai interviewer
    - ai interview

### Tools
- report tools
- job tools