# Lessons Learned - 專案教訓與自我改進記錄

## 1. 儀表板深色模式配色與易讀性失敗
*   **錯誤描述**：
    在上一版重構中，採用了「莫蘭迪粉彩 (Morandi Pastels)」色彩方案。用戶回饋「這個配色很糟糕，閱讀起來非常吃力」，因為在深色背景 (`#0b0f19`) 下，文字、數值和決策狀態 Badge 的對比度過低（接近 3:1），導致字體與背景融合在一起，使用者需要極度用力才能看清數據。
*   **根因（第一性原理拆解）**：
    *   **忽略了光度對比的物理真理**：眼睛辨識文字的本質在於光度對比（Luminance Contrast）。深色背景（亮度 < 10%）如果搭配暗灰、暗藍或低飽和度低明度的粉彩文字（亮度 40-50%），兩者的亮度差過小，視網膜需要更強的調節力才能區分，導致極易疲勞。
    *   **粉彩（Pastel）的場景誤用**：粉彩在淺色模式（白色背景）下有極佳的高級感，但在深色模式下，低飽和度 + 低明度會直接導致「色彩失真」與「字體模糊化」。深色模式的「高級感」與「柔和感」應該來自於「極低飽和度大面積背景 + 少量且高對比的明亮語意色彩 (SaaS Bright Glow Theme) + 精緻的半透明玻璃擬物邊框」，而非把文字也改得暗沉。
*   **下次 MUST 怎麼做**：
    *   **ALWAYS** 確保深色模式下的主體文字與核心數值亮度高於 85%（例如近純白 `#f9fafb` 或淡灰 `#e5e7eb`），確保對比度符合 WCAG 2.1 AA 標準（至少 4.5:1）。
    *   **NEVER** 在深色模式下使用暗灰色（如 `#64748b` 或 `text-slate-600`）作為需要閱讀的數值或描述性小字，這會導致文字隱形。
    *   **ALWAYS** 對於語意狀態（HOLD, ROTATE, TRADE, AVOID），使用「亮色文字 + 半透明背景 + 亮色微邊框」的微發光結構（例如 `bg-emerald-500/15 text-emerald-400 border-emerald-500/30`），這能在保持顏色 salience 的同時，避免刺眼的霓虹震顫，又具備極高易讀性。
    *   **ALWAYS** 調整 Plotly 圖表時，將格線 (`gridcolor`) 的不透明度設在 `0.06 - 0.08` 之間以保證可讀性，並將折線寬度設在 `3.0px` 以上，以在深色背景中突出數據。
*   **相關檔案**：
    *   [dashboard.py](file:///home/wuminchin/.gemini/antigravity/scratch/sopx-chain-scorer/dashboard.py)
    *   [sopx_dashboard_generator.py](file:///home/wuminchin/.gemini/antigravity/scratch/sopx-chain-scorer/sopx_dashboard_generator.py)
