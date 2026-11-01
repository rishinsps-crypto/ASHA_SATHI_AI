const searchBox=document.getElementById("tableSearch");
if(searchBox)searchBox.addEventListener("input",()=>{const q=searchBox.value.toLowerCase();document.querySelectorAll("#dataTable tbody tr").forEach(r=>r.style.display=r.innerText.toLowerCase().includes(q)?"":"none");});
function downloadTable(id,name){const t=document.getElementById(id);if(!t)return;const lines=[...t.querySelectorAll("tr")].map(r=>[...r.querySelectorAll("th,td")].map(c=>'"'+c.innerText.replaceAll('"','""')+'"').join(","));const blob=new Blob([lines.join("\\n")],{type:"text/csv"});const a=document.createElement("a");a.href=URL.createObjectURL(blob);a.download=name;a.click();URL.revokeObjectURL(a.href);}

// Browser speech-to-text for the Voice-to-EHR Studio.
(() => {
  const start = document.getElementById("startVoice");
  const stop = document.getElementById("stopVoice");
  const transcript = document.getElementById("transcript");
  const language = document.getElementById("speechLanguage");
  const status = document.getElementById("voiceStatus");
  if (!start || !transcript) return;
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  let recognition = null;
  let finalText = "";
  if (!SpeechRecognition) {
    status.textContent = "Speech recognition is not supported in this browser. Use Chrome or type the transcript.";
    start.disabled = true;
    return;
  }
  recognition = new SpeechRecognition();
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.onstart = () => { start.disabled = true; stop.disabled = false; status.textContent = "Listening… speak clearly."; };
  recognition.onresult = (event) => {
    let interim = "";
    for (let i = event.resultIndex; i < event.results.length; i++) {
      const text = event.results[i][0].transcript;
      if (event.results[i].isFinal) finalText += text + " ";
      else interim += text;
    }
    transcript.value = finalText + interim;
  };
  recognition.onerror = (event) => { status.textContent = "Speech error: " + event.error + ". You can type/edit the transcript."; };
  recognition.onend = () => { start.disabled = false; stop.disabled = true; status.textContent = "Capture stopped. Review the transcript before saving."; };
  start.addEventListener("click", () => {
    finalText = transcript.value.trim() ? transcript.value.trim() + " " : "";
    recognition.lang = language.value;
    try { recognition.start(); } catch (e) { status.textContent = "Microphone could not start. Check browser permission."; }
  });
  stop.addEventListener("click", () => recognition.stop());
})();
