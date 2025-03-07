
# AI-Powered CXR Report Generator (胸部X光AI報告產生器)

[English](./README.md) | [中文](README_ZH.md)

這是一個使用AI分析技術，從胸部X光(CXR)影像自動生成結構化放射學報告的網頁應用程式。應用程式提供簡單的界面上傳影像並接收詳細、醫學準確的報告。

## 功能特點

- **直接影像分析**：上傳JPG/JPEG格式的胸部X光影像進行即時處理
- **AI驅動報告生成**：先進的AI模型分析影像並生成結構化報告
- **醫學術語**：報告使用標準放射學術語和格式
- **儲存與匯出**：儲存生成的報告以供未來參考
- **響應式設計**：適用於桌面和平板設備的友好用戶界面

## 開始使用

### 系統需求

- Python 3.8 或更高版本
- pip (Python 套件安裝器)

### 安裝步驟

1. **複製專案**

   ```bash
   git clone https://github.com/shin13/AI-Powered-CXR-Report-Generator.git
   cd AI-Powered-CXR-Report-Generator
   ```

2. **安裝必要套件**

   ```bash
   pip install -r requirements.txt
   ```

3. **設定環境變數**

   在專案根目錄創建一個 `.env` 檔案，包含以下變數：

   ```bash
   # API 設定
   OPENAI_API_KEY=your-openai-key-here
   CHATGPT_MODEL=gpt-4o-mini
   
   # 後端設定
   BACKEND_URL=http://localhost:7890
   
   # AI 服務設定
   BASE_URL_AI=https://your-ai-service-url.com/api
   CXR_FEATURES_ENDPOINT=/v1/cxr/features
   CXR_LINEAR_PROBE_ENDPOINT=/v1/cxr/linear-probe
   AUTH_USERNAME=your_username
   AUTH_PASSWORD=your_password
   ```

### 運行應用程式

使用單一命令啟動應用程式：

```bash
python main.py
```

這將同時啟動FastAPI後端服務器和Streamlit前端應用程式。應用程式將可通過以下地址訪問：

- **前端**：http://localhost:8501
- **後端API**：http://localhost:7890

## 使用指南

1. **訪問應用程式**
   - 打開瀏覽器並開啟此連結 http://localhost:8501

2. **上傳影像**
   - 點擊「Upload your CXR image file (jpg)」按鈕
   - 從您的設備選擇有效的胸部X光影像

3. **生成報告**
   - 點擊「Submit」按鈕處理影像
   - 等待 AI 分析影像並生成報告

4. **查看和保存報告**
   - 生成的報告將出現在「Report (draft)」部分
   - 以 Markdown 或 Text 格式查看報告
   - 可通過「Recent Reports」下拉選單訪問先前的報告

## 專案結構

```bash
AI-Powered-CXR-Report-Generator/
├── app/                    # 前端和服務組件
│   ├── app.py              # Streamlit前端應用
│   ├── config.py           # 配置設定
│   ├── data/               # 數據和模型信息
│   ├── middleware/         # 錯誤處理和日誌記錄
│   ├── services/           # 服務層組件
│   └── static/             # 靜態資源
├── logs/                   # 應用程式日誌
├── reports/                # 生成的報告
├── main.py                 # FastAPI後端應用
├── requirements.txt        # Python依賴項
└── README.md               # 專案文檔
```

## 許可證

[MIT License](LICENSE)

## 致謝

- 本專案使用 OpenAI API 進行語言處理
- 使用 Streamlit 和 FastAPI 作為應用程式框架
