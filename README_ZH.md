# 展示網頁應用程式

[English](./README.md)    [中文](README_ZH.md)

此應用程式允許使用者提交透過 [AI 模型網站](https://aiotplatform.ndmctsgh.edu.tw/service-website) 解析的 Linear Probe 結果。系統會自動生成對應的 CXR 報告，使用者可以複製文字、下載或列印。

## 使用說明

### 步驟 1: 克隆專案

將此專案克隆到本地：

```bash
git clone https://github.com/shin13/AI-generated-CXR-report-assistant.git
```

若需指定存放目錄，可添加路徑參數：

```bash
git clone https://github.com/shin13/AI-generated-CXR-report-assistant.git 自訂資料夾名稱
```

### 步驟 2: 安裝必要套件

安裝必要的套件：

```bash
pip install -r requirements.txt
```

### 步驟 3: 設定環境變數

創建一個 `.env` 文件並設定以下環境變數：

```python
`AI_MODEL_URL`: AI 模型的 URL (OpenAI or DeepSeek)
`API_KEY`: AI 模型的 API 密鑰 (OpenAI or DeepSeek)
`MODEL_NAME`: AI 模型名稱 (e.g., GPT-3, DeepSeek)
`FASTAPI_ENDPOINT` = "http://127.0.0.1:7890/upload_csv/"
```

### 步驟 4: 啟動應用

啟動應用：

```bash
python main.py
```

這會啟動 FastAPI 和 Streamlit 應用程式。

### 步驟 5: 生成 AI 報告

選擇 Example 檔案後，點選 submit 按鈕，即可生成 AI 報告。
