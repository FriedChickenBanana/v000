// AI Misinformation Detector - Content Script

/**
 * Dynamically injects Google Fonts (Outfit) into the host webpage.
 * This guarantees premium typography regardless of the website's default font settings.
 */
(function() {
  const fontLinkId = "misinfo-detector-fonts";
  if (!document.getElementById(fontLinkId)) {
    const link = document.createElement("link");
    link.id = fontLinkId;
    link.rel = "stylesheet";
    link.href = "https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap";
    document.head.appendChild(link);
    console.log("AI Misinformation Detector: Premium font 'Outfit' successfully injected into host page.");
  }
})();
