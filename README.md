# SOPX Chain Scorer

Weekly GitHub Actions job:
- Pulls CoinGecko Top100
- Scores via SOPX Quant proxy + curated institutional facts + plugin rules
- Writes reports to `reports/` and appends `reports/history.csv`
- Posts summary to Plurk (optional; via GitHub Secrets)

## Setup
1) Add Plurk OAuth secrets in repo settings:
- PLURK_CONSUMER_KEY
- PLURK_CONSUMER_SECRET
- PLURK_ACCESS_TOKEN
- PLURK_ACCESS_TOKEN_SECRET

2) Edit `curated_dataset.yml` to improve institutional accuracy.

3) Run Actions → Weekly SOPX Scoring → Run workflow.

## Outputs
- reports/report_YYYY-MM-DD.md
- reports/report_YYYY-MM-DD.json
- reports/history.csv
