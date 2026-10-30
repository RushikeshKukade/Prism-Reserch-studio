# Submission guide

PRISM Research Studio is an independent India-focused assessment prototype.
It is not an official PRISM product.

## Run locally

Requires Python 3.10+ and a modern browser. No third-party packages. Core research needs no API key.

1. Extract the download and open this folder (the folder containing app.py).
2. In a terminal, run: python app.py --port 18765
   On Windows you can use: py app.py --port 18765
3. Keep the terminal running and open http://127.0.0.1:18765 manually.
4. Stop with Ctrl+C.

Use HTTP, not HTTPS. Do not open static/index.html directly or use Live Server.
If a port is blocked or occupied, select another port and use the same number
in the browser address. Read any terminal error before opening the page.

## Check the project

python -m unittest discover -s tests -v
python evaluate.py

The evaluation report covers 35 automated test methods and 16 handcrafted
historical question cases. It does not establish unrestricted answer accuracy
or investment performance. No live refresh runs as part of these checks.

## Scope and limitations

- 200 NIFTY 200 companies have identity and saved market-data coverage.
- Verified financial-statement analysis covers TCS, Infosys and HCLTech.
- Market data is a dated snapshot, not a guaranteed live exchange feed.
- Research monitors are local browser rules, not scheduled notifications.
- The core assistant uses defined queries and calculations. An optional OpenAI brief requires a local API key; no live model call has yet been verified. See README.md.
- Current constituents have survivorship bias and are not a historical universe.
- No trading backtest or validated profitable strategy is claimed.
- Public provider terms and exchange data licensing need review before production use.

See README.md for architecture, source links, metric definitions and caveats.

## Optional API setup

Copy .env.example to .env and add your OpenAI key locally. Git ignores .env and
.env.*; only the blank .env.example is included. Never upload your populated .env.
The core application works without a key. Generate brief is an explicit paid API
request when configured; it sends the question and selected evidence to OpenAI.

## Upload to GitHub

Create an empty repository on your GitHub account, preferably private for an
assessment. Do not select GitHub's generated README, license or gitignore.
From this folder:

git init -b main
git add .
git commit -m "Add India equity research assessment prototype"
git remote add origin YOUR_REPOSITORY_URL
git push -u origin main

Replace YOUR_REPOSITORY_URL with the HTTPS URL shown by your new repository.
A private repository requires explicitly granting the reviewer access.
No software license is added; choose one deliberately if you want to grant
reuse rights. Data remains subject to its original provider terms.

## Email submission

Gmail blocks JavaScript files even inside ZIP attachments. Upload the ZIP to
Google Drive and share a download link, or share a GitHub repository with
appropriate reviewer access. Do not attach this source ZIP directly in Gmail.
