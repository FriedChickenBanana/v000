# 🛡️ Setup & Testing Guide - AI Misinformation Detector

This guide provides step-by-step instructions to configure, run, and test your **Web-Augmented RAG Misinformation Detector** on Windows.

---

## 📋 Prerequisites

Ensure you have the following installed and ready:
1. **Python 3.9+** (Installed and added to your system `PATH`)
2. **Google Chrome** browser
3. **API Keys**:
   - API KEYS ALREADY ADDED YOU CAN SKIP THIS PART
   - YOU MIGHT WANT TO CHANGE THE GEMINI API KEY WHEN YOU RUN AS IT MIGHT RUN OUT
   - **Google Gemini API Key**: [Get a key from Google AI Studio](https://aistudio.google.com/).
   - **Tavily API Key**: [Get a key from Tavily Search API](https://tavily.com/).

---

## 🛠️ Step 1: Configure and Start the Backend Server

The backend requires a Python virtual environment to manage dependencies. Since you are on Windows, we provide the most bulletproof ways to run your commands depending on your shell.

### 1. Open your Terminal
Open **PowerShell** or **Command Prompt** and navigate to the backend directory:
```powershell
cd "d:\VS\chrome_extension\v001\misinfo-detector\backend"
```

### 2. Activate the Virtual Environment & Install Dependencies
A virtual environment (`venv`) has already been created in your backend folder. Follow one of the methods below to activate it or run commands inside it.

#### 💡 Method A: The Bulletproof Method (Highly Recommended - No Activation Needed!)
You do **not** need to activate the virtual environment to use it. You can call the Python executable inside the `venv` directory directly. This avoids all Windows Execution Policy restrictions!

* **Install/Verify dependencies:**
  ```powershell
  .\venv\Scripts\pip.exe install -r requirements.txt
  ```

* **Start the FastAPI Server:**
  ```powershell
  .\venv\Scripts\python.exe -m uvicorn main:app --reload
  ```
  *(Note: Ensure you use a **single colon** `:` between `main` and `app`! Double colons like `main::app` will cause an error.)*

---

#### 💡 Method B: PowerShell Activation
If you prefer activating the virtual environment in PowerShell:
1. **Enable Script Execution (If blocked):**
   By default, Windows blocks running scripts. Run this command first in your PowerShell window:
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
   ```
2. **Activate the Environment:**
   ```powershell
   .\venv\Scripts\Activate.ps1
   ```
   *(You should now see `(venv)` prepended to your command prompt).*
3. **Install Dependencies:**
   ```powershell
   pip install -r requirements.txt
   ```
4. **Start the FastAPI Server:**
   ```powershell
   uvicorn main:app --reload
   ```

---

#### 💡 Method C: Windows Command Prompt (CMD)
If you are using the classic Windows Command Prompt instead of PowerShell:
1. **Activate the Environment:**
   ```cmd
   call venv\Scripts\activate.bat
   ```
2. **Install Dependencies:**
   ```cmd
   pip install -r requirements.txt
   ```
3. **Start the FastAPI Server:**
   ```cmd
   uvicorn main:app --reload
   ```

---

### 3. Verify Backend Status
Once the server starts successfully, you will see output like this:
```text
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```
Open your browser and navigate to `http://localhost:8000/`. You should see a successful health check response:
```json
{"status":"healthy","service":"Misinformation Detector RAG API"}
```

---

## 🧩 Step 2: Load the Chrome Extension

1. **Open Google Chrome** and go to `chrome://extensions/` in the URL bar.
2. **Turn on Developer Mode** by toggling the switch in the top-right corner.
3. Click **Load unpacked** in the top-left corner.
4. **Browse and Select** the following directory:
   `d:\VS\chrome_extension\v001\misinfo-detector\extension`
5. The extension is now successfully installed! You will see the **AI Misinformation Detector** card on the screen.

---

## 🔍 Step 3: Test the RAG Fact-Checking in Action

Let's test the entire Web-RAG fact-checking system:

1. **Open any webpage** (e.g., a news article, Wikipedia page, or blog post).
2. **Highlight a claim** you want to fact-check.
   - *Example 1 (True claim):* `"NASA discovered liquid water flowing on Mars in 2015."`
   - *Example 2 (False claim):* `"Bananas grow on giant wooden trees."`
   - *Example 3 (Misleading claim):* `"The Great Wall of China is the only man-made structure visible from space."`
3. **Right-click** on the highlighted text.
4. Select **Verify claim with AI** from the context menu.

### 🌟 What Happens Behind the Scenes:
1. **Instant Glassmorphism Overlay**: A dark glassmorphism overlay slides up from the bottom with a glowing spinner and an italicized preview of your claim.
2. **RAG pipeline**:
   - The backend queries Tavily Search for the top 4 matching articles.
   - Scraped text is split into 500-character chunks.
   - Chunks are converted to vector embeddings using `GoogleGenerativeAIEmbeddings` and stored in an ephemeral, in-memory ChromaDB.
   - The vector store retrieves the top 3 most relevant context blocks.
   - Gemini 3.5 Flash evaluates the claim based on the context and compiles a structured JSON fact check.
3. **Result Presentation**:
   - The spinner transitions into a bold verdict badge (**TRUE CLAIM** in emerald green gradient, **FALSE CLAIM** in crimson red gradient, or **MISLEADING** in amber orange gradient).
   - You will see a detailed 2-3 sentence AI explanation in the Fact-Check Analysis block.
   - A list of clickable, interactive **Verified Sources** appears at the bottom. Hovering over a source highlights it with a blue glow.

---

## ❌ Troubleshooting

### 1. `uvicorn : The term 'uvicorn' is not recognized...`
* **Why it happens:** The `uvicorn` command is only available inside your virtual environment. If the virtual environment is not activated, or if Windows script execution policy blocked activation, Windows cannot find `uvicorn`.
* **Fix:** Use **Method A (The Bulletproof Method)** to call the executable directly without needing activation:
  ```powershell
  .\venv\Scripts\python.exe -m uvicorn main:app --reload
  ```

### 2. `Activate.ps1 cannot be loaded because running scripts is disabled...`
* **Why it happens:** Windows PowerShell has a security feature called `ExecutionPolicy` that blocks script execution by default.
* **Fix:** Run this command to bypass the block for the current terminal session:
  ```powershell
  Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process
  ```
  Then try running `.\venv\Scripts\Activate.ps1` again.

### 3. `Failed to load app: Error parsing attribute "main::app"`
* **Why it happens:** You used two colons (`::`) instead of a single colon (`:`).
* **Fix:** Ensure you run:
  ```powershell
  uvicorn main:app --reload
  ```
  *(with only one colon).*

### 4. Connection Error (`VERIFICATION ERROR`) in Chrome Overlay
* **Why it happens:** The extension cannot communicate with `http://localhost:8000`.
* **Fix:** Ensure your FastAPI backend server is running in your terminal. Verify that the terminal window is open and that the server didn't stop or crash.
