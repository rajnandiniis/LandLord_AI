# 🏛️ LandlordAI v2 — NYC Property Violation Assistant

> Upload any violation → AI analyzes → action plan + letters + summons in 60 seconds
## 📺 Demo & How It Works

📽️ **[Click here to watch the LandlordAI v2 Demo](https://drive.google.com/file/d/1zKfknYlFOVDRHy0KEWmVVqSeT-pX7Bow/view?usp=drivesdk)**
*(Recommended: Watch on 2x speed)*


### The Workflow:
1. **Upload:** Drop your HPD/DOB violation notice (PDF/Image).
2. **Analyze:** `Reader Agent` extracts data while `Research Agent` builds a strategy.
3. **Draft:** `Writer Agent` generates legal letters and `Document Agent` scrapes extra data for the summons.
4. **Export:** Download your ready-to-use PDF packages and Excel databases.

## 🚀 Quick Start

```powershell
# Clone and run locally
cd landlordai_v2
pip install -r requirements.txt
python -m streamlit run app.py


## Project Structure

```
landlordai_v2/
├── app.py                    ← UI only (Streamlit)
├── agents/
│   ├── reader_agent.py       ← Agent 1: reads violations
│   ├── research_agent.py     ← Agent 2: builds strategy
│   ├── writer_agent.py       ← Agent 3: writes letters
│   └── document_agent.py     ← Agent 4: scrapes data + generates summons
├── utils/
│   ├── extractor.py          ← PDF/DOCX/Image text extraction
│   ├── excel_processor.py    ← Builds Excel database (3 sheets)
│   ├── pdf_generator.py      ← Creates PDF documents
│   └── validator.py          ← Edge case checks
├── config/
│   └── settings.py           ← Constants, violation data, prompt loader
├── prompts/
│   ├── reader_prompt.txt     ← AI prompt for violation reading
│   ├── research_prompt.txt   ← AI prompt for strategy
│   ├── writer_prompt.txt     ← AI prompt for letters
│   └── document_prompt.txt   ← AI prompt for scraping + summons
├── templates/
│   ├── rent_demand.txt       ← Legal template
│   ├── notice_to_cure.txt    ← Legal template
│   ├── eviction_notice.txt   ← Legal template
│   └── summons_draft.txt     ← Legal template
└── requirements.txt
```

## Features

| Tab | Feature |
|-----|---------|
| 📋 Analyze Violation | Upload HPD/DOB notice → 3 AI agents → full analysis |
| 💬 Legal Assistant | Chat with NYC property law AI |
| 📂 Case History | All violations analyzed this session |
| 📚 NYC Law Guide | Violation classes, agencies, fine reduction tips |
| 📊 Scrape & Summons | Upload any doc → extract to Excel → generate summons PDFs |

## Appearance Settings (in sidebar)

- 🌙 Dark / ☀️ Light mode
- 🟡 Gold / 🔵 Blue / 🟢 Green / 🔴 Rose accent colors
- Font size: Small / Medium / Large
- Compact mode toggle

## Pricing Suggestion

- Pay per notice: $25
- Basic: $99/month (10 violations)
- Pro: $199/month (unlimited + summons generator)
