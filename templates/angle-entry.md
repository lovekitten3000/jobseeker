<!-- The `## Angles` block of profile/evidence-bank.md. PRD §21.

     An ANGLE is a positioning stance: one claim about what you are *for*,
     proved by at least two evidence entries, aimed at a track. Do not
     confuse the three:

       track    (goals.yaml)        the job you are applying FOR
       evidence (evidence-bank.md)  what you have actually DONE
       angle    (this block)        the ARGUMENT connecting the two

     Every tailored resume picks exactly one angle; that choice sets the
     summary's opening line and which bullets lead. Three or more angles means
     different postings get genuinely different arguments instead of the same
     resume with the nouns swapped.

     Write these AFTER the evidence exists. An angle written first is a slogan
     looking for proof. `python3 bin/validate.py --lint-bank` fails an angle
     that fewer than two entries support, an angle with no claim, and an entry
     that cites an angle you never declared. -->

## Angles

### angle: a-slug
claim:  One line, in your own words, saying what you are for. Not a job title,
        not a list of skills — the thing a stranger should conclude about you.
proof:  ev:0000, ev:0000        # two or more entries that demonstrate it
serves: primary                 # track ids from goals.yaml this angle argues for

### angle: another-slug
claim:  A different argument, for a different kind of posting.
proof:  ev:0000, ev:0000
serves: primary, second-track
