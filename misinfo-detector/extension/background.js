// Service worker for AI Misinformation Detector

// 1. Create Context Menu on Installation
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "verifyClaim",
    title: "Verify claim with AI",
    contexts: ["selection"]
  });
  console.log("AI Misinformation Detector context menu created successfully.");
});

// 2. Listen for Context Menu clicks
chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId === "verifyClaim" && info.selectionText) {
    const selectedText = info.selectionText;
    const tabId = tab.id;

    console.log(`Verifying claim: "${selectedText}"`);

    // A. Show immediate loading overlay inside the web page for instant feedback
    chrome.scripting.executeScript({
      target: { tabId: tabId },
      func: injectLoadingModal,
      args: [selectedText]
    });

    // B. Send POST request to FastAPI Backend
    fetch("http://localhost:8000/verify", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ claim: selectedText })
    })
    .then(async (response) => {
      if (!response.ok) {
        // Retrieve error details if possible
        let errMsg = `Server returned status ${response.status}`;
        try {
          const errData = await response.json();
          errMsg = errData.detail || errMsg;
        } catch(e) {}
        throw new Error(errMsg);
      }
      return response.json();
    })
    .then((data) => {
      console.log("Fact-check result received:", data);
      // C. Inject result modal with the fact check verdict, analysis, and sources
      chrome.scripting.executeScript({
        target: { tabId: tabId },
        func: injectResultModal,
        args: [data]
      });
    })
    .catch((error) => {
      console.error("Fact-checking failed:", error);
      // D. Inject error modal to let the user know what happened (e.g. backend server offline)
      chrome.scripting.executeScript({
        target: { tabId: tabId },
        func: injectErrorModal,
        args: [error.message || "Failed to communicate with the fact-checking backend."]
      });
    });
  }
});

// --- Injected Functions ---
// Note: These functions run in the content script context of the active tab.
// They must be self-contained and cannot reference outer variables of background.js.

function injectLoadingModal(claimText) {
  // Check if a modal is already active and remove it
  const existingModal = document.getElementById("misinfo-detector-overlay");
  if (existingModal) {
    existingModal.remove();
  }

  // Escape claim text to prevent HTML injection
  const escapedClaim = claimText
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");

  // Create loading overlay
  const overlay = document.createElement("div");
  overlay.id = "misinfo-detector-overlay";
  overlay.className = "misinfo-overlay animate-fade-in";
  
  overlay.innerHTML = `
    <div class="misinfo-modal animate-slide-up">
      <div class="misinfo-modal-header">
        <span class="misinfo-logo">🛡️ Misinfo Detector</span>
        <button class="misinfo-close-btn" id="misinfo-close-btn" aria-label="Close">&times;</button>
      </div>
      <div class="misinfo-loading-container">
        <div class="misinfo-spinner"></div>
        <p class="misinfo-loading-text">Analyzing your claim using Web-Augmented RAG...</p>
      </div>
      <div class="misinfo-claim-preview">
        <strong>Selected Claim:</strong> "${escapedClaim}"
      </div>
    </div>
  `;

  document.body.appendChild(overlay);

  // Setup close listener
  document.getElementById("misinfo-close-btn").addEventListener("click", () => {
    overlay.classList.add("animate-fade-out");
    setTimeout(() => overlay.remove(), 300);
  });
}

function injectResultModal(data) {
  const overlay = document.getElementById("misinfo-detector-overlay");
  if (!overlay) return;

  const { verdict, analysis, sources } = data;
  
  // Decide styling classes based on verdict
  let verdictClass = "verdict-misleading";
  let verdictIcon = "⚠️";
  let verdictLabel = "MISLEADING";

  if (verdict === "TRUE") {
    verdictClass = "verdict-true";
    verdictIcon = "✅";
    verdictLabel = "TRUE CLAIM";
  } else if (verdict === "FALSE") {
    verdictClass = "verdict-false";
    verdictIcon = "❌";
    verdictLabel = "FALSE CLAIM";
  }

  // Construct sources HTML
  let sourcesHTML = "";
  if (sources && sources.length > 0) {
    sourcesHTML = `
      <div class="misinfo-section-title">Verified Sources</div>
      <div class="misinfo-sources-list">
        ${sources.map((url, index) => {
          let displayName = url;
          try {
            const parsedUrl = new URL(url);
            displayName = parsedUrl.hostname.replace("www.", "") + parsedUrl.pathname;
            if (displayName.length > 40) {
              displayName = displayName.substring(0, 38) + "...";
            }
          } catch(e) {}
          return `
            <a href="${url}" target="_blank" rel="noopener noreferrer" class="misinfo-source-card">
              <span class="source-index">${index + 1}</span>
              <span class="source-url" title="${url}">${displayName}</span>
              <span class="source-icon">🔗</span>
            </a>
          `;
        }).join("")}
      </div>
    `;
  } else {
    sourcesHTML = `
      <div class="misinfo-section-title">Verified Sources</div>
      <p class="misinfo-no-sources">No external sources were referenced for this validation.</p>
    `;
  }

  // Escape analysis to prevent XSS
  const escapedAnalysis = analysis
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");

  // Re-populate modal with the results
  const modalContainer = overlay.querySelector(".misinfo-modal");
  if (modalContainer) {
    modalContainer.innerHTML = `
      <div class="misinfo-modal-header">
        <span class="misinfo-logo">🛡️ Misinfo Detector</span>
        <button class="misinfo-close-btn" id="misinfo-close-btn" aria-label="Close">&times;</button>
      </div>
      <div class="misinfo-result-body">
        <div class="misinfo-verdict-badge ${verdictClass}">
          <span class="verdict-icon">${verdictIcon}</span>
          <span class="verdict-text">${verdictLabel}</span>
        </div>
        
        <div class="misinfo-section-title">AI Fact-Check Analysis</div>
        <div class="misinfo-analysis-content">
          ${escapedAnalysis}
        </div>
        
        ${sourcesHTML}
      </div>
      <div class="misinfo-modal-footer">
        Powered by Gemini 3.5 Flash & Tavily Search RAG
      </div>
    `;
  }

  // Setup close listener again on new elements
  document.getElementById("misinfo-close-btn").addEventListener("click", () => {
    overlay.classList.add("animate-fade-out");
    setTimeout(() => overlay.remove(), 300);
  });
}

function injectErrorModal(errorMessage) {
  const overlay = document.getElementById("misinfo-detector-overlay");
  if (!overlay) return;

  const escapedError = errorMessage
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");

  const modalContainer = overlay.querySelector(".misinfo-modal");
  if (modalContainer) {
    modalContainer.innerHTML = `
      <div class="misinfo-modal-header">
        <span class="misinfo-logo">🛡️ Misinfo Detector</span>
        <button class="misinfo-close-btn" id="misinfo-close-btn" aria-label="Close">&times;</button>
      </div>
      <div class="misinfo-result-body">
        <div class="misinfo-verdict-badge verdict-error">
          <span class="verdict-icon">⚠️</span>
          <span class="verdict-text">VERIFICATION ERROR</span>
        </div>
        
        <div class="misinfo-section-title">What went wrong?</div>
        <div class="misinfo-error-content">
          <p>${escapedError}</p>
          <p class="misinfo-error-tip">Please ensure your FastAPI backend is running locally at <code>http://localhost:8000</code> and your API keys are correctly set in the backend <code>.env</code> file.</p>
        </div>
      </div>
      <div class="misinfo-modal-footer">
        Verification failed. Check network or server logs.
      </div>
    `;
  }

  // Setup close listener again on new elements
  document.getElementById("misinfo-close-btn").addEventListener("click", () => {
    overlay.classList.add("animate-fade-out");
    setTimeout(() => overlay.remove(), 300);
  });
}
