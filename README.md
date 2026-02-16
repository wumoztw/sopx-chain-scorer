# SOPX Chain Scorer

`sopx-chain-scorer` 是一個針對加密貨幣（Altcoins）進行每週量化評分與分析的自動化系統。它結合了市場數據、制度分析、代幣經濟學與風險評估，為投資者提供多維度的決策參考。

Weekly GitHub Actions job:
- Pulls CoinGecko Top100
- Scores via SOPX Quant proxy + curated institutional facts + plugin rules
- Writes reports to `reports/` and appends `reports/history.csv`
- Posts summary to Plurk (optional; via GitHub Secrets)

## 核心功能與特點

### 1. 四維度量化評分模型 (SOPX Model)
該程式的核心是其獨特的評分模型，計算公式大致為：
**總分 = (制度 × 權重) + (需求 × 權重) + (捕獲 × 權重) - (風險 × 權重)**

*   **🧱 制度 (Constitutional)**:
    *   評估項目的核心架構與法律/治理基礎。
    *   透過專家維護的手動數據進行校準。
*   **🏗 需求 (Demand)**:
    *   **流動性需求**: 透過成交量與市值的比例 (Vol/Mcap) 衡量。
    *   **社群熱度**: 分析 X (Twitter) 與 Reddit 數據。
*   **🎭 捕獲 (Capture)**:
    *   **代幣經濟學**: 分析供應量透明度與通膨懲罰。
*   **⛔ 風險 (Risk)**:
    *   監控 GitHub 開發活躍度、流動性風險與市值門檻。

### 2. 多層次數據抓取
系統利用 CoinGecko API 進行兩階段數據獲取，確保深度分析的高分項目擁有最完整的數據指標。

### 3. 週報生成與趨勢分析
自動計算 7 週內的趨勢變化，識別上升明星與結構性警訊，並生成 Markdown 與 JSON 報告。

### 4. 投資人導向的 Plurk 自動推送
自動將項目分類為 **HOLD (長期核心)**、**ROTATE (成長配置)**、**TRADE (高波動交易)** 與 **AVOID (結構風險)** 並推送至社交平台。

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
