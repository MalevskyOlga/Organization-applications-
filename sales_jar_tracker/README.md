# 🫙 Sales Jar Tracker

A web application that reads monthly sales data from an Excel file and generates a **glass jar visualization** showing sales progress toward the monthly target.

---

## 📋 Features

- Upload an Excel file with your monthly sales data
- Generates a jar image filled with gold coins proportional to sales progress
- Displays **Current Sales**, **Sales Target**, and **Sales Growth %** gauge
- Shows **OVERFLOW!** banner when sales exceed the target
- Download the result as **PNG image** or **PowerPoint (.pptx)** slide

---

## 🗂️ Project Structure

```
sales_jar_tracker/
├── app/
│   ├── app.py              ← Flask web server
│   ├── jar_generator.py    ← Image generation (Pillow)
│   └── templates/
│       └── index.html      ← Web UI
├── sales_jar_tracker_v2.xlsx   ← Sample Excel file
├── start.bat               ← Launch the app (double-click)
└── README.md
```

---

## 🚀 How to Start

1. Double-click **`start.bat`**
2. The browser opens automatically at `http://localhost:5050`
3. Press `Ctrl+C` in the terminal to stop the server

---

## 📊 Excel File Format

The Excel file must contain the following two rows in the first sheet:

| A | B |
|---|---|
| Monthly Target | 6000000 |
| Current Sales | 310000 |

Each month, upload a fresh Excel file with updated values.

---

## 🛠️ Requirements

- Python 3.10+
- Flask
- Pillow
- openpyxl
- python-pptx

Install all dependencies:

```bash
pip install flask pillow openpyxl python-pptx
```

---

## 📤 Output Options

| Button | Format | Description |
|--------|--------|-------------|
| ⬇ Download PNG | `.png` | Image file (800×500 px) |
| 📊 Download PPT | `.pptx` | 16:9 widescreen PowerPoint slide |
