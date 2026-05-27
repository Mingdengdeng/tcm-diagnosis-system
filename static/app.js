const STORAGE_KEYS = {
  userId: "tcm_user_id",
  profile: "tcm_user_profile",
  baseline: "tcm_user_baseline",
  history: "tcm_follow_up_history",
  settings: "tcm_app_settings"
};
const APP_BASE = (window.TCM_APP_BASE || "").replace(/\/$/, "");

let state = {
  currentStep: 1,
  furthestStep: 1,
  sessionId: null,
  mode: "qa_only",
  userId: getOrCreateUserId(),
  userType: "new_user",
  settings: normalizeSpeechSettings(loadJson(STORAGE_KEYS.settings, defaultSpeechSettings())),
  profile: {},
  baseline: loadJson(STORAGE_KEYS.baseline, null),
  faceObservation: null,
  chiefComplaint: null,
  currentQuestion: null,
  tenQuestions: [],
  symptoms: [],
  recognitionTarget: null,
  recognitionGroup: null,
  recognition: null,
  webSpeechSupported: false,
  localRecorderSupported: false,
  webRecognition: null,
  webFinalTranscript: "",
  webInterimTranscript: "",
  webSpeechError: "",
  voiceEngine: null,
  isRecording: false,
  recordingBaseText: "",
  audioContext: null,
  audioStream: null,
  audioSource: null,
  audioProcessor: null,
  audioChunks: [],
  audioSampleRate: 16000,
  voiceStartedAt: 0,
  voiceLastSoundAt: 0,
  voiceDetected: false,
  voiceAutoStopping: false,
  isSubmittingAnswer: false,
  voiceHadResult: false,
  voiceNoResultTimer: null,
  redFlagActive: false,
  urgentAcknowledged: false,
  adminTapCount: 0,
  adminTapTimer: null,
  processingTimer: null,
  keyboardTarget: null
};

const $ = (selector) => document.querySelector(selector);
const stepItems = Array.from(document.querySelectorAll(".step-item"));
const stepPanels = Array.from(document.querySelectorAll(".wizard-panel"));

init();

function init() {
  populateRangeSelects();
  hydrateProfile();
  setupSpeechRecognition();
  bindEvents();
  renderSettingsPanel();
  renderUrgentBanner();
  setResultState("empty");
  updateProfileStatus();
  showStep(1);
}

function bindEvents() {
  $("#sampleBtn").addEventListener("click", loadSample);
  $("#startBtn").addEventListener("click", startSession);
  $("#collectFaceBtn").addEventListener("click", collectFace);
  $("#skipFaceBtn").addEventListener("click", () => saveFace("skipped"));
  $("#cameraCsvInput").addEventListener("change", handleCameraCsvUpload);
  $("#submitChiefBtn").addEventListener("click", submitChiefComplaint);
  $("#answerBtn").addEventListener("click", submitTenQuestion);
  $("#finishQuestionsBtn").addEventListener("click", runDiagnosis);
  $("#diagnoseBtn").addEventListener("click", runDiagnosis);
  $("#chiefMicBtn").addEventListener("click", () => toggleVoice("#chiefText", "chief"));
  $("#answerMicBtn").addEventListener("click", () => toggleVoice("#answerText", "answer"));
  $("#chiefClearBtn").addEventListener("click", () => clearVoiceInput("#chiefText", "chief"));
  $("#answerClearBtn").addEventListener("click", () => clearVoiceInput("#answerText", "answer"));
  bindSettingsEvents();
  bindAdminEvents();
  bindVirtualKeyboardEvents();

  document.querySelectorAll("[data-chief-chip]").forEach((button) => {
    button.addEventListener("click", () => appendText("#chiefText", button.dataset.chiefChip));
  });
  document.querySelectorAll(".backBtn").forEach((button) => {
    button.addEventListener("click", () => showStep(Math.max(1, state.currentStep - 1)));
  });
  stepItems.forEach((item) => {
    item.addEventListener("click", () => {
      const target = Number(item.dataset.stepJump);
      if (target <= state.furthestStep) showStep(target);
    });
  });
}

function populateRangeSelects() {
  fillRangeSelect("#userAge", "請選擇", 1, 100, 1, "");
  fillRangeSelect("#userHeight", "可略過", 120, 210, 1, " cm");
  fillRangeSelect("#userWeight", "可略過", 30, 160, 1, " kg");
}

function fillRangeSelect(selector, placeholder, min, max, step, suffix) {
  const select = $(selector);
  if (!select || select.options.length) return;
  select.append(new Option(placeholder, ""));
  for (let value = min; value <= max; value += step) {
    select.append(new Option(`${value}${suffix}`, String(value)));
  }
}

async function startSession() {
  clearError();
  resetDiagnosisFlow({ keepChiefText: false });
  state.profile = readProfile();
  if (!state.profile.display_name && !state.profile.age) {
    showError("請至少輸入暱稱或年齡，方便建立本次參考資料。");
    return;
  }
  state.baseline = buildBaseline();
  saveJson(STORAGE_KEYS.profile, state.profile);
  saveJson(STORAGE_KEYS.baseline, state.baseline);
  const payload = {
    profile: state.profile,
    baseline: state.baseline,
    preferred_mode: "auto",
    camera_confidence: 0.8,
    known_user: Boolean(localStorage.getItem(STORAGE_KEYS.profile))
  };
  try {
    const result = await postJson("api/session/start", payload);
    state.sessionId = result.session_id;
    state.mode = result.mode;
    state.userType = result.user_type;
    updateProfileStatus(result);
    showStep(2);
  } catch (error) {
    showError("無法建立本次 session，請確認服務是否正常。");
  }
}

function collectFace() {
  const statuses = [
    ["請靠近一點", "距離：偏遠", "光線：待確認", "位置：待確認", 18],
    ["請稍微離遠一點", "距離：偏近", "光線：良好", "位置：待確認", 38],
    ["請將臉部置中", "距離：適中", "光線：良好", "位置：偏左", 62],
    ["收集中", "距離：適中", "光線：良好", "位置：置中", 84],
    ["收集完成", "距離：適中", "光線：良好", "位置：置中", 100]
  ];
  let index = 0;
  $("#collectFaceBtn").disabled = true;
  const timer = setInterval(() => {
    const [status, distance, lighting, alignment, progress] = statuses[index];
    $("#faceStatus").textContent = status;
    $("#distanceCheck").textContent = distance;
    $("#lightingCheck").textContent = lighting;
    $("#alignmentCheck").textContent = alignment;
    $("#faceProgress").textContent = `${progress}%`;
    const scanMetric = $("#faceScanMetric");
    if (scanMetric) scanMetric.textContent = `${progress}%`;
    $("#faceFrame").style.setProperty("--face-progress", `${progress}%`);
    index += 1;
    if (index >= statuses.length) {
      clearInterval(timer);
      $("#collectFaceBtn").disabled = false;
      $("#faceObservation").value = "本次面部觀察品質良好；系統未保存原始影像。";
      saveFace("complete");
    }
  }, 450);
}

async function saveFace(status) {
  const parsedFace = parseFaceObservationInput();
  state.faceObservation = {
    status,
    baseline_used: parsedFace?.baseline_used ?? state.baseline.status === "ready",
    quality: {
      distance: parsedFace?.quality?.distance || (status === "complete" ? "ok" : "unknown"),
      lighting: parsedFace?.quality?.lighting || (status === "complete" ? "ok" : "unknown"),
      alignment: parsedFace?.quality?.alignment || (status === "complete" ? "centered" : "unknown")
    },
    progress: parsedFace?.progress ?? (status === "complete" ? 100 : 0),
    observation_summary: parsedFace?.observation_summary || $("#faceObservation").value || (status === "skipped" ? "使用者略過面部觀察。" : ""),
    raw_image_stored: false,
    features: parsedFace?.features || (status === "complete" ? { mouth_delta: -0.2, eye_fatigue_delta: 0.05, cheek_delta: -0.1 } : {}),
    roi_signals: Array.isArray(parsedFace?.roi_signals) ? parsedFace.roi_signals : [],
    routing_hints: Array.isArray(parsedFace?.routing_hints) ? parsedFace.routing_hints : []
  };
  if (!state.sessionId) {
    showStep(3);
    return;
  }
  await postJson("api/session/face", { session_id: state.sessionId, face_observation: state.faceObservation });
  showStep(3);
}

async function handleCameraCsvUpload(event) {
  clearError();
  const file = event.target.files && event.target.files[0];
  if (!file) return;
  try {
    const text = await file.text();
    const observation = buildFaceObservationFromFile(text, file.name);
    $("#faceObservation").value = JSON.stringify(observation, null, 2);
    $("#cameraCsvStatus").textContent = `已匯入 ${observation.roi_signals.length} 個 ROI`;
    $("#faceStatus").textContent = "已讀取相機觀察檔";
    $("#faceInstruction").textContent = observation.observation_summary;
    $("#distanceCheck").textContent = "距離：檔案已接收";
    $("#lightingCheck").textContent = "光線：依 CSV brightness 參考";
    $("#alignmentCheck").textContent = "位置：依相機模組結果";
    $("#faceProgress").textContent = "100%";
    $("#faceFrame").style.setProperty("--face-progress", "100%");
  } catch (error) {
    $("#cameraCsvStatus").textContent = "檔案讀取失敗";
    showError("相機觀察檔案無法解析。請使用 CSV、JSON，或包含 ROI / today_redness / baseline_redness / shift / brightness / red_area_ratio / status 的文字報告。");
  } finally {
    event.target.value = "";
  }
}

function parseFaceObservationInput() {
  const text = $("#faceObservation").value.trim();
  if (!text || !text.startsWith("{")) return null;
  try {
    return JSON.parse(text);
  } catch {
    showError("望診 JSON 格式無法解析，將先以文字摘要保存。");
    return null;
  }
}

function buildFaceObservationFromFile(text, fileName) {
  const trimmed = String(text || "").trim();
  const lowerName = String(fileName || "").toLowerCase();
  if (!trimmed) throw new Error("Empty camera file");
  if (lowerName.endsWith(".json") || trimmed.startsWith("{") || trimmed.startsWith("[")) {
    return buildFaceObservationFromJson(JSON.parse(trimmed), fileName);
  }
  if (lowerName.endsWith(".csv") || looksLikeCsv(trimmed)) {
    return buildFaceObservationFromCsv(trimmed, fileName);
  }
  return buildFaceObservationFromText(trimmed, fileName);
}

function buildFaceObservationFromJson(payload, fileName) {
  const source = Array.isArray(payload) ? { roi_signals: payload } : (payload.face_observation || payload);
  const roiSignals = normalizeRoiSignalList(source.roi_signals || source.results || source.signals || source.items || []);
  if (!roiSignals.length) throw new Error("Missing ROI rows");
  const abnormal = abnormalRoiSignals(roiSignals);
  return {
    ...source,
    status: source.status || "complete",
    source: source.source || "camera_json",
    source_file: fileName,
    baseline_used: source.baseline_used ?? roiSignals.some((row) => row.baseline_redness !== null),
    quality: source.quality || { distance: "unknown", lighting: "unknown", alignment: "unknown" },
    progress: source.progress ?? 100,
    observation_summary: source.observation_summary || buildFileObservationSummary(abnormal, "JSON"),
    raw_image_stored: false,
    roi_signals: roiSignals,
    routing_hints: Array.isArray(source.routing_hints) ? source.routing_hints : routingHintsFromRoiSignals(abnormal)
  };
}

function buildFaceObservationFromCsv(text, fileName) {
  const rows = parseCsv(text);
  if (rows.length < 2) throw new Error("CSV is empty");
  const headers = rows[0].map((item) => item.trim());
  const records = rows.slice(1)
    .filter((row) => row.some((cell) => String(cell || "").trim()))
    .map((row) => Object.fromEntries(headers.map((header, index) => [header, row[index] ?? ""])));
  const roiSignals = normalizeRoiSignalList(records);
  if (!roiSignals.length) throw new Error("Missing ROI rows");
  const abnormal = abnormalRoiSignals(roiSignals);
  return {
    status: "complete",
    source: "camera_csv",
    source_file: fileName,
    baseline_used: roiSignals.some((row) => row.baseline_redness !== null),
    quality: { distance: "unknown", lighting: "unknown", alignment: "unknown" },
    progress: 100,
    observation_summary: buildFileObservationSummary(abnormal, "CSV"),
    raw_image_stored: false,
    roi_signals: roiSignals,
    routing_hints: routingHintsFromRoiSignals(abnormal)
  };
}

function buildFaceObservationFromText(text, fileName) {
  const signals = [];
  let current = null;
  String(text || "").replace(/\r/g, "").split("\n").forEach((line) => {
    const trimmed = line.trim();
    if (!trimmed) return;
    const heading = trimmed.match(/^([A-Za-z0-9_ -]+)\s*\/\s*(.+)$/);
    if (heading && !trimmed.includes(":")) {
      if (current) signals.push(current);
      current = { roi_id: heading[1].trim(), meridian: heading[2].trim() };
      return;
    }
    const pair = trimmed.match(/^([A-Za-z_][A-Za-z0-9_ ]*)\s*:\s*(.+)$/);
    if (pair && current) {
      const key = pair[1].trim().toLowerCase().replace(/\s+/g, "_");
      current[key] = pair[2].trim();
    }
  });
  if (current) signals.push(current);
  const roiSignals = normalizeRoiSignalList(signals);
  if (!roiSignals.length) throw new Error("Missing ROI rows");
  const abnormal = abnormalRoiSignals(roiSignals);
  return {
    status: "complete",
    source: "camera_text",
    source_file: fileName,
    baseline_used: roiSignals.some((row) => row.baseline_redness !== null),
    quality: { distance: "unknown", lighting: "unknown", alignment: "unknown" },
    progress: 100,
    observation_summary: buildFileObservationSummary(abnormal, "文字報告"),
    raw_image_stored: false,
    roi_signals: roiSignals,
    routing_hints: routingHintsFromRoiSignals(abnormal)
  };
}

function looksLikeCsv(text) {
  const firstLine = String(text || "").split(/\r?\n/, 1)[0] || "";
  return firstLine.includes(",") && /roi|status|redness|ratio|shift/i.test(firstLine);
}

function normalizeRoiSignalList(source) {
  const rows = Array.isArray(source) ? source : Object.values(source || {});
  return rows.map(normalizeRoiSignal).filter((row) => row.roi_id);
}

function normalizeRoiSignal(row) {
  const value = (keys) => {
    for (const key of keys) {
      if (row[key] !== undefined && row[key] !== null && String(row[key]).trim() !== "") return row[key];
    }
    return "";
  };
  return {
    roi_id: String(value(["roi_id", "roi", "ROI", "id", "meridian_id", "label_en"])).trim(),
    meridian: String(value(["meridian", "meridian_zh", "對應經絡", "經絡", "label", "label_zh"])).trim(),
    area: String(value(["area", "face_area", "臉部位置", "部位"])).trim(),
    today_redness: readCsvNumber(value(["today_redness", "today", "今日紅度"])),
    baseline_redness: readCsvNumber(value(["baseline_redness", "baseline", "基準紅度"])),
    shift: readCsvNumber(value(["shift", "差值"])),
    brightness: readCsvNumber(value(["brightness", "亮度"])),
    red_area_ratio: readCsvNumber(value(["red_area_ratio", "ratio", "紅色比例"])),
    status: String(value(["status", "狀態"]) || "normal").trim() || "normal"
  };
}

function abnormalRoiSignals(signals) {
  return signals.filter((row) => ["slight_redness", "obvious_redness"].includes(row.status));
}

function parseCsv(text) {
  const rows = [];
  let row = [];
  let cell = "";
  let quoted = false;
  const source = text.replace(/^\uFEFF/, "");
  for (let index = 0; index < source.length; index += 1) {
    const char = source[index];
    const next = source[index + 1];
    if (char === '"' && quoted && next === '"') {
      cell += '"';
      index += 1;
    } else if (char === '"') {
      quoted = !quoted;
    } else if (char === "," && !quoted) {
      row.push(cell);
      cell = "";
    } else if ((char === "\n" || char === "\r") && !quoted) {
      if (char === "\r" && next === "\n") index += 1;
      row.push(cell);
      rows.push(row);
      row = [];
      cell = "";
    } else {
      cell += char;
    }
  }
  if (cell || row.length) {
    row.push(cell);
    rows.push(row);
  }
  return rows;
}

function readCsvNumber(value) {
  const number = Number(value);
  return Number.isFinite(number) ? number : null;
}

function buildFileObservationSummary(abnormal, sourceLabel = "檔案") {
  if (!abnormal.length) return `相機${sourceLabel}已讀取，未見明顯局部紅色比例偏高的 ROI。`;
  const labels = abnormal.map((item) => `${item.meridian || item.roi_id} ${item.status}`).join("、");
  return `相機${sourceLabel}已讀取，${labels}，系統會將其作為問診追問方向提示。`;
}

function routingHintsFromRoiSignals(signals) {
  const hints = [];
  signals.forEach((signal) => {
    const id = String(signal.roi_id || "").toLowerCase();
    const meridian = String(signal.meridian || "");
    if (id.includes("stomach") || id.startsWith("st_") || meridian.includes("胃")) hints.push("digestive", "mouth", "diet_stimulation");
    if (id.includes("conception") || id.startsWith("cv_") || meridian.includes("任脈")) hints.push("mouth_chin", "sleep_stress", "fatigue");
    if (id.includes("spleen") || id.startsWith("sp_") || meridian.includes("脾")) hints.push("digestive", "fatigue");
    if (id.includes("liver") || id.startsWith("lr_") || meridian.includes("肝")) hints.push("sleep", "emotion", "eye_fatigue");
    if (id.includes("kidney") || id.startsWith("ki_") || meridian.includes("腎")) hints.push("fatigue", "sleep");
  });
  return Array.from(new Set(hints));
}

async function submitChiefComplaint() {
  clearError();
  const text = $("#chiefText").value.trim();
  if (!text) {
    showError("請先描述最主要的不適。");
    return;
  }
  resetDiagnosisFlow({ keepChiefText: true });
  state.chiefComplaint = { text, input_method: "text" };
  try {
    const result = await postJson("api/session/chief-complaint", {
      session_id: state.sessionId,
      chief_complaint: state.chiefComplaint
    });
    state.symptoms = result.current_symptoms || [];
    refreshSafetyState();
    if (result.next_action === "ready_to_diagnose") {
      if (!hasImmediateSafetyFlag()) {
        showError("主訴整理完成，接下來需要完成十問詳問，不能只憑主訴直接產生結果。");
        if (result.question) {
          renderQuestion(result.question, result.progress);
          showStep(4);
        }
        return;
      }
      await runDiagnosis();
      return;
    }
    renderQuestion(result.question, result.progress);
    showStep(4);
  } catch (error) {
    showError("整理主訴時發生問題，請稍後再試。");
  }
}

async function submitTenQuestion() {
  if (state.isSubmittingAnswer) return;
  if (!state.currentQuestion) {
    if (!canFinishQuestionFlow()) {
      showError(`目前只完成 ${state.tenQuestions.length} 題。請先繼續完成十問詳問，再產生結果。`);
      updateFinishButton();
      return;
    }
    await runDiagnosis();
    return;
  }
  const selected = Array.from(document.querySelectorAll("#quickAnswerPanel .quick-chip.is-selected")).map((button) => button.dataset.value);
  const freeText = $("#answerText").value.trim();
  if (!freeText && !selected.length) {
    showError("請先用語音或文字回答本題，再送出。");
    return;
  }
  if (state.tenQuestions.some((item) => item.question_id === state.currentQuestion.id)) {
    showError("這一題已經送出，系統正在切換下一題，請稍等。");
    return;
  }
  clearError();
  state.isSubmittingAnswer = true;
  setAnswerSubmitting(true);
  const answer = {
    question_id: state.currentQuestion.id,
    category: state.currentQuestion.category,
    question: state.currentQuestion.question,
    answer_type: state.currentQuestion.answer_type,
    selected_options: selected,
    free_text: freeText,
    input_method: freeText ? "text" : "choice"
  };
  state.tenQuestions.push(answer);
  renderAnswerHistory();
  try {
    const result = await postJson("api/session/ten-question", {
      session_id: state.sessionId,
      answer
    });
    state.symptoms = result.current_symptoms || state.symptoms;
    refreshSafetyState();
    resetCurrentAnswerInput();
    if (result.next_action === "ready_to_diagnose") {
      if (!canFinishQuestionFlow() && !hasImmediateSafetyFlag()) {
        showError(`目前只完成 ${state.tenQuestions.length} 題。系統會繼續追問，至少完成 ${minimumQuestionCount()} 題後才產生結果。`);
        if (result.question) renderQuestion(result.question, result.progress);
        updateFinishButton();
        return;
      }
      await runDiagnosis();
      return;
    }
    renderQuestion(result.question, result.progress);
  } catch (error) {
    state.tenQuestions = state.tenQuestions.filter((item) => item !== answer);
    renderAnswerHistory();
    showError("送出回答時發生問題，請稍後再試。");
  } finally {
    state.isSubmittingAnswer = false;
    setAnswerSubmitting(false);
  }
}

async function runDiagnosis() {
  if (state.currentStep === 4 && !canFinishQuestionFlow()) {
    const minimum = minimumQuestionCount();
    showError(`目前只完成 ${state.tenQuestions.length} 題。為了讓判斷更可靠，請至少完成 ${minimum} 題十問詳問。`);
    updateFinishButton();
    return;
  }
  refreshSafetyState();
  if (state.redFlagActive && !state.urgentAcknowledged) {
    showStep(4);
    showError("資料中出現安全警訊。請先確認上方安全提醒；若正在發生胸痛、呼吸困難、意識不清或症狀快速惡化，請立即就醫。");
    updateFinishButton();
    return;
  }
  showStep(5);
  setResultState("loading");
  try {
    const payload = {
      session_id: state.sessionId,
      mode: state.mode,
      profile: state.profile,
      baseline: state.baseline,
      face_observation: state.faceObservation,
      chief_complaint: state.chiefComplaint,
      ten_questions: state.tenQuestions,
      symptoms: state.symptoms
    };
    const result = await postJson("api/diagnose", payload);
    renderResult(result);
    saveFollowUp(result);
    setResultState("result");
  } catch (error) {
    setResultState("error");
  }
}

function renderQuestion(question, progress) {
  resetCurrentAnswerInput();
  renderAnswerHistory();
  if (!question) {
    state.currentQuestion = null;
    $("#questionCategory").textContent = categoryLabel("");
    const reason = $("#questionReason");
    if (reason) {
      reason.textContent = "";
      reason.hidden = true;
    }
    $("#questionBox").textContent = canFinishQuestionFlow()
      ? "已完成必要問題，可以產生參考結果。"
      : "還需要更多問診資料，請稍後再試。";
    $("#questionProgress").textContent = progressText();
    updateFinishButton();
    return;
  }
  state.currentQuestion = question;
  $("#questionCategory").textContent = categoryLabel(question.category);
  const reason = $("#questionReason");
  if (reason) {
    reason.textContent = question.reason_label || "";
    reason.hidden = !question.reason_label;
  }
  $("#questionBox").textContent = question.question;
  $("#questionProgress").textContent = progressText();
  renderQuickAnswers(question);
  updateFinishButton();
}

function renderQuickAnswers(question) {
  const panel = $("#quickAnswerPanel");
  if (!panel) return;
  panel.innerHTML = "";
  const options = Array.isArray(question.options) ? question.options : [];
  const type = question.answer_type || "free_text";
  if (!options.length || type === "free_text") {
    panel.hidden = true;
    return;
  }
  const title = document.createElement("span");
  title.className = "quick-title";
  title.textContent = type === "scale" ? "可直接選擇分數，也可用語音補充" : "可點選符合的選項，也可用語音補充";
  const choices = document.createElement("div");
  choices.className = type === "scale" ? "quick-scale" : "quick-choices";
  options.forEach((option) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "quick-chip";
    button.dataset.value = String(option);
    button.textContent = String(option);
    button.addEventListener("click", () => toggleQuickAnswer(button, type));
    choices.append(button);
  });
  panel.append(title, choices);
  panel.hidden = false;
}

function toggleQuickAnswer(button, type) {
  if (type === "single_choice" || type === "scale") {
    button.closest("#quickAnswerPanel").querySelectorAll(".quick-chip").forEach((item) => {
      item.classList.toggle("is-selected", item === button && !button.classList.contains("is-selected"));
    });
    return;
  }
  button.classList.toggle("is-selected");
}

function renderAnswerHistory() {
  const container = $("#answerHistory");
  if (!container) return;
  container.hidden = state.tenQuestions.length === 0;
  if (container.hidden) return;
  const summary = $("#answerHistorySummary");
  const list = $("#answerHistoryList");
  summary.textContent = `已回答 ${state.tenQuestions.length} 題，點此查看`;
  list.innerHTML = "";
  state.tenQuestions.forEach((item, index) => {
    const row = document.createElement("li");
    const question = document.createElement("strong");
    question.textContent = `${index + 1}. ${item.question}`;
    const answer = document.createElement("span");
    answer.textContent = item.free_text || (item.selected_options || []).join("、") || "已回答";
    row.append(question, answer);
    list.append(row);
  });
}

function progressText() {
  const total = minimumQuestionCount();
  const current = Math.min(state.tenQuestions.length + 1, total);
  return canFinishQuestionFlow()
    ? `已完成 ${state.tenQuestions.length} / ${total} 題，可產生結果`
    : `第 ${current} / ${total} 題`;
}

function resetCurrentAnswerInput() {
  if (state.recognitionTarget === "#answerText") stopVoice();
  const field = $("#answerText");
  if (field) field.value = "";
  state.recordingBaseText = "";
  if (state.recognitionTarget === "#answerText") {
    state.recognitionTarget = null;
    state.recognitionGroup = null;
  }
  const status = $("#answerVoiceStatus");
  if (status) status.textContent = "這是本題的獨立回答框；送出後會保存到上方紀錄。";
}

function resetDiagnosisFlow({ keepChiefText = false } = {}) {
  if (state.isRecording) stopVoice();
  state.faceObservation = null;
  state.chiefComplaint = null;
  state.currentQuestion = null;
  state.tenQuestions = [];
  state.symptoms = [];
  state.isSubmittingAnswer = false;
  state.recordingBaseText = "";
  state.voiceStartedAt = 0;
  state.voiceLastSoundAt = 0;
  state.voiceDetected = false;
  state.voiceAutoStopping = false;
  state.redFlagActive = false;
  state.urgentAcknowledged = false;
  state.recognitionTarget = null;
  state.recognitionGroup = null;
  if (!keepChiefText) {
    const chiefText = $("#chiefText");
    if (chiefText) chiefText.value = "";
  }
  const answerText = $("#answerText");
  if (answerText) answerText.value = "";
  const faceObservation = $("#faceObservation");
  if (faceObservation) faceObservation.value = "";
  renderAnswerHistory();
  updateFinishButton();
  setAnswerSubmitting(false);
  renderUrgentBanner();
  setResultState("empty");
}

function renderResult(result) {
  $("#reportId").textContent = buildReportId();
  $("#reportTime").textContent = new Date().toLocaleString("zh-Hant-TW", { hour12: false });
  $("#profileSummary").textContent = buildProfileSummary();
  $("#disclaimer").textContent = result.medical_disclaimer || "結果只具有參考作用，不能取代醫師診斷。";
  $("#reportSummary").textContent = cleanPublicText(result.report_summary || result.preliminary_assessment || "-");
  renderList("#carePlan", result.care_plan || []);
  renderList("#watchItems", result.watch_items || []);
  renderList("#selfCheckQuestions", result.self_check_questions || []);
  renderList("#seekCareIf", result.seek_care_if || []);
  const list = $("#possibilityList");
  list.innerHTML = "";
  const possibilities = result.possibilities && result.possibilities.length
    ? result.possibilities
    : [{
        pattern: result.preliminary_assessment || "需要更多資料",
        fit_percent: result.possibility_level === "高" ? 82 : result.possibility_level === "中" ? 60 : 35,
        level: result.possibility_level || "低",
        tcm_explanation: "",
        plain_explanation: result.supporting_evidence || "",
        evidence: result.supporting_evidence ? [result.supporting_evidence] : [],
        lifestyle_suggestion: "",
        dietary_suggestion: result.dietary_suggestion || ""
      }];
  possibilities.slice(0, 3).forEach((item, index) => list.append(renderPossibility(item, index)));
}

function renderPossibility(item, index) {
  const article = document.createElement("article");
  article.className = "possibility-card";
  article.dataset.rank = String(index + 1);
  const evidence = Array.isArray(item.evidence) && item.evidence.length ? item.evidence : ["目前資料仍需補充，建議搭配後續觀察。"];
  const fitPercent = Math.max(0, Math.min(100, Number(item.fit_percent || 0)));
  const detailsId = `possibility-details-${index + 1}`;
  const summary = item.plain_explanation || item.tcm_explanation || "點開查看本傾向的依據、說明與日常建議。";
  article.innerHTML = `
    <button class="possibility-toggle" type="button" aria-expanded="false" aria-controls="${detailsId}">
      <span class="possibility-rank">可能性 ${index + 1}</span>
      <span class="possibility-title">${escapeHtml(item.pattern || "需要更多資料")}</span>
      <span class="possibility-percent">${fitPercent}%</span>
      <span class="possibility-summary">${escapeHtml(truncateText(summary, 58))}</span>
      <span class="progress-track"><i style="width:${fitPercent}%"></i></span>
      <span class="toggle-hint">查看詳細</span>
    </button>
    <div id="${detailsId}" class="possibility-details" hidden>
      <div class="result-two-col">
        <section>
          <span class="report-label">中醫角度</span>
          <p>${escapeHtml(item.tcm_explanation || "目前資料較少，暫以已填寫的症狀傾向做初步整理。")}</p>
        </section>
        <section>
          <span class="report-label">現代語言說明</span>
          <p>${escapeHtml(item.plain_explanation || "這代表身體狀態可能有某些失衡訊號，但仍需結合專業面診與持續觀察。")}</p>
        </section>
      </div>
      <span class="report-label">支持依據</span>
      <div class="evidence-list">${evidence.map((text) => `<em>${escapeHtml(text)}</em>`).join("")}</div>
      <div class="result-two-col guidance-row">
        <section>
          <span class="report-label">生活建議</span>
          <p>${escapeHtml(item.lifestyle_suggestion || "先維持規律作息，避免過度勞累，觀察症狀是否隨休息、飲食與壓力變化。")}</p>
        </section>
        <section>
          <span class="report-label">飲食方向</span>
          <p>${escapeHtml(item.dietary_suggestion || "以清淡、溫和、易消化的日常食物為主，暫時減少油膩、冰冷與刺激性飲食。")}</p>
        </section>
      </div>
      ${renderMiniList("可做的事", item.care_plan)}
    </div>
  `;
  const toggle = article.querySelector(".possibility-toggle");
  const details = article.querySelector(".possibility-details");
  toggle.addEventListener("click", () => {
    const expanded = toggle.getAttribute("aria-expanded") === "true";
    toggle.setAttribute("aria-expanded", String(!expanded));
    details.hidden = expanded;
    toggle.querySelector(".toggle-hint").textContent = expanded ? "查看詳細" : "收起詳細";
  });
  return article;
}

function renderList(selector, items) {
  const list = $(selector);
  list.innerHTML = "";
  const safeItems = Array.isArray(items) && items.length ? items : ["目前資料不足，建議持續觀察並補充症狀變化。"];
  safeItems.forEach((item) => {
    const li = document.createElement("li");
    li.textContent = cleanPublicText(item);
    list.append(li);
  });
}

function renderMiniList(title, items) {
  if (!Array.isArray(items) || !items.length) return "";
  return `<div class="mini-guidance"><span>${escapeHtml(title)}</span><ul>${items.slice(0, 3).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></div>`;
}

function truncateText(value, maxLength) {
  const text = String(value || "").trim();
  return text.length > maxLength ? `${text.slice(0, maxLength)}…` : text;
}

function setupSpeechRecognition() {
  state.webSpeechSupported = Boolean(window.SpeechRecognition || window.webkitSpeechRecognition);
  state.localRecorderSupported = Boolean(
    window.isSecureContext &&
    navigator.mediaDevices &&
    navigator.mediaDevices.getUserMedia &&
    (window.AudioContext || window.webkitAudioContext)
  );
  if (!window.isSecureContext) {
    setVoiceUnsupported(insecureVoiceMessage());
    return;
  }
  if (!state.webSpeechSupported && !state.localRecorderSupported) {
    setVoiceUnsupported("此瀏覽器無法錄音，請確認瀏覽器版本、麥克風權限，或改用文字輸入。");
    return;
  }
  setVoiceReadyStatus();
}

function insecureVoiceMessage() {
  const host = window.location.hostname || "";
  const isLocalhost = host === "localhost" || host === "127.0.0.1" || host === "::1";
  if (isLocalhost) {
    return "目前連線不支援錄音。請重新整理頁面，或確認瀏覽器允許麥克風。";
  }
  return `錄音需要安全連線。從筆電連 Raspberry Pi 時，請改用 https://${host}/ 並在瀏覽器允許麥克風。`;
}

async function toggleVoice(target, group) {
  if (state.isRecording && state.recognitionTarget === target) {
    await stopVoice();
    return;
  }
  if (!window.isSecureContext) {
    showError(insecureVoiceMessage());
    return;
  }
  if (state.isRecording) await stopVoice({ discard: true });
  const engine = selectVoiceEngine();
  if (!engine) return;
  state.recognitionTarget = target;
  state.recognitionGroup = group;
  state.recordingBaseText = $(target).value.trim();
  state.voiceHadResult = false;
  state.audioChunks = [];
  state.webFinalTranscript = "";
  state.webInterimTranscript = "";
  state.webSpeechError = "";
  state.voiceStartedAt = performance.now();
  state.voiceLastSoundAt = state.voiceStartedAt;
  state.voiceDetected = false;
  state.voiceAutoStopping = false;
  state.voiceEngine = engine;
  state.isRecording = true;
  updateVoiceUi();
  try {
    if (engine === "web") {
      startWebSpeechRecognition();
    } else {
      await startLocalRecording();
    }
  } catch (error) {
    await stopVoice({ keepStatus: true, discard: true });
    const status = group === "chief" ? $("#chiefVoiceStatus") : $("#answerVoiceStatus");
    status.textContent = `錄音啟動失敗：${microphoneErrorMessage(error)}。`;
  }
}

function selectVoiceEngine() {
  const config = currentSpeechConfig();
  const onlineMode = isOnlineSpeechEnabled();
  if (!state.localRecorderSupported) {
    showError("目前無法啟動錄音。請確認瀏覽器麥克風權限、HTTPS/localhost，或改用文字輸入。");
    return null;
  }
  if (onlineMode && navigator.onLine === false) {
    showError("目前設定為線上 Google Cloud 語音辨識，但網路顯示離線。請連線後再試，或在設定手動切換離線 Vosk。");
    return null;
  }
  if (config.language === "hokkien" && !onlineMode) {
    showError("台語 / 閩南語目前沒有可靠的離線模型；請改用華語或切回線上模式。");
    return null;
  }
  return "local";
}

function currentSpeechConfig() {
  const language = state.settings.speechLanguage || "mandarin";
  return {
    language,
    speechLang: "zh-TW",
    label: language === "hokkien" ? "台語 / 閩南語（實驗）" : "華語 / 中文"
  };
}

function startWebSpeechRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) throw new Error("SpeechRecognition unavailable");
  const config = currentSpeechConfig();
  const recognition = new SpeechRecognition();
  state.webRecognition = recognition;
  recognition.lang = config.speechLang;
  recognition.interimResults = true;
  recognition.continuous = true;
  recognition.maxAlternatives = 3;
  recognition.onresult = (event) => {
    let interim = "";
    for (let index = event.resultIndex; index < event.results.length; index += 1) {
      const transcript = bestSpeechAlternative(event.results[index]);
      if (event.results[index].isFinal) state.webFinalTranscript += transcript;
      else interim += transcript;
    }
    state.webInterimTranscript = interim;
    state.voiceHadResult = Boolean(state.webFinalTranscript || state.webInterimTranscript);
    state.voiceDetected = true;
    state.voiceLastSoundAt = performance.now();
    scheduleWebSpeechAutoStop();
    const status = activeVoiceStatus();
    if (status) {
      status.textContent = interim
        ? `正在辨識：${normalizeTranscript(interim)}`
        : "正在辨識語音，請說完後再按一次停止或稍等自動結束。";
    }
  };
  recognition.onerror = (event) => {
    state.webSpeechError = event.error || "unknown";
  };
  recognition.onend = () => handleWebSpeechEnd();
  recognition.start();
}

function bestSpeechAlternative(result) {
  if (!result || !result.length) return "";
  let best = result[0];
  for (let index = 1; index < result.length; index += 1) {
    const candidate = result[index];
    if ((candidate?.confidence || 0) > (best?.confidence || 0)) best = candidate;
  }
  return best?.transcript || "";
}

function scheduleWebSpeechAutoStop() {
  clearVoiceNoResultTimer();
  state.voiceNoResultTimer = setTimeout(() => {
    if (state.isRecording && state.voiceEngine === "web" && state.voiceHadResult) {
      requestAutoStopVoice();
    }
  }, 950);
}

async function handleWebSpeechEnd() {
  if (state.voiceEngine !== "web") return;
  const status = activeVoiceStatus();
  clearVoiceNoResultTimer();
  const finalText = normalizeTranscript(state.webFinalTranscript || state.webInterimTranscript);
  state.isRecording = false;
  state.voiceEngine = null;
  state.webRecognition = null;
  updateVoiceUi();
  if (finalText) {
    appendTranscribedText(finalText);
    if (status) status.textContent = "語音已轉成文字，可檢查後送出。";
  } else if (status) {
    status.textContent = state.webSpeechError ? voiceErrorMessage(state.webSpeechError) : "未辨識到語音，請再試一次或直接輸入文字。";
  }
  state.webFinalTranscript = "";
  state.webInterimTranscript = "";
  state.webSpeechError = "";
}

async function startLocalRecording() {
  const AudioContext = window.AudioContext || window.webkitAudioContext;
  state.audioStream = await navigator.mediaDevices.getUserMedia({
    audio: {
      echoCancellation: true,
      noiseSuppression: true,
      autoGainControl: true
    }
  });
  state.audioContext = new AudioContext();
  state.audioSampleRate = state.audioContext.sampleRate;
  state.audioSource = state.audioContext.createMediaStreamSource(state.audioStream);
  state.audioProcessor = state.audioContext.createScriptProcessor(4096, 1, 1);
  state.audioProcessor.onaudioprocess = (event) => {
    if (!state.isRecording) return;
    const input = event.inputBuffer.getChannelData(0);
    state.audioChunks.push(new Float32Array(input));
    state.voiceHadResult = true;
    handleVoiceActivity(input);
  };
  state.audioSource.connect(state.audioProcessor);
  state.audioProcessor.connect(state.audioContext.destination);
}

function handleVoiceActivity(input) {
  const now = performance.now();
  const elapsed = now - state.voiceStartedAt;
  const rms = audioRms(input);
  if (rms >= 0.016) {
    state.voiceDetected = true;
    state.voiceLastSoundAt = now;
  }
  if (state.voiceAutoStopping) return;
  if (state.voiceDetected && elapsed >= 900 && now - state.voiceLastSoundAt >= 1300) {
    requestAutoStopVoice();
    return;
  }
  if (elapsed >= 24000) {
    requestAutoStopVoice();
  }
}

function audioRms(input) {
  if (!input.length) return 0;
  let sum = 0;
  for (let index = 0; index < input.length; index += 1) {
    sum += input[index] * input[index];
  }
  return Math.sqrt(sum / input.length);
}

function requestAutoStopVoice() {
  state.voiceAutoStopping = true;
  const status = activeVoiceStatus();
  if (status) status.textContent = "已偵測到停頓，正在停止錄音並轉成文字...";
  setTimeout(() => {
    if (state.isRecording) stopVoice();
  }, 0);
}

async function stopVoice({ keepStatus = false, discard = false } = {}) {
  if (!state.recognition && !state.isRecording) return;
  if (state.voiceEngine === "web") {
    const recognition = state.webRecognition;
    clearVoiceNoResultTimer();
    if (discard) {
      state.webFinalTranscript = "";
      state.webInterimTranscript = "";
      state.isRecording = false;
      state.voiceEngine = null;
      state.webRecognition = null;
      if (recognition) {
        try { recognition.abort(); } catch {}
      }
      if (!keepStatus) updateVoiceUi();
      return;
    }
    if (recognition) {
      try {
        recognition.stop();
      } catch {
        state.isRecording = false;
        state.voiceEngine = null;
        state.webRecognition = null;
        updateVoiceUi();
      }
    } else {
      state.isRecording = false;
      state.voiceEngine = null;
      updateVoiceUi();
    }
    return;
  }
  state.isRecording = false;
  state.voiceAutoStopping = false;
  clearVoiceNoResultTimer();
  stopAudioGraph();
  if (keepStatus) updateVoiceButtonsOnly();
  else updateVoiceUi();
  if (!discard && state.audioChunks.length) {
    await transcribeCurrentRecording();
  }
  state.audioChunks = [];
  state.voiceEngine = null;
}

function stopAudioGraph() {
  if (state.audioProcessor) {
    state.audioProcessor.disconnect();
    state.audioProcessor.onaudioprocess = null;
  }
  if (state.audioSource) state.audioSource.disconnect();
  if (state.audioStream) state.audioStream.getTracks().forEach((track) => track.stop());
  if (state.audioContext) state.audioContext.close().catch(() => {});
  state.audioProcessor = null;
  state.audioSource = null;
  state.audioStream = null;
  state.audioContext = null;
}

async function transcribeCurrentRecording() {
  const status = activeVoiceStatus();
  if (status) status.textContent = "錄音已收到，正在轉成文字...";
  try {
    const wavBlob = encodeWavBlob(state.audioChunks, state.audioSampleRate, 16000);
    const formData = new FormData();
    formData.append("audio", wavBlob, "voice-input.wav");
    formData.append("group", state.recognitionGroup || "");
    formData.append("language", state.settings.speechLanguage || "mandarin");
    formData.append("engine", currentSpeechMode() === "offline" ? "offline" : "google");
    const response = await fetch(appUrl("api/audio/transcribe"), {
      method: "POST",
      body: formData
    });
    const result = await response.json();
    if (result.ok && result.transcript) {
      appendTranscribedText(result.transcript);
      if (status) status.textContent = "語音已轉成文字，可檢查後送出。";
    } else if (status) {
      const message = result.message || "已收到錄音，但目前尚未完成語音轉文字。";
      status.textContent = result.status === "missing_model"
        ? `${message} 麥克風已可使用；若要自動變成文字，請在 Pi 設定離線語音模型 VOSK_MODEL_PATH。`
        : message;
    }
  } catch (error) {
    if (status) status.textContent = "錄音已停止，但送往語音辨識時發生問題，請改用文字輸入。";
  }
}

function appendTranscribedText(text) {
  if (!state.recognitionTarget) return;
  const input = $(state.recognitionTarget);
  const joined = [state.recordingBaseText, normalizeTranscript(text)].filter(Boolean).join(" ").trim();
  input.value = joined;
  state.recordingBaseText = joined;
}

function normalizeTranscript(text) {
  let normalized = String(text || "").replace(/\s+/g, "").trim();
  const replacements = {
    "头痛": "頭痛",
    "头晕": "頭暈",
    "头重": "頭重",
    "发烧": "發燒",
    "发热": "發熱",
    "怕热": "怕熱",
    "口干": "口乾",
    "嘴干": "嘴乾",
    "喉咙": "喉嚨",
    "恶心": "噁心",
    "呕吐": "嘔吐",
    "腹泻": "腹瀉",
    "肚子胀": "肚子脹",
    "胃胀": "胃脹",
    "没力": "沒力",
    "无力": "無力",
    "身体": "身體",
    "睡觉": "睡覺",
    "盗汗": "盜汗",
    "脸": "臉",
    "经痛": "經痛",
    "月经": "月經",
    "腹胀": "腹脹",
    "拉肚子": "腹瀉",
    "食欲": "食慾",
    "胸闷": "胸悶",
    "气短": "氣短",
    "呼吸困难": "呼吸困難",
    "喉咙痛": "喉嚨痛",
    "牙龈": "牙齦",
    "压力": "壓力",
    "哪里": "哪裡",
    "这里": "這裡",
    "那里": "那裡",
    "症状": "症狀",
    "厉害": "厲害",
    "持续": "持續",
    "发冷": "發冷",
    "发麻": "發麻",
    "发炎": "發炎",
    "尿频": "尿頻",
    "颜色": "顏色",
    "抑郁": "抑鬱",
    "焦虑": "焦慮",
    "烦躁": "煩躁",
    "做梦": "做夢",
    "线上": "線上",
    "语音": "語音",
    "识别": "辨識"
  };
  Object.entries(replacements).forEach(([from, to]) => {
    normalized = normalized.replaceAll(from, to);
  });
  const charMap = {
    "头": "頭", "晕": "暈", "发": "發", "热": "熱", "干": "乾",
    "咙": "嚨", "恶": "噁", "呕": "嘔", "泻": "瀉", "胀": "脹",
    "没": "沒", "无": "無", "体": "體", "觉": "覺", "盗": "盜",
    "脸": "臉", "经": "經", "闷": "悶", "气": "氣", "难": "難",
    "压": "壓", "药": "藥", "医": "醫", "疗": "療", "诊": "診",
    "问": "問", "个": "個", "么": "麼", "为": "為", "会": "會",
    "时": "時", "间": "間", "长": "長", "过": "過", "还": "還",
    "轻": "輕", "对": "對", "开": "開", "关": "關", "状": "狀",
    "紧": "緊", "张": "張", "虑": "慮", "郁": "鬱", "湿": "濕",
    "虚": "虛", "风": "風", "阳": "陽", "阴": "陰", "痒": "癢",
    "软": "軟", "厉": "厲", "频": "頻", "黄": "黃", "红": "紅",
    "肿": "腫", "劳": "勞", "烦": "煩", "梦": "夢", "质": "質",
    "涩": "澀", "颜": "顏", "这": "這", "吗": "嗎", "裡": "裡", "语": "語",
    "识": "識", "线": "線"
  };
  normalized = Array.from(normalized).map((char) => charMap[char] || char).join("");
  return normalized;
}

function encodeWavBlob(chunks, sourceRate, targetRate) {
  const samples = mergeAudioChunks(chunks);
  const resampled = resampleLinear(samples, sourceRate, targetRate);
  const buffer = new ArrayBuffer(44 + resampled.length * 2);
  const view = new DataView(buffer);
  writeString(view, 0, "RIFF");
  view.setUint32(4, 36 + resampled.length * 2, true);
  writeString(view, 8, "WAVE");
  writeString(view, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, targetRate, true);
  view.setUint32(28, targetRate * 2, true);
  view.setUint16(32, 2, true);
  view.setUint16(34, 16, true);
  writeString(view, 36, "data");
  view.setUint32(40, resampled.length * 2, true);
  floatTo16BitPcm(view, 44, resampled);
  return new Blob([view], { type: "audio/wav" });
}

function mergeAudioChunks(chunks) {
  const length = chunks.reduce((total, chunk) => total + chunk.length, 0);
  const result = new Float32Array(length);
  let offset = 0;
  chunks.forEach((chunk) => {
    result.set(chunk, offset);
    offset += chunk.length;
  });
  return result;
}

function resampleLinear(samples, sourceRate, targetRate) {
  if (sourceRate === targetRate) return samples;
  const ratio = sourceRate / targetRate;
  const newLength = Math.round(samples.length / ratio);
  const result = new Float32Array(newLength);
  for (let index = 0; index < newLength; index += 1) {
    const position = index * ratio;
    const left = Math.floor(position);
    const right = Math.min(left + 1, samples.length - 1);
    const weight = position - left;
    result[index] = samples[left] * (1 - weight) + samples[right] * weight;
  }
  return result;
}

function floatTo16BitPcm(view, offset, samples) {
  for (let index = 0; index < samples.length; index += 1, offset += 2) {
    const sample = Math.max(-1, Math.min(1, samples[index]));
    view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
  }
}

function writeString(view, offset, text) {
  for (let index = 0; index < text.length; index += 1) {
    view.setUint8(offset + index, text.charCodeAt(index));
  }
}

function microphoneErrorMessage(error) {
  if (error && error.name === "NotAllowedError") return "麥克風權限被拒絕，請在網址列的網站設定允許麥克風";
  if (error && error.name === "NotFoundError") return "找不到可用麥克風，請確認 USB mic 已連接";
  if (error && error.name === "NotReadableError") return "麥克風被其他程式占用，請關閉其他錄音程式";
  return "請確認麥克風、瀏覽器權限與 HTTPS/localhost";
}

function clearVoiceInput(target, group) {
  if (state.recognitionTarget === target) stopVoice({ discard: true });
  $(target).value = "";
  state.recordingBaseText = "";
  const status = group === "chief" ? $("#chiefVoiceStatus") : $("#answerVoiceStatus");
  status.textContent = group === "chief" ? "已清除，可重新錄音描述主訴。" : "已清除，可重新錄音回答本題。";
}

function bindVirtualKeyboardEvents() {
  const keyboard = $("#virtualKeyboard");
  if (!keyboard) return;
  const editableSelector = "#chiefText, #answerText, #displayName";
  document.addEventListener("focusin", (event) => {
    if (event.target.matches(editableSelector)) showVirtualKeyboard(event.target);
  });
  document.addEventListener("pointerdown", (event) => {
    if (event.target.matches(editableSelector)) showVirtualKeyboard(event.target);
  });
  $("#keyboardCloseBtn").addEventListener("click", hideVirtualKeyboard);
  keyboard.addEventListener("pointerdown", (event) => {
    if (event.target.closest("button")) event.preventDefault();
  });
  keyboard.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-vkey-text], button[data-vkey-action]");
    if (button) handleVirtualKey(button);
  });
}

function showVirtualKeyboard(target) {
  if (!target || target.hidden || target.disabled || target.readOnly) return;
  state.keyboardTarget = target;
  const keyboard = $("#virtualKeyboard");
  const label = $("#keyboardTargetLabel");
  if (label) label.textContent = target.id === "chiefText" ? "編輯主訴" : target.id === "answerText" ? "編輯本題回答" : "輸入姓名 / 暱稱";
  renderVirtualKeyboard(target);
  keyboard.hidden = false;
  document.body.classList.add("has-virtual-keyboard");
  setTimeout(() => target.scrollIntoView({ block: "center", behavior: "smooth" }), 20);
}

function hideVirtualKeyboard() {
  const keyboard = $("#virtualKeyboard");
  if (!keyboard) return;
  keyboard.hidden = true;
  document.body.classList.remove("has-virtual-keyboard");
  state.keyboardTarget = null;
}

function handleVirtualKey(button) {
  const target = state.keyboardTarget;
  if (!target) return;
  const action = button.dataset.vkeyAction;
  if (action === "backspace") {
    deleteVirtualKeyboardSelection(target);
  } else if (action === "clear") {
    target.value = "";
  } else if (action === "space") {
    insertVirtualKeyboardText(target, " ");
  } else if (action === "newline") {
    insertVirtualKeyboardText(target, "\n");
  } else if (action === "done") {
    hideVirtualKeyboard();
    return;
  } else {
    const text = button.dataset.vkeyText || "";
    insertVirtualKeyboardText(target, text);
  }
  target.focus({ preventScroll: true });
  target.dispatchEvent(new Event("input", { bubbles: true }));
}

function insertVirtualKeyboardText(target, text) {
  const start = Number.isFinite(target.selectionStart) ? target.selectionStart : target.value.length;
  const end = Number.isFinite(target.selectionEnd) ? target.selectionEnd : target.value.length;
  const spacer = shouldAddKeyboardSpacer(target, text, start) ? "，" : "";
  target.value = `${target.value.slice(0, start)}${spacer}${text}${target.value.slice(end)}`;
  const caret = start + spacer.length + text.length;
  target.setSelectionRange(caret, caret);
}

function deleteVirtualKeyboardSelection(target) {
  const start = Number.isFinite(target.selectionStart) ? target.selectionStart : target.value.length;
  const end = Number.isFinite(target.selectionEnd) ? target.selectionEnd : target.value.length;
  if (start !== end) {
    target.value = `${target.value.slice(0, start)}${target.value.slice(end)}`;
    target.setSelectionRange(start, start);
    return;
  }
  if (start <= 0) return;
  target.value = `${target.value.slice(0, start - 1)}${target.value.slice(start)}`;
  target.setSelectionRange(start - 1, start - 1);
}

function shouldAddKeyboardSpacer(target, text, start) {
  if (!text || text.length <= 1 || target.id === "displayName" || start === 0) return false;
  const before = target.value.slice(Math.max(0, start - 1), start);
  return Boolean(before && !/[，。、；：？\s]$/.test(before));
}

function renderVirtualKeyboard(target) {
  const container = $("#keyboardKeys");
  if (!container) return;
  container.innerHTML = target.id === "displayName" ? englishKeyboardMarkup() : symptomKeyboardMarkup();
}

function englishKeyboardMarkup() {
  const rows = [
    ["1", "2", "3", "4", "5", "6", "7", "8", "9", "0"],
    ["Q", "W", "E", "R", "T", "Y", "U", "I", "O", "P"],
    ["A", "S", "D", "F", "G", "H", "J", "K", "L"],
    ["Z", "X", "C", "V", "B", "N", "M"]
  ];
  return `
    <div class="keyboard-section">
      <span class="keyboard-section-title">英文姓名輸入</span>
      ${rows.map((row) => `<div class="keyboard-grid qwerty-grid">${row.map(keyButton).join("")}</div>`).join("")}
      <div class="keyboard-grid command-grid">
        ${actionButton("clear", "清除")}
        ${actionButton("space", "空格")}
        ${keyButton("-")}
        ${keyButton(".")}
        ${actionButton("backspace", "⌫")}
        ${actionButton("done", "完成")}
      </div>
    </div>
  `;
}

function symptomKeyboardMarkup() {
  const phrases = [
    "頭痛", "頭暈", "腹脹", "腹痛", "胃口不好", "大便不成形", "便秘", "口乾",
    "怕冷", "怕熱", "出汗", "疲倦", "睡不好", "胸悶", "咳嗽", "喉嚨痛",
    "已經", "今天開始", "三天左右", "一週以上", "輕微", "中等", "很嚴重", "會加重",
    "會緩解", "飯後", "晚上", "早上", "壓力大", "熬夜後"
  ];
  const symbols = ["，", "。", "、", "？", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"];
  return `
    <div class="keyboard-section">
      <span class="keyboard-section-title">常用症狀詞</span>
      <div class="keyboard-grid phrase-grid">${phrases.map(keyButton).join("")}</div>
    </div>
    <div class="keyboard-section">
      <span class="keyboard-section-title">符號與操作</span>
      <div class="keyboard-grid symbol-grid">
        ${symbols.map(keyButton).join("")}
        ${actionButton("space", "空格")}
        ${actionButton("newline", "換行")}
        ${actionButton("clear", "清除")}
        ${actionButton("backspace", "⌫")}
        ${actionButton("done", "完成")}
      </div>
    </div>
  `;
}

function keyButton(text) {
  return `<button type="button" data-vkey-text="${escapeHtml(text)}">${escapeHtml(text)}</button>`;
}

function actionButton(action, label) {
  return `<button type="button" data-vkey-action="${escapeHtml(action)}">${escapeHtml(label)}</button>`;
}

function updateVoiceUi() {
  [
    { group: "chief", button: $("#chiefMicBtn"), status: $("#chiefVoiceStatus") },
    { group: "answer", button: $("#answerMicBtn"), status: $("#answerVoiceStatus") }
  ].forEach(({ group, button, status }) => {
    const active = state.isRecording && state.recognitionGroup === group;
    button.classList.toggle("is-recording", active);
    button.setAttribute("aria-pressed", String(active));
    button.querySelector(".mic-label").textContent = active ? "停止錄音" : "開始錄音";
    if (active) {
      const config = currentSpeechConfig();
      status.textContent = state.voiceEngine === "web"
        ? `正在使用 Google ${config.label}線上辨識；文字會自動轉為繁體。`
        : isOnlineSpeechEnabled()
          ? `正在錄音；停止後會送到 Google Cloud ${config.label}辨識並轉為繁體。`
          : "正在使用離線 Vosk 錄音；說完停頓後會轉成文字，也可再按一次停止。";
    }
    else if (status.textContent.includes("正在錄音")) status.textContent = group === "chief" ? "錄音已停止，可檢查文字後送出。" : "錄音已停止，可檢查文字後送出回答。";
  });
}

function updateVoiceButtonsOnly() {
  [
    { group: "chief", button: $("#chiefMicBtn") },
    { group: "answer", button: $("#answerMicBtn") }
  ].forEach(({ group, button }) => {
    const active = state.isRecording && state.recognitionGroup === group;
    button.classList.toggle("is-recording", active);
    button.setAttribute("aria-pressed", String(active));
    button.querySelector(".mic-label").textContent = active ? "停止錄音" : "開始錄音";
  });
}

function activeVoiceStatus() {
  if (state.recognitionGroup === "chief") return $("#chiefVoiceStatus");
  if (state.recognitionGroup === "answer") return $("#answerVoiceStatus");
  return null;
}

function clearVoiceNoResultTimer() {
  if (state.voiceNoResultTimer) {
    clearTimeout(state.voiceNoResultTimer);
    state.voiceNoResultTimer = null;
  }
}

function setVoiceUnsupported(message) {
  const chief = $("#chiefVoiceStatus");
  const answer = $("#answerVoiceStatus");
  if (chief) chief.textContent = message;
  if (answer) answer.textContent = message;
  ["#chiefMicBtn", "#answerMicBtn"].forEach((selector) => {
    const button = $(selector);
    if (button) button.disabled = true;
  });
}

function setVoiceReadyStatus() {
  const message = voiceReadyMessage();
  const chief = $("#chiefVoiceStatus");
  const answer = $("#answerVoiceStatus");
  if (chief) chief.textContent = message;
  if (answer) answer.textContent = "可語音回答；辨識完成後請檢查文字再送出。";
  ["#chiefMicBtn", "#answerMicBtn"].forEach((selector) => {
    const button = $(selector);
    if (button) button.disabled = false;
  });
}

function voiceReadyMessage() {
  const config = currentSpeechConfig();
  if (config.language === "hokkien") return "台語 / 閩南語辨識為實驗功能；目前會先以 Google Cloud 華語模型嘗試辨識，辨識後仍可手動修正文字。";
  if (isOnlineSpeechEnabled()) return "預設使用 Google Cloud 線上華語辨識；Firefox/Chromium 只負責錄音，辨識文字會自動轉為繁體。";
  return "目前使用離線 Vosk 模式；辨識速度取決於 Pi 與本機模型。";
}

function voiceErrorMessage(error) {
  return {
    "not-allowed": "麥克風權限被拒絕。請在瀏覽器網址列允許麥克風，並使用 HTTPS 或 localhost。",
    "service-not-allowed": "Google 線上語音辨識目前不可用。請確認瀏覽器語音服務與網路；若要離線辨識，請到設定手動切換 Vosk。",
    "network": "Google 線上語音辨識連線失敗。系統不會自動改用 Vosk；請確認網路後重試，或到設定手動切換離線 Vosk。",
    "no-speech": "沒有偵測到語音。請靠近麥克風再試一次，或直接輸入文字。",
    "audio-capture": "找不到可用麥克風。請確認系統麥克風與瀏覽器權限。"
  }[error] || "語音辨識發生問題，請重新錄音或改用文字輸入。";
}

function minimumQuestionCount() {
  return state.userType && state.userType.startsWith("returning") ? 5 : 7;
}

function canFinishQuestionFlow() {
  return state.tenQuestions.length >= minimumQuestionCount();
}

function hasImmediateSafetyFlag() {
  const redFlagSymptoms = new Set(["chest_pain", "breath_shortness", "fainting", "high_fever", "severe_pain", "neurologic"]);
  return state.symptoms.some((symptom) => redFlagSymptoms.has(symptom));
}

function refreshSafetyState() {
  const wasActive = state.redFlagActive;
  state.redFlagActive = hasImmediateSafetyFlag();
  if (!state.redFlagActive) state.urgentAcknowledged = false;
  if (state.redFlagActive && !wasActive) state.urgentAcknowledged = false;
  renderUrgentBanner();
  updateFinishButton();
}

function renderUrgentBanner() {
  const banner = $("#urgentBanner");
  if (!banner) return;
  banner.hidden = !state.redFlagActive;
  const checkbox = $("#urgentConfirm");
  if (checkbox) checkbox.checked = state.urgentAcknowledged;
}

function updateFinishButton() {
  const button = $("#finishQuestionsBtn");
  if (!button) return;
  const hint = $("#finishHint");
  const minimum = minimumQuestionCount();
  const canFinish = state.tenQuestions.length >= minimum;
  button.hidden = !canFinish;
  button.disabled = !canFinish || (state.redFlagActive && !state.urgentAcknowledged);
  button.textContent = "產生結果";
  if (hint) {
    if (canFinish && state.redFlagActive && !state.urgentAcknowledged) {
      hint.hidden = false;
      hint.textContent = "請先確認上方安全提醒";
    } else {
      hint.hidden = canFinish;
      hint.textContent = `完成 ${minimum} 題後產生結果`;
    }
  }
}

function setAnswerSubmitting(isSubmitting) {
  const button = $("#answerBtn");
  if (!button) return;
  button.disabled = isSubmitting;
  button.textContent = isSubmitting ? "送出中..." : "送出回答";
}

function categoryLabel(category) {
  return {
    red_flag: "安全警訊",
    duration: "病程時間",
    pain: "程度與疼痛",
    cold_heat: "寒熱口渴",
    sweat: "汗出狀態",
    head_body: "頭身狀態",
    appetite: "飲食脾胃",
    mouth: "口腔咽喉",
    bowel_urine: "二便狀態",
    sleep: "睡眠狀態",
    emotion: "精神情緒",
    menstruation: "月經狀態",
    history: "病史用藥"
  }[category] || "十問問診";
}

function readProfile() {
  return {
    user_id: state.userId,
    display_name: $("#displayName").value.trim(),
    age: readNumber("#userAge"),
    sex: $("#userSex").value,
    height_cm: readNumber("#userHeight"),
    weight_kg: readNumber("#userWeight"),
    lifestyle: {
      sleep_pattern: $("#sleepPattern").value,
      diet_pattern: $("#dietPattern").value,
      exercise_level: $("#exerciseLevel").value,
      stress_level: $("#stressLevel").value
    }
  };
}

function buildBaseline() {
  const previous = state.baseline || {};
  const days = Number(previous.baseline_days || 0);
  return {
    user_id: state.userId,
    baseline_id: previous.baseline_id || `BL-${state.userId.slice(0, 8)}`,
    baseline_days: days,
    status: days >= 15 ? "ready" : days > 0 ? "building" : "none",
    face_summary: previous.face_summary || {},
    symptom_baseline: previous.symptom_baseline || {},
    last_updated: new Date().toISOString()
  };
}

function hydrateProfile() {
  const saved = loadJson(STORAGE_KEYS.profile, {});
  state.profile = saved;
  if (saved.display_name) $("#displayName").value = saved.display_name;
  if (saved.age) $("#userAge").value = saved.age;
  if (saved.sex) $("#userSex").value = saved.sex;
  if (saved.height_cm) $("#userHeight").value = saved.height_cm;
  if (saved.weight_kg) $("#userWeight").value = saved.weight_kg;
  if (saved.lifestyle) {
    $("#sleepPattern").value = saved.lifestyle.sleep_pattern || "regular";
    $("#dietPattern").value = saved.lifestyle.diet_pattern || "balanced";
    $("#exerciseLevel").value = saved.lifestyle.exercise_level || "low";
    $("#stressLevel").value = saved.lifestyle.stress_level || "low";
  }
}

function updateProfileStatus(result = {}) {
  const hasProfile = Boolean(loadJson(STORAGE_KEYS.profile, {}).user_id);
  const baseline = state.baseline || {};
  const baselineStatus = result.baseline_status || baseline.status || "none";
  $("#profileStatus").textContent = hasProfile ? "已找到舊資料" : "新使用者";
  $("#userTypeLabel").textContent = result.user_type || (hasProfile ? "舊使用者" : "新使用者");
  $("#baselineLabel").textContent = baselineStatus === "ready" ? "已建立基準資料" : baselineStatus === "building" ? "基準建立中" : "尚未建立基準";
  $("#modeLabel").textContent = result.mode === "multimodal" ? "面部與問答綜合" : "問答為主";
  renderSettingsPanel();
}

function showStep(step) {
  hideVirtualKeyboard();
  state.currentStep = step;
  state.furthestStep = Math.max(state.furthestStep, step);
  stepPanels.forEach((panel) => { panel.hidden = Number(panel.dataset.step) !== step; });
  stepItems.forEach((item) => {
    const itemStep = Number(item.dataset.stepJump);
    item.classList.toggle("is-active", itemStep === step);
    item.classList.toggle("is-complete", itemStep < step);
    item.disabled = itemStep > state.furthestStep;
  });
}

function setResultState(name) {
  $("#emptyState").hidden = name !== "empty";
  $("#loadingState").hidden = name !== "loading";
  $("#errorState").hidden = name !== "error";
  $("#resultContent").hidden = name !== "result";
  $("#aiStatus").textContent = { empty: "等待資料", loading: "整理中", error: "需要重試", result: "完成" }[name] || "等待資料";
  updateProcessingAnimation(name === "loading");
}

function updateProcessingAnimation(active) {
  if (state.processingTimer) {
    clearInterval(state.processingTimer);
    state.processingTimer = null;
  }
  const status = $("#processingStatusText");
  if (!status) return;
  if (!active) {
    status.textContent = "整理問診資料...";
    return;
  }
  const phases = ["整理問診資料...", "比對規則引擎...", "整合面部觀察提示...", "生成參考結果..."];
  let index = 0;
  status.textContent = phases[index];
  state.processingTimer = setInterval(() => {
    index = (index + 1) % phases.length;
    status.textContent = phases[index];
  }, 900);
}

async function postJson(url, payload) {
  const response = await fetch(appUrl(url), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!response.ok) throw new Error(`Request failed: ${response.status}`);
  return response.json();
}

async function postJsonAllowError(url, payload) {
  const response = await fetch(appUrl(url), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(body.error || `Request failed: ${response.status}`);
  return body;
}

function bindSettingsEvents() {
  const button = $("#settingsBtn");
  if (!button) return;
  button.addEventListener("click", openSettingsPanel);
  $("#settingsCloseBtn").addEventListener("click", closeSettingsPanel);
  $("#settingsOverlay").addEventListener("click", (event) => {
    if (event.target.id === "settingsOverlay") closeSettingsPanel();
  });
  $("#speechLanguageSetting").addEventListener("change", saveSettingsFromPanel);
  $("#speechModeSetting").addEventListener("change", saveSettingsFromPanel);
  $("#settingsClearHistoryBtn").addEventListener("click", clearLocalHistory);
  const urgentConfirm = $("#urgentConfirm");
  if (urgentConfirm) {
    urgentConfirm.addEventListener("change", () => {
      state.urgentAcknowledged = urgentConfirm.checked;
      updateFinishButton();
      if (state.urgentAcknowledged) clearError();
    });
  }
}

function openSettingsPanel() {
  renderSettingsPanel();
  $("#settingsOverlay").hidden = false;
}

function closeSettingsPanel() {
  $("#settingsOverlay").hidden = true;
}

function saveSettingsFromPanel() {
  const speechMode = $("#speechModeSetting").value || "online";
  state.settings = {
    speechLanguage: $("#speechLanguageSetting").value,
    speechMode,
    onlineSpeechEnabled: speechMode !== "offline",
    historyOpenMode: "open_personal_family"
  };
  saveJson(STORAGE_KEYS.settings, state.settings);
  setVoiceReadyStatus();
}

function renderSettingsPanel() {
  const language = $("#speechLanguageSetting");
  if (!language) return;
  language.value = state.settings.speechLanguage || "mandarin";
  $("#speechModeSetting").value = currentSpeechMode();
  $("#settingsProfileSummary").textContent = buildProfileSummary();
  $("#settingsUserId").textContent = `本機識別碼：${state.userId}`;
  renderHistorySettings();
}

function renderHistorySettings() {
  const list = $("#settingsHistoryList");
  const empty = $("#settingsHistoryEmpty");
  if (!list || !empty) return;
  const history = loadJson(STORAGE_KEYS.history, { sessions: [] });
  const sessions = Array.isArray(history.sessions) ? history.sessions : [];
  list.innerHTML = "";
  empty.hidden = sessions.length > 0;
  sessions.slice(0, 10).forEach((item, index) => {
    const details = document.createElement("details");
    const summary = document.createElement("summary");
    const date = item.date ? new Date(item.date).toLocaleString("zh-Hant-TW", { hour12: false }) : `第 ${index + 1} 次`;
    summary.textContent = `${date}｜${(item.top_patterns || ["未產生傾向"]).slice(0, 2).join("、")}`;
    const body = document.createElement("div");
    body.className = "history-detail";
    const chief = document.createElement("p");
    chief.textContent = `主訴：${item.chief_complaint_summary || "未記錄"}`;
    const answers = document.createElement("p");
    answers.textContent = `問答：${Array.isArray(item.ten_questions) ? item.ten_questions.length : 0} 題`;
    const possibilities = document.createElement("ul");
    (item.result?.possibilities || []).slice(0, 3).forEach((possibility) => {
      const li = document.createElement("li");
      li.textContent = `${possibility.pattern || "未命名傾向"} ${possibility.fit_percent || 0}%`;
      possibilities.append(li);
    });
    body.append(chief, answers, possibilities);
    details.append(summary, body);
    list.append(details);
  });
}

function clearLocalHistory() {
  if (!confirm("確定清除本機歷史紀錄嗎？這不會刪除後端資料庫，只清除目前瀏覽器的紀錄。")) return;
  saveJson(STORAGE_KEYS.history, { user_id: state.userId, sessions: [] });
  renderHistorySettings();
}

function bindAdminEvents() {
  const hotspot = $("#adminHotspot");
  if (!hotspot) return;
  hotspot.addEventListener("click", handleAdminHotspotTap);
  $("#adminCloseBtn").addEventListener("click", closeAdminPanel);
  $("#adminOverlay").addEventListener("click", (event) => {
    if (event.target.id === "adminOverlay") closeAdminPanel();
  });
  $("#adminReloadBtn").addEventListener("click", () => window.location.reload());
  $("#adminFullscreenBtn").addEventListener("click", enterFullscreen);
  $("#adminExitFullscreenBtn").addEventListener("click", exitFullscreen);
  $("#adminCheckBtn").addEventListener("click", checkAdminStatus);
  $("#adminExitKioskBtn").addEventListener("click", exitKiosk);
}

function handleAdminHotspotTap() {
  state.adminTapCount += 1;
  if (state.adminTapTimer) clearTimeout(state.adminTapTimer);
  state.adminTapTimer = setTimeout(() => {
    state.adminTapCount = 0;
  }, 2200);
  if (state.adminTapCount >= 6) {
    state.adminTapCount = 0;
    openAdminPanel();
  }
}

function openAdminPanel() {
  const overlay = $("#adminOverlay");
  overlay.hidden = false;
  $("#adminStatus").textContent = "已開啟維護選單。";
}

function closeAdminPanel() {
  $("#adminOverlay").hidden = true;
}

async function checkAdminStatus() {
  try {
    const result = await postJsonAllowError("api/admin/action", { action: "status" });
    const stats = result.database || {};
    $("#adminStatus").textContent = `系統正常。profiles: ${stats.profiles ?? 0}, sessions: ${stats.sessions ?? 0}, results: ${stats.results ?? 0}`;
  } catch {
    $("#adminStatus").textContent = "無法讀取系統狀態。";
  }
}

async function exitKiosk() {
  if (!confirm("確定要回到 Raspberry Pi 桌面嗎？系統會關閉 kiosk 瀏覽器。")) return;
  try {
    await postJsonAllowError("api/admin/action", { action: "exit_kiosk" });
    $("#adminStatus").textContent = "已送出返回 Raspberry Pi 桌面的指令。";
  } catch {
    $("#adminStatus").textContent = "無法退出 kiosk。請用鍵盤 Alt+F4 / VNC 維護。";
  }
}

function enterFullscreen() {
  const target = document.documentElement;
  if (target.requestFullscreen) target.requestFullscreen();
  $("#adminStatus").textContent = "已嘗試進入全螢幕。";
}

function exitFullscreen() {
  if (document.exitFullscreen) document.exitFullscreen();
  $("#adminStatus").textContent = "已嘗試離開全螢幕。";
}

function appUrl(path) {
  if (/^https?:\/\//.test(path)) return path;
  const normalizedPath = String(path || "").replace(/^\/+/, "");
  return `${APP_BASE}/${normalizedPath}`;
}

function loadSample() {
  $("#displayName").value = "陳小姐";
  $("#userAge").value = 35;
  $("#userSex").value = "female";
  $("#userHeight").value = 162;
  $("#userWeight").value = 55;
  $("#sleepPattern").value = "late";
  $("#dietPattern").value = "cold_sweet";
  $("#exerciseLevel").value = "low";
  $("#stressLevel").value = "medium";
  $("#chiefText").value = "最近肚子脹，身體沉重，大便不成形，胃口也不好，約持續兩週。";
}

function saveFollowUp(result) {
  const history = loadJson(STORAGE_KEYS.history, { user_id: state.userId, sessions: [] });
  const top = (result.possibilities || []).slice(0, 3).map((item) => item.pattern);
  history.user_id = state.userId;
  history.sessions = [{
    session_id: state.sessionId,
    date: new Date().toISOString(),
    top_patterns: top,
    chief_complaint_summary: state.chiefComplaint?.text || "",
    ten_questions: state.tenQuestions,
    result: {
      possibilities: (result.possibilities || []).slice(0, 3),
      report_summary: result.report_summary || result.preliminary_assessment || "",
      care_plan: result.care_plan || [],
      seek_care_if: result.seek_care_if || [],
      red_flag: Boolean(result.red_flag)
    },
    baseline_compared: state.baseline?.status === "ready"
  }, ...(history.sessions || [])].slice(0, 30);
  saveJson(STORAGE_KEYS.history, history);
  renderSettingsPanel();
}

function getOrCreateUserId() {
  let id = localStorage.getItem(STORAGE_KEYS.userId);
  if (!id) {
    id = crypto.randomUUID ? crypto.randomUUID() : `user-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    localStorage.setItem(STORAGE_KEYS.userId, id);
  }
  return id;
}

function buildProfileSummary() {
  const p = state.profile || {};
  return [p.display_name || "匿名", p.age ? `${p.age}歲` : "", sexLabel(p.sex)].filter(Boolean).join(" / ");
}

function buildReportId() {
  return `TCM-${(state.sessionId || state.userId).slice(0, 8).toUpperCase()}`;
}

function appendText(selector, text) {
  const input = $(selector);
  input.value = input.value.trim() ? `${input.value.trim()} ${text}` : text;
  input.focus();
}

function showError(text) {
  const formError = $("#formError");
  if (formError) formError.textContent = text;
  const globalAlert = $("#globalAlert");
  if (globalAlert) {
    globalAlert.textContent = text;
    globalAlert.hidden = !text;
  }
}

function clearError() {
  const formError = $("#formError");
  if (formError) formError.textContent = "";
  const globalAlert = $("#globalAlert");
  if (globalAlert) {
    globalAlert.textContent = "";
    globalAlert.hidden = true;
  }
}

function readNumber(selector) {
  const value = Number($(selector).value);
  return Number.isFinite(value) && value > 0 ? value : null;
}

function defaultSpeechSettings() {
  return {
    speechLanguage: "mandarin",
    speechMode: "online",
    onlineSpeechEnabled: true,
    historyOpenMode: "open_personal_family"
  };
}

function normalizeSpeechSettings(settings) {
  const loaded = settings && typeof settings === "object" ? settings : {};
  const normalized = { ...defaultSpeechSettings(), ...loaded };
  if (!Object.prototype.hasOwnProperty.call(loaded, "speechMode")) {
    normalized.speechMode = "online";
  }
  if (!["online", "offline"].includes(normalized.speechMode)) normalized.speechMode = "online";
  normalized.onlineSpeechEnabled = normalized.speechMode !== "offline";
  return normalized;
}

function currentSpeechMode() {
  if (state.settings.speechMode === "offline") return "offline";
  if (state.settings.speechMode === "online") return "online";
  return state.settings.onlineSpeechEnabled === false ? "offline" : "online";
}

function isOnlineSpeechEnabled() {
  return currentSpeechMode() === "online";
}

function loadJson(key, fallback) {
  try {
    return JSON.parse(localStorage.getItem(key) || "null") || fallback;
  } catch {
    return fallback;
  }
}

function saveJson(key, value) {
  localStorage.setItem(key, JSON.stringify(value));
}

function sexLabel(value) {
  return { male: "男", female: "女", other: "其他", unspecified: "未提供" }[value] || "未提供";
}

function cleanPublicText(value) {
  return String(value || "").replace(/rule_trace|Python|null|False|True|[{}]/g, "");
}

function escapeHtml(value) {
  return String(value || "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "\"": "&quot;", "'": "&#039;" }[char]));
}
