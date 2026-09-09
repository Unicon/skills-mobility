# Landing page

The public front door for people hearing about SMI: the project introduction plus
links to the two demo consoles (credential-gated) and the GitHub repository — so
only one URL needs remembering.

A single static `index.html`, deliberately build-free (no React/Vite — it is two
paragraphs and three links). The `package.json` exists only so the npm workspace
glob (`apps/*`) tolerates the directory; there are no dependencies or scripts.

Hosting: its own **un-gated** S3 + CloudFront distribution
(`infra/cloudformation/landing-ui.yml`, demo branch) — unlike the consoles, this
page must be reachable without the demo Basic-auth credential. Deploy steps live
in `infra/DEPLOY.md`.

The console URLs are hardcoded (stable CloudFront domains); update them here if
either distribution is ever recreated.
