### ev:0000 — Short imperative headline of the accomplishment
role:       Title, Company            # must match an employer in resume.yaml
dates:      YYYY-MM → YYYY-MM
metric:     before → after (delta)    # or "n/a" if qualitative — plenty of
                                      # real work has no number, and inventing
                                      # one is the failure this system prevents
confidence: measured                  # measured | estimated | qualitative
source:     where the number is documented   # REQUIRED when confidence: measured
scope:      who/how many · how often · what was at stake — what sizes the win
tags:       comma, separated, lowercase — whatever your field calls its
            capabilities: tools, systems, procedures, languages, curricula,
            licences, methods, domains
angles:     which angle(s) this supports, comma separated — each must be
            declared in the bank's `## Angles` block (templates/angle-entry.md)
narrative: >
  Two to four sentences. What was broken, what you did, what happened. This is
  the STAR story, written once here — not regenerated per JD. The tailor quotes
  and trims it; it never invents beyond it.
