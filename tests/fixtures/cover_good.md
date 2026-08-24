Your work on build-cache warming is the exact problem I spent two years on at
Example Co, so this role reads like a continuation rather than a jump.

There the deploy pipeline was the bottleneck; I cut median deploy time from 45m
to 6m across roughly 200 deploys a week, which unblocked the engineers who had
been waiting on CI. The same instinct (find the expensive thing in the critical
path and make it cheap) is what your platform team seems to be hiring for.

I'd bring the same bias toward measured wins over rewrites. I'd welcome the
chance to talk about where your build times hurt most.
