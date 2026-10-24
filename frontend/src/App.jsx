import { Fragment, useEffect, useMemo, useRef, useState } from "react";

const API_URL = import.meta.env.VITE_API_URL || "";
const SESSION_KEY = "automl-studio-session-v1";
const ACCESS_TOKEN_KEY = "automl_access_token";
const DEFAULT_CLEANING_OPTIONS = Object.freeze({
  numeric_impute: "median",
  categorical_impute: "most_frequent",
  scaling: "standard",
  outlier_method: "none",
  remove_duplicates: false,
  column_types: {}
});

function cleaningOptionsEqual(left, right) {
  const normalize = (options) => JSON.stringify({
    ...options,
    column_types: Object.fromEntries(Object.entries(options.column_types || {}).sort(([a], [b]) => a.localeCompare(b)))
  });
  return normalize(left) === normalize(right);
}

function getAccessToken() {
  const token = localStorage.getItem(ACCESS_TOKEN_KEY);
  if (token) return token;
  const legacyToken = sessionStorage.getItem(ACCESS_TOKEN_KEY);
  if (legacyToken) {
    localStorage.setItem(ACCESS_TOKEN_KEY, legacyToken);
    sessionStorage.removeItem(ACCESS_TOKEN_KEY);
  }
  return legacyToken;
}

function saveAccessToken(token) {
  localStorage.setItem(ACCESS_TOKEN_KEY, token);
  sessionStorage.removeItem(ACCESS_TOKEN_KEY);
}

function clearAccessToken() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  sessionStorage.removeItem(ACCESS_TOKEN_KEY);
}
const STEPS = [
  ["Data", "Upload & preview", "upload"],
  ["Explore", "Understand it", "chart"],
  ["Clean", "Fix & prepare", "sparkle"],
  ["Features", "Goal & columns", "target"],
  ["Train", "Pick & tune models", "settings"],
  ["Results", "Compare & export", "star"],
  ["History", "Past runs & settings", "clock"]
];

function Icon({ name, size = 22 }) {
  const paths = {
    upload: <><path d="M12 16V4" /><path d="m7 9 5-5 5 5" /><path d="M5 20h14" /></>,
    chart: <><path d="M4 19V5" /><path d="M4 19h16" /><path d="m7 15 3-4 3 2 4-6" /></>,
    sparkle: <><path d="m12 3 1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5L12 3Z" /><path d="m19 16 .6 2.4L22 19l-2.4.6L19 22l-.6-2.4L16 19l2.4-.6L19 16Z" /></>,
    target: <><circle cx="12" cy="12" r="8" /><circle cx="12" cy="12" r="3" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3" /></>,
    settings: <><path d="M12 3v3M12 18v3M3 12h3M18 12h3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M18.4 5.6l-2.1 2.1M7.7 16.3l-2.1 2.1" /><circle cx="12" cy="12" r="4" /></>,
    star: <path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-2.9-5.6 2.9 1.1-6.2L3 9.6l6.2-.9L12 3Z" />,
    cloud: <><path d="M7 18h10a4 4 0 0 0 .5-8A6 6 0 0 0 6 11a3.5 3.5 0 0 0 1 7Z" /><path d="M12 14V7m0 0L9 10m3-3 3 3" /></>,
    play: <path d="m9 6 9 6-9 6V6Z" />,
    download: <><path d="M12 3v12" /><path d="m7 11 5 5 5-5" /><path d="M5 21h14" /></>,
    clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
    mail: <><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m3 7 9 6 9-6" /></>,
    lock: <><rect x="4" y="10" width="16" height="11" rx="2" /><path d="M8 10V7a4 4 0 1 1 8 0v3M12 14v3" /></>,
    eye: <><path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6-10-6-10-6Z" /><circle cx="12" cy="12" r="3" /></>,
    user: <><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></>,
    database: <><ellipse cx="12" cy="5" rx="8" ry="3" /><path d="M4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3" /></>,
    send: <><path d="m22 2-7 20-4-9-9-4Z" /><path d="M22 2 11 13" /></>,
    check: <path d="m5 12 4 4L19 6" />,
    arrowRight: <><path d="M5 12h14" /><path d="m13 6 6 6-6 6" /></>,
    logout: <><path d="M10 17l5-5-5-5" /><path d="M15 12H3" /><path d="M12 3h6a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-6" /></>
  };
  return <svg className="icon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}

function ProviderIcon({ provider }) {
  if (provider === "github") return <svg className="provider-icon" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 .9a11.1 11.1 0 0 0-3.51 21.63c.56.1.76-.24.76-.54v-2.1c-3.1.68-3.76-1.32-3.76-1.32-.5-1.3-1.24-1.65-1.24-1.65-1.01-.7.08-.69.08-.69 1.12.08 1.71 1.15 1.71 1.15 1 1.7 2.62 1.21 3.26.93.1-.72.39-1.21.71-1.49-2.47-.28-5.07-1.24-5.07-5.51 0-1.22.44-2.21 1.15-2.99-.12-.28-.5-1.42.11-2.95 0 0 .94-.3 3.05 1.14a10.6 10.6 0 0 1 5.55 0c2.11-1.44 3.04-1.14 3.04-1.14.61 1.53.23 2.67.12 2.95.72.78 1.15 1.77 1.15 2.99 0 4.28-2.6 5.22-5.08 5.5.4.35.76 1.03.76 2.08v3.1c0 .3.2.65.77.54A11.1 11.1 0 0 0 12 .9Z" /></svg>;
  return <svg className="provider-icon google-icon" viewBox="0 0 48 48" aria-hidden="true"><path fill="#4285F4" d="M43.6 24.5c0-1.4-.1-2.8-.4-4.1H24v7.8h11a9.4 9.4 0 0 1-4.1 6.2v5.1h6.7c3.9-3.6 6-8.8 6-15Z"/><path fill="#34A853" d="M24 44c5.5 0 10.1-1.8 13.5-4.8l-6.7-5.1c-1.8 1.2-4 1.9-6.8 1.9-5.2 0-9.7-3.5-11.3-8.2H5.8v5.2A20 20 0 0 0 24 44Z"/><path fill="#FBBC05" d="M12.7 27.8a12 12 0 0 1 0-7.6V15H5.8a20 20 0 0 0 0 18Z"/><path fill="#EA4335" d="M24 12c3 0 5.7 1 7.8 3.1l5.8-5.8C34.1 6.1 29.5 4 24 4A20 20 0 0 0 5.8 15l6.9 5.2C14.3 15.5 18.8 12 24 12Z"/></svg>;
}

async function api(path, options = {}) {
  const headers = new Headers(options.headers || {});
  const token = getAccessToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (response.status === 401 && token) {
    clearAccessToken();
    sessionStorage.removeItem(SESSION_KEY);
    window.location.assign("/login");
  }
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = Array.isArray(body.detail)
      ? body.detail.map((item) => item.msg).join(", ")
      : body.detail || "Request failed.";
    throw new Error(detail);
  }
  return body;
}

function Workspace({ onLogout, initialAccount }) {
  const [restored] = useState(() => {
    try { return JSON.parse(sessionStorage.getItem(SESSION_KEY) || "{}"); } catch { return {}; }
  });
  const [step, setStep] = useState(restored.step ?? 0);
  const [dataset, setDataset] = useState(restored.dataset ?? null);
  const [datasetCharts, setDatasetCharts] = useState(restored.datasetCharts ?? null);
  const [history, setHistory] = useState([]);
  const [account, setAccount] = useState(initialAccount);
  const [accountName, setAccountName] = useState(initialAccount?.display_name || "");
  const [accountSavedNotice, setAccountSavedNotice] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const [selectedRunIds, setSelectedRunIds] = useState(restored.selectedRunIds ?? []);
  const [file, setFile] = useState(null);
  const [target, setTarget] = useState(restored.target ?? "");
  const [task, setTask] = useState(restored.task ?? "classification");
  const [exclude, setExclude] = useState(restored.exclude ?? []);
  const [include, setInclude] = useState(restored.include ?? []);
  const [excludeFlagged, setExcludeFlagged] = useState(restored.excludeFlagged ?? true);
  const [numericImpute, setNumericImpute] = useState(restored.numericImpute ?? "median");
  const [categoricalImpute, setCategoricalImpute] = useState(restored.categoricalImpute ?? "most_frequent");
  const [scaling, setScaling] = useState(restored.scaling ?? "standard");
  const [outlierMethod, setOutlierMethod] = useState(restored.outlierMethod ?? "none");
  const [removeDuplicates, setRemoveDuplicates] = useState(restored.removeDuplicates ?? false);
  const [columnTypes, setColumnTypes] = useState(restored.columnTypes ?? {});
  const [appliedCleaning, setAppliedCleaning] = useState(() => restored.appliedCleaning ?? {
    numeric_impute: restored.numericImpute ?? DEFAULT_CLEANING_OPTIONS.numeric_impute,
    categorical_impute: restored.categoricalImpute ?? DEFAULT_CLEANING_OPTIONS.categorical_impute,
    scaling: restored.scaling ?? DEFAULT_CLEANING_OPTIONS.scaling,
    outlier_method: restored.outlierMethod ?? DEFAULT_CLEANING_OPTIONS.outlier_method,
    remove_duplicates: restored.removeDuplicates ?? DEFAULT_CLEANING_OPTIONS.remove_duplicates,
    column_types: restored.columnTypes ?? {}
  });
  const [runAll, setRunAll] = useState(restored.runAll ?? true);
  const [selectedModels, setSelectedModels] = useState(restored.selectedModels ?? []);
  const [job, setJob] = useState(restored.job ?? null);
  const [results, setResults] = useState(restored.results ?? null);
  const [predictionRows, setPredictionRows] = useState(restored.predictionRows ?? "{}");
  const [predictions, setPredictions] = useState(restored.predictions ?? null);
  const [busy, setBusy] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [error, setError] = useState("");
  const [selectedColumn, setSelectedColumn] = useState(restored.selectedColumn ?? "");
  const [activity, setActivity] = useState(restored.activity ?? []);
  const [assistantQuestion, setAssistantQuestion] = useState("");
  const [assistantMessages, setAssistantMessages] = useState(restored.assistantMessages ?? [
    { role: "assistant", content: "Ask me about your dataset, warnings, targets, features, or training." }
  ]);
  const [assistantBusy, setAssistantBusy] = useState(false);
  const [apiOnline, setApiOnline] = useState(null);
  const [persistentDatabase, setPersistentDatabase] = useState(null);
  const [cleanAppliedNotice, setCleanAppliedNotice] = useState(0);
  const assistantChatRef = useRef(null);

  useEffect(() => {
    setAccount(initialAccount);
    setAccountName(initialAccount?.display_name || "");
  }, [initialAccount]);

  useEffect(() => {
      try {
      sessionStorage.setItem(SESSION_KEY, JSON.stringify({ step, dataset, datasetCharts, target, task, exclude, include, excludeFlagged, numericImpute, categoricalImpute, scaling, outlierMethod, removeDuplicates, columnTypes, appliedCleaning, runAll, selectedModels, job, results, predictionRows, predictions, selectedColumn, activity, assistantMessages, selectedRunIds }));
    } catch (storageError) { console.warn("Could not save workspace in this browser tab.", storageError); }
  }, [step, dataset, datasetCharts, target, task, exclude, include, excludeFlagged, numericImpute, categoricalImpute, scaling, outlierMethod, removeDuplicates, columnTypes, appliedCleaning, runAll, selectedModels, job, results, predictionRows, predictions, selectedColumn, activity, assistantMessages, selectedRunIds]);

  useEffect(() => {
    api("/jobs").then(setHistory).catch(() => {});
  }, [job?.status]);

  useEffect(() => {
    if (step !== 6) return undefined;
    let active = true;
    api("/jobs").then((runs) => { if (active) setHistory(runs); }).catch((requestError) => { if (active) setError(requestError.message); });
    return () => { active = false; };
  }, [step]);

  useEffect(() => {
    if (!error) return undefined;
    const timer = setTimeout(() => setError(""), 2000);
    return () => clearTimeout(timer);
  }, [error]);

  useEffect(() => {
    if (!cleanAppliedNotice) return undefined;
    const timer = setTimeout(() => setCleanAppliedNotice(0), 2000);
    return () => clearTimeout(timer);
  }, [cleanAppliedNotice]);

  useEffect(() => {
    if (!accountSavedNotice) return undefined;
    const timer = setTimeout(() => setAccountSavedNotice(false), 2000);
    return () => clearTimeout(timer);
  }, [accountSavedNotice]);

  useEffect(() => {
    if (!dataset?.dataset_id) return;
    let active = true;
    api(`/datasets/${dataset.dataset_id}/charts?target=${encodeURIComponent(target)}&numeric_impute=${numericImpute}&categorical_impute=${categoricalImpute}`)
      .then((charts) => { if (active) setDatasetCharts(charts); })
      .catch((requestError) => { if (active) setError(requestError.message); });
    return () => { active = false; };
  }, [dataset?.dataset_id, target, numericImpute, categoricalImpute]);

  useEffect(() => {
    if (!job?.job_id || ["completed", "failed"].includes(job.status)) return;
    api(`/jobs/${job.job_id}`).then(setJob).catch(() => {});
  }, []);

  const profile = dataset?.profile;
  const flaggedColumns = Object.values(profile?.flagged || {}).flat();
  const columns = profile?.columns || [];
  const selectedProfile = columns.find((column) => column.name === selectedColumn);
  const targetColumn = columns.find((column) => column.name === target);
  const draftCleaning = useMemo(() => ({ numeric_impute: numericImpute, categorical_impute: categoricalImpute, scaling, outlier_method: outlierMethod, remove_duplicates: removeDuplicates, column_types: columnTypes }), [numericImpute, categoricalImpute, scaling, outlierMethod, removeDuplicates, columnTypes]);
  const cleaningDirty = !cleaningOptionsEqual(draftCleaning, appliedCleaning);
  const trainable = Boolean(dataset && target && !busy);
  const done = new Set([
    ...(dataset ? [0, 1, 2, 3] : []),
    ...(job ? [4] : []),
    ...(results ? [5] : [])
  ]);

  useEffect(() => {
    let active = true;
    const checkHealth = async () => {
      try {
        const health = await api("/health");
        if (active) {
          setApiOnline(true);
          setPersistentDatabase(Boolean(health.persistent_database));
        }
      } catch {
        if (active) setApiOnline(false);
      }
    };
    checkHealth();
    const timer = setInterval(checkHealth, 5000);
    return () => {
      active = false;
      clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    const chat = assistantChatRef.current;
    if (chat) chat.scrollTop = chat.scrollHeight;
  }, [assistantMessages, assistantBusy]);

  useEffect(() => {
    if (!job || ["completed", "failed"].includes(job.status)) return undefined;
    const timer = setTimeout(async () => {
      try {
        const updated = await api(`/jobs/${job.job_id}`);
        setJob(updated);
        if (updated.logs.length) setActivity(updated.logs);
      } catch (requestError) {
        setError(requestError.message);
      }
    }, 1500);
    return () => clearTimeout(timer);
  }, [job]);

  useEffect(() => {
    if (job?.status !== "completed" || results) return;
    api(`/jobs/${job.job_id}/results`)
      .then((response) => {
        setResults(response);
        setStep(5);
        setActivity(["Training completed", `Best model: ${response.best_model}`]);
      })
      .catch((requestError) => setError(requestError.message));
  }, [job, results]);

  async function upload(event) {
    const selectedFile = event.target.files?.[0];
    if (!selectedFile) return;
    setFile(selectedFile);
    setBusy(true);
    setUploadProgress(0);
    setError("");
    setDataset(null);
    setExclude([]);
    setInclude([]);
    setNumericImpute(DEFAULT_CLEANING_OPTIONS.numeric_impute);
    setCategoricalImpute(DEFAULT_CLEANING_OPTIONS.categorical_impute);
    setScaling(DEFAULT_CLEANING_OPTIONS.scaling);
    setOutlierMethod(DEFAULT_CLEANING_OPTIONS.outlier_method);
    setRemoveDuplicates(DEFAULT_CLEANING_OPTIONS.remove_duplicates);
    setColumnTypes({});
    setAppliedCleaning({ ...DEFAULT_CLEANING_OPTIONS, column_types: {} });
    setDatasetCharts(null);
    setJob(null);
    setResults(null);
    try {
      const formData = new FormData();
      formData.append("file", selectedFile);
      const uploaded = await uploadWithProgress(formData, setUploadProgress);
      setDataset(uploaded);
      const names = uploaded.profile.columns.map((column) => column.name);
      const flagged = new Set(uploaded.profile.flagged.id_like || []);
      const preferred = ["Survived", "target", "Target", "label", "Label", "price", "Price", "y"];
      const inferredTarget = preferred.find((name) => names.includes(name)) || names.find((name) => !flagged.has(name)) || names[0] || "";
      setTarget(inferredTarget);
      setSelectedColumn(inferredTarget);
      setActivity(["Dataset uploaded", `${uploaded.profile.n_rows.toLocaleString()} rows detected`]);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }

    function uploadWithProgress(formData, onProgress) {
      return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest();
        xhr.open("POST", `${API_URL}/datasets`);
        const token = getAccessToken();
        if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
        xhr.upload.addEventListener("progress", (event) => {
          if (event.lengthComputable) onProgress(Math.round((event.loaded / event.total) * 100));
        });
        xhr.addEventListener("load", () => {
          const body = JSON.parse(xhr.responseText || "{}");
          if (xhr.status >= 200 && xhr.status < 300) resolve(body);
          else reject(new Error(Array.isArray(body.detail) ? body.detail.map((item) => item.msg).join(", ") : body.detail || "Upload failed."));
        });
        xhr.addEventListener("error", () => reject(new Error("Upload failed. Check that the backend is running.")));
        xhr.send(formData);
      });
    }
  }

  async function startTraining() {
    if (cleaningDirty) {
      setError("Apply your cleaning changes before starting training.");
      setStep(2);
      return;
    }
    setBusy(true);
    setError("");
    setResults(null);
    try {
      const created = await api("/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          dataset_id: dataset.dataset_id,
          target,
          task,
          exclude,
          include,
          exclude_flagged: excludeFlagged,
          selected_models: selectedModels,
          run_all: runAll,
          options: appliedCleaning
        })
      });
      setJob(created);
      setStep(5);
      setActivity(["Training job queued"]);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  }

  function applyCleaning() {
    setAppliedCleaning({ ...draftCleaning, column_types: { ...draftCleaning.column_types } });
    setCleanAppliedNotice((current) => current + 1);
    setError("");
    setActivity((current) => ["Cleaning settings applied for training", ...current].slice(0, 20));
  }

  function resetCleaning() {
    const defaults = { ...DEFAULT_CLEANING_OPTIONS, column_types: {} };
    setNumericImpute(defaults.numeric_impute);
    setCategoricalImpute(defaults.categorical_impute);
    setScaling(defaults.scaling);
    setOutlierMethod(defaults.outlier_method);
    setRemoveDuplicates(defaults.remove_duplicates);
    setColumnTypes({});
    setAppliedCleaning(defaults);
    setError("");
  }

  async function askAssistant() {
    const question = assistantQuestion.trim();
    if (!question || assistantBusy) return;
    const nextMessages = [...assistantMessages, { role: "user", content: question }];
    setAssistantMessages(nextMessages);
    setAssistantQuestion("");
    setAssistantBusy(true);
    try {
      const response = await api("/assistant", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question,
          context: {
            profile,
            target,
            task,
            step: STEPS[step][0],
            job: job?.status,
            results: results ? { best_model: results.best_model } : null,
            conversation: nextMessages.slice(-12)
          }
        })
      });
      setAssistantMessages((current) => [...current, { role: "assistant", content: response.answer }]);
    } catch (requestError) {
      setAssistantMessages((current) => [...current, { role: "assistant", content: requestError.message }]);
    } finally {
      setAssistantBusy(false);
    }
  }

  async function predict() {
    try {
      const parsed = JSON.parse(predictionRows);
      const rows = Array.isArray(parsed) ? parsed : [parsed];
      const response = await api(`/models/${results.model_id}/predict`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ rows })
      });
      setPredictions(response.predictions);
      setError("");
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  function toggleExclude(name) {
    const isAutoExcluded = excludeFlagged && flaggedColumns.includes(name) && !include.includes(name);
    const isExcluded = exclude.includes(name) || isAutoExcluded;
    if (isExcluded) {
      setExclude((current) => current.filter((column) => column !== name));
      setInclude((current) => current.includes(name) ? current : [...current, name]);
    } else {
      setExclude((current) => current.includes(name) ? current : [...current, name]);
      setInclude((current) => current.filter((column) => column !== name));
    }
  }

  function moveTo(nextStep) {
    if (nextStep === 0 || nextStep === 6 || dataset) {
      setAccountOpen(false);
      setStep(nextStep);
    }
  }

  async function saveAccountName(event) {
    event.preventDefault();
    try {
      const updated = await api("/auth/me", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ display_name: accountName })
      });
      setAccount(updated);
      setAccountName(updated.display_name);
      setAccountSavedNotice(true);
      setError("");
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  return (
    <div className="app">
      <TopNav step={step} done={done} moveTo={moveTo} hasDataset={Boolean(dataset)} account={account} accountActive={accountOpen} onOpenAccount={() => setAccountOpen(true)} />
      <main className="main">
        <header className="topbar">
          <div>
            <span className="kicker">AUTOML STUDIO</span>
            <h1>{accountOpen ? "Account" : STEPS[step][0]}</h1>
            <p>{accountOpen ? "Profile and account settings" : STEPS[step][1]}</p>
          </div>
          <div className="top-actions">
            {dataset && <span className="file-label">{file?.name || dataset.original_name}</span>}
            <span className={`api-status ${apiOnline === false ? "offline" : apiOnline === true ? "online" : "checking"}`}><i />{apiOnline === false ? "Backend offline" : apiOnline === true ? persistentDatabase === false ? "API ready · temporary database" : "API ready" : "Checking API..."}</span>
            <button className="btn primary dashboard-signout" onClick={onLogout}><Icon name="logout" size={15} />Sign out</button>
          </div>
        </header>
      {error && <Notice type="error" message={error} onDismiss={() => setError("")} />}
        {accountOpen ? <AccountStep account={account} accountName={accountName} setAccountName={setAccountName} saveAccountName={saveAccountName} savedNotice={accountSavedNotice} /> : <>
        {step === 0 && <DataStep dataset={dataset} file={file} profile={profile} busy={busy} uploadProgress={uploadProgress} upload={upload} apiOnline={apiOnline} />}
        {step === 1 && <ExploreStep profile={profile} charts={datasetCharts?.explore} selectedColumn={selectedColumn} setSelectedColumn={setSelectedColumn} target={target} />}
        {step === 2 && <CleanStep profile={profile} charts={datasetCharts?.clean} numericImpute={numericImpute} setNumericImpute={setNumericImpute} categoricalImpute={categoricalImpute} setCategoricalImpute={setCategoricalImpute} scaling={scaling} setScaling={setScaling} outlierMethod={outlierMethod} setOutlierMethod={setOutlierMethod} removeDuplicates={removeDuplicates} setRemoveDuplicates={setRemoveDuplicates} columnTypes={columnTypes} setColumnTypes={setColumnTypes} cleaningDirty={cleaningDirty} appliedNotice={cleanAppliedNotice > 0} onApply={applyCleaning} onReset={resetCleaning} />}
        {step === 3 && <FeaturesStep columns={columns} target={target} setTarget={setTarget} task={task} setTask={setTask} setSelectedModels={setSelectedModels} exclude={exclude} include={include} flaggedColumns={flaggedColumns} toggleExclude={toggleExclude} excludeFlagged={excludeFlagged} setExcludeFlagged={setExcludeFlagged} />}
        {step === 4 && <TrainStep dataset={dataset} task={task} target={target} startTraining={startTraining} busy={busy} runAll={runAll} setRunAll={setRunAll} selectedModels={selectedModels} setSelectedModels={setSelectedModels} cleaningDirty={cleaningDirty} />}
        {step === 5 && <ResultsStep job={job} results={results} history={history} selectedRunIds={selectedRunIds} setSelectedRunIds={setSelectedRunIds} predictionRows={predictionRows} setPredictionRows={setPredictionRows} predictions={predictions} predict={predict} />}
        {step === 6 && <HistoryStep history={history} datasetId={dataset?.dataset_id} selectedRunIds={selectedRunIds} setSelectedRunIds={setSelectedRunIds} openRun={async (run) => {
          try {
            const [runJob, runResults] = await Promise.all([api(`/jobs/${run.job_id}`), api(`/jobs/${run.job_id}/results`)]);
            setJob(runJob); setResults(runResults); setStep(5); setError("");
          } catch (requestError) { setError(requestError.message); }
        }} />}
        </>}
      </main>
      <Aside profile={profile} job={job} results={results} activity={activity} selectedProfile={selectedProfile} assistantQuestion={assistantQuestion} setAssistantQuestion={setAssistantQuestion} assistantMessages={assistantMessages} assistantBusy={assistantBusy} askAssistant={askAssistant} assistantChatRef={assistantChatRef} />
    </div>
  );
}

function AccountStep({ account, accountName, setAccountName, saveAccountName, savedNotice }) {
  const displayName = account?.display_name || account?.email?.split("@", 1)[0] || "User";
  const initials = displayName.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]?.toUpperCase()).join("") || "U";
  const methods = account?.auth_methods || [];
  return <>
    <section className="card account-hero"><div className="account-avatar">{initials}</div><div><span className="kicker">YOUR ACCOUNT</span><h2>{displayName}</h2><p>{account?.email || "Loading account details…"}</p></div><span className={`account-verified ${account?.is_verified ? "verified" : "unverified"}`}><Icon name={account?.is_verified ? "check" : "mail"} size={14} />{account?.is_verified ? "Verified account" : "Email not verified"}</span></section>
    <div className="two-col account-grid">
      <form className="card account-card" onSubmit={saveAccountName}><SectionTitle title="Profile details" hint="Set the name shown in your AutoML Studio workspace" /><label className="field">Display name<input type="text" value={accountName} maxLength={80} required onChange={(event) => setAccountName(event.target.value)} placeholder="Your name" /></label><label className="field">Email address<input type="email" value={account?.email || ""} readOnly /></label>{savedNotice && <Notice type="success" message="Your profile name has been saved." />}<button className="btn primary account-save" type="submit" disabled={!accountName.trim() || accountName.trim() === account?.display_name}>Save profile</button></form>
      <section className="card account-card"><SectionTitle title="Sign-in and security" hint="Connected methods and account status" /><div className="account-facts"><div><span>Email status</span><b className={account?.is_verified ? "text-verified" : "text-unverified"}>{account?.is_verified ? "Verified" : "Needs verification"}</b></div><div><span>Sign-in methods</span><b>{methods.length ? methods.map((method) => method === "email" ? "Email and password" : method[0].toUpperCase() + method.slice(1)).join(" · ") : "Not available"}</b></div><div><span>Member since</span><b>{account?.created_at ? new Date(account.created_at).toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" }) : "—"}</b></div><div><span>Account ID</span><b>#{account?.id ?? "—"}</b></div></div><div className="info">Your email address is the sign-in identity for this account. You can update your display name here.</div></section>
    </div>
  </>;
}

function TopNav({ step, done, moveTo, hasDataset, account, accountActive, onOpenAccount }) {
  return (
    <nav className="top-nav">
      <div className="brand"><b><Icon name="sparkle" size={25} /></b><span>AutoML Studio</span></div>
      <div className="workflow">
        {STEPS.map(([name, description, icon], index) => (
          <button key={name} title={!hasDataset && index !== 0 && index !== 6 ? "Upload dataset first" : name} aria-disabled={!hasDataset && index !== 0 && index !== 6} aria-current={!accountActive && step === index ? "page" : undefined} data-tooltip={!hasDataset && index !== 0 && index !== 6 ? "Upload dataset first" : undefined} className={`nav-step ${!accountActive && step === index ? "active" : ""} ${done.has(index) ? "done" : ""} ${!hasDataset && index !== 0 && index !== 6 ? "locked" : ""}`} onClick={() => moveTo(index)}>
            <strong><Icon name={icon} size={17} /></strong>
            <span><b>{name}</b><small>{description}</small></span>
          </button>
        ))}
      </div>
      <div className="nav-account"><button type="button" className={`nav-account-button ${accountActive ? "active" : ""}`} onClick={onOpenAccount} title={account?.email || "Account settings"} aria-label="Open account settings" aria-current={accountActive ? "page" : undefined}><strong><Icon name="user" size={17} /></strong><span>Account</span></button></div>
      <div className="top-nav-progress"><span>WORKFLOW</span><b>{done.size} of 6 steps</b><div><i style={{ width: `${(done.size / 6) * 100}%` }} /></div></div>
    </nav>
  );
}

function DataStep({ dataset, file, profile, busy, uploadProgress, upload, apiOnline }) {
  return (
    <>
      <section className="drop-card">
        <div className="upload-mark"><Icon name="cloud" size={34} /></div>
        <h2>Drop your CSV file here</h2>
        <p>CSV or split ZIP · up to 20 MB · first row should hold column names</p>
        <label className={`btn primary ${apiOnline === false ? "disabled" : ""}`}><Icon name="upload" size={16} />Browse files<input type="file" accept=".csv,.zip,text/csv,application/zip" onChange={upload} disabled={apiOnline === false} /></label>
        {apiOnline === false && <div className="backend-offline">Backend is not ready. Start the FastAPI server before uploading.</div>}
        {busy && <div className="upload-progress"><div className="upload-progress-top"><span>Uploading and validating</span><b>{uploadProgress}%</b></div><div className="upload-track"><i style={{ width: `${Math.max(uploadProgress, 3)}%` }} /></div><small>{uploadProgress < 100 ? "Uploading file..." : "Validating dataset..."}</small></div>}
      </section>
      <section className="card">
        <SectionTitle title="Dataset overview" hint={dataset ? "Validated by the backend" : "Upload a dataset to begin"} />
        {profile ? <><div className="format-note"><Icon name="check" size={15} />{dataset.format === "provided" ? "Preserved train.csv, validation.csv and test.csv" : dataset.format === "train_test" ? "train.csv and test.csv detected; cross-validation will replace validation" : "Standard CSV dataset"}</div><div className="stat-grid">{[
          ["Rows", profile.n_rows.toLocaleString()],
          ["Columns", profile.n_columns],
          ["Missing cells", profile.missing_cells.toLocaleString()],
          ["Duplicates", profile.duplicate_rows]
        ].map(([label, value]) => <div className="stat" key={label}><small>{label}</small><b>{value}</b></div>)}</div><Preview profile={profile} file={file} /></> : <div className="empty">Your validated preview and detected column types will appear here.</div>}
      </section>
    </>
  );
}

function ExploreStep({ profile, charts, selectedColumn, setSelectedColumn, target }) {
  if (!profile) return <EmptyState text="Upload a dataset first." />;
  const maxMissing = Math.max(...profile.columns.map((column) => column.missing_pct), 1);
  const numeric = charts?.histograms || [];
  const categorical = charts?.categories || [];
  const strings = charts?.strings || [];
  return <><div className="stat-grid">{[["Rows", profile.n_rows.toLocaleString()], ["Columns", profile.n_columns], ["Missing cells", profile.missing_cells.toLocaleString()], ["Duplicates", profile.duplicate_rows]].map(([label, value]) => <div className="stat" key={label}><small>{label}</small><b>{value}</b></div>)}</div>
    <div className="two-col"><section className="card"><SectionTitle title="Missing values" hint="Missing cell percentages are highlighted in red" />{profile.columns.map((column) => <div className="bar-row" key={column.name}><span>{column.name}</span><div className="bar"><i className={column.missing_pct > 0 ? "missing-bar" : ""} style={{ width: `${(column.missing_pct / maxMissing) * 100}%` }} /></div><small className={column.missing_pct > 0 ? "missing-value" : ""}>{column.missing_pct}%</small></div>)}</section>
      <section className="card"><SectionTitle title="Column profile" hint="Inspect detected type and quality" /><select value={selectedColumn} onChange={(event) => setSelectedColumn(event.target.value)}>{profile.columns.map((column) => <option key={column.name}>{column.name}</option>)}</select>{profile.columns.filter((column) => column.name === selectedColumn).map((column) => <div className="profile-detail" key={column.name}><b>{column.name}</b><span className="pill">{column.display_kind || column.kind}</span><dl><dt>Data type</dt><dd>{column.dtype}</dd><dt>Unique values</dt><dd>{column.unique.toLocaleString()}</dd><dt>Missing</dt><dd className={column.missing_pct > 0 ? "missing-value" : ""}>{column.missing_pct}%</dd><dt>Target</dt><dd>{column.name === target ? "Selected" : "No"}</dd></dl></div>)}</section></div>
    <section className="card"><SectionTitle title="Numeric columns" hint="Histograms, distribution summaries, and pairwise correlation" />{numeric.length ? <div className="chart-grid">{numeric.map((chart) => <BarChart key={chart.name} title={`${chart.name} · histogram`} labels={chart.bins} values={chart.counts} variant="numeric" />)}{(charts?.numeric_summaries || []).map((item) => <BoxPlot key={item.name} item={item} />)}</div> : <div className="empty small">No numeric columns found.</div>}{charts?.numeric_correlations?.length > 0 && <Heatmap data={charts.numeric_correlations} labels={[...new Set(charts.numeric_correlations.map((x) => x.x))]} />}</section>
    <section className="card"><SectionTitle title="Categorical columns" hint="Category share and frequency comparisons" />{categorical.length ? <div className="chart-grid">{categorical.flatMap((chart) => [<DonutChart key={chart.name} title={chart.name} items={chart.counts} />, <BarChart key={chart.name + "-bars"} title={`${chart.name} · counts`} labels={chart.counts.map((x) => x.label)} values={chart.counts.map((x) => x.value)} variant="category" />])}</div> : <div className="empty small">No categorical columns found.</div>}</section>
    <section className="card"><SectionTitle title="String columns" hint="Most frequent text values, shown separately from categorical fields" />{strings.length ? <div className="chart-grid">{strings.map((chart) => <Fragment key={chart.name}><DonutChart title={`${chart.name} · share`} items={chart.counts} /><BarChart title={`${chart.name} · most common values`} labels={chart.counts.map((x) => x.label)} values={chart.counts.map((x) => x.value)} variant="category" /></Fragment>)}</div> : <div className="empty small">No string columns found.</div>}</section>
    {charts?.target && <section className="card"><SectionTitle title={`Target distribution: ${charts.target.name}`} hint="Distribution fetched from the dataset chart API" />{charts.target.kind === "numeric" ? <BarChart title={charts.target.name} labels={charts.target.bins} values={charts.target.counts} /> : <BarChart title={charts.target.name} labels={charts.target.counts.map((x) => x.label)} values={charts.target.counts.map((x) => x.value)} />}</section>}
    <section className="card"><SectionTitle title="Data-quality warnings" hint="Detected issues are shown without changing your data" />{profile.warnings.length ? profile.warnings.map((warning) => <div className="warning" key={warning}>! {warning}</div>) : <div className="success">No warnings detected</div>}</section></>;
}

function CleanStep({ profile, charts, numericImpute, setNumericImpute, categoricalImpute, setCategoricalImpute, scaling, setScaling, outlierMethod, setOutlierMethod, removeDuplicates, setRemoveDuplicates, columnTypes, setColumnTypes, cleaningDirty, appliedNotice, onApply, onReset }) {
  const [tab, setTab] = useState("missing");
  const tabs = [["missing", "Missing Values", "chart"], ["duplicates", "Duplicates", "database"], ["outliers", "Outliers", "chart"], ["types", "Data Types", "settings"], ["scaling", "Scaling", "target"], ["summary", "Summary", "star"]];
  const missing = profile?.columns?.filter((column) => column.missing_pct > 0) || [];
  const numeric = profile?.columns?.filter((column) => column.kind === "numeric").length || 0;
  const categorical = profile?.columns?.filter((column) => column.kind !== "numeric").length || 0;
  const change = (setter) => (value) => setter(value);
  return <section className="card clean-workspace">
    <div className="clean-dataset"><Icon name="database" size={20} /><div><b>{profile?.n_rows?.toLocaleString() || "—"} rows · {profile?.n_columns || 0} columns</b><small>Cleaning configuration is saved with this workspace and used by model training.</small></div></div>
    {cleaningDirty && <div className="warning clean-pending">Cleaning edits are pending. Apply them before starting training.</div>}
    {!cleaningDirty && appliedNotice && <Notice className="clean-pending" type="success" message="Cleaning settings are applied and ready for training." />}
    <div className="clean-tabs" role="tablist" aria-label="Data cleaning options">{tabs.map(([id, label, icon]) => <button type="button" role="tab" aria-selected={tab === id} className={tab === id ? "active" : ""} key={id} onClick={() => setTab(id)}><Icon name={icon} size={15} />{label}</button>)}</div>
    {tab === "missing" && <section className="clean-panel"><SectionTitle title="Missing values" hint="Choose imputation strategies for numeric and categorical columns" />
      <div className="clean-stats"><div><small>Total missing cells</small><b>{profile?.missing_cells?.toLocaleString() || 0}</b></div><div><small>Numeric columns</small><b>{numeric}</b></div><div><small>Categorical columns</small><b>{categorical}</b></div></div>
      <div className="clean-two-col"><div className="clean-option"><h4>Numeric columns</h4><p>Choose how blank numeric values are filled inside each training fold.</p><Control label="Imputation strategy" value={numericImpute} options={[["median", "Median"], ["mean", "Mean"], ["most_frequent", "Most frequent"], ["constant", "Fill with 0"]]} setValue={change(setNumericImpute)} /></div><div className="clean-option"><h4>Categorical columns</h4><p>Fill empty categories before one-hot encoding.</p><Control label="Imputation strategy" value={categoricalImpute} options={[["most_frequent", "Most frequent"], ["constant", "Use ‘Missing’"]]} setValue={change(setCategoricalImpute)} /></div></div>
      <div className="clean-table"><h4>Columns with missing values</h4>{missing.length ? missing.map((column) => <div className="clean-row" key={column.name}><b>{column.name}</b><span className="pill">{column.display_kind || column.kind}</span><span>{column.missing_pct}% missing</span><small>{column.unique.toLocaleString()} unique</small></div>) : <div className="empty small">No missing values detected in this dataset.</div>}</div>
      <div className="info">Imputers are fitted on training data only to avoid leaking information into validation or test data.</div>
    </section>}
    {tab === "duplicates" && <section className="clean-panel"><SectionTitle title="Duplicate rows" hint="Choose whether exact duplicate records should be removed before model fitting" /><div className="clean-highlight"><Icon name="database" size={22} /><div><b>{profile?.duplicate_rows?.toLocaleString() || 0} duplicate rows detected</b><p>Only fully identical rows are considered duplicates. The original uploaded file stays unchanged.</p></div></div><label className="clean-check"><input type="checkbox" checked={removeDuplicates} onChange={(event) => change(setRemoveDuplicates)(event.target.checked)} /><span><b>Remove duplicate rows for training</b><small>Duplicate records will be dropped from the training dataset before the train/test split.</small></span></label></section>}
    {tab === "outliers" && <section className="clean-panel"><SectionTitle title="Outlier handling" hint="Reduce the influence of extreme numeric values while preserving rows" /><div className="clean-option"><Control label="Numeric outlier treatment" value={outlierMethod} options={[["none", "Keep as-is"], ["iqr_clip", "Clip using IQR fences"]]} setValue={change(setOutlierMethod)} /><p>When enabled, values below Q1 − 1.5×IQR or above Q3 + 1.5×IQR are clipped. Fences are learned from each training fold only.</p></div><div className="info">Clipping keeps all records and does not alter categorical columns.</div></section>}
    {tab === "types" && <section className="clean-panel"><SectionTitle title="Data types" hint="Override automatic column detection when a field has the wrong type" /><div className="clean-type-list">{(profile?.columns || []).map((column) => <label className="clean-type-row" key={column.name}><span><b>{column.name}</b><small>{column.dtype} · {column.unique.toLocaleString()} unique values</small></span><select value={columnTypes[column.name] || "auto"} onChange={(event) => { const value = event.target.value; setColumnTypes((current) => { const next = { ...current }; if (value === "auto") delete next[column.name]; else next[column.name] = value; return next; }); }}><option value="auto">Auto ({column.display_kind || column.kind})</option><option value="numeric">Numeric</option><option value="categorical">Categorical</option></select></label>)}</div><div className="info">Numeric overrides are safely converted to numbers; values that cannot be parsed are treated as missing and imputed.</div></section>}
    {tab === "scaling" && <section className="clean-panel"><SectionTitle title="Feature scaling" hint="Normalize numeric features for scale-sensitive models" /><div className="clean-option"><Control label="Scaling method" value={scaling} options={[["standard", "Standard (z-score)"], ["minmax", "Min-max (0–1)"], ["robust", "Robust (median/IQR)"], ["none", "No scaling"]]} setValue={change(setScaling)} /><p>Scaling is fitted inside each cross-validation fold and applied only to numeric input features.</p></div></section>}
    {tab === "summary" && <section className="clean-panel"><SectionTitle title="Cleaning summary" hint="Review the preprocessing that will be used by your next model run" /><div className="clean-summary-list"><div><span>Numeric missing values</span><b>{numericImpute === "constant" ? "Fill with 0" : numericImpute.replace("_", " ")}</b></div><div><span>Categorical missing values</span><b>{categoricalImpute === "constant" ? "Fill with Missing" : "Most frequent"}</b></div><div><span>Duplicates</span><b>{removeDuplicates ? "Remove before training" : "Keep"}</b></div><div><span>Outliers</span><b>{outlierMethod === "iqr_clip" ? "Clip with IQR fences" : "Keep as-is"}</b></div><div><span>Scaling</span><b>{scaling}</b></div><div><span>Custom data types</span><b>{Object.keys(columnTypes).length || "Auto detected"}</b></div></div><div className="info">Settings are applied by the backend training pipeline. Your uploaded dataset is never overwritten.</div></section>}
    <div className="clean-footer"><button className="btn secondary" type="button" onClick={onReset}>Reset cleaning options</button><button className="btn primary" type="button" onClick={onApply} disabled={!cleaningDirty}><Icon name="check" size={15} />{cleaningDirty ? "Apply cleaning changes" : "Settings applied"}</button></div>
    {charts?.missing_before_after?.length > 0 && <section className="clean-impact"><SectionTitle title="Missing-value preview" hint="Current dataset missing percentages" /><BarChart title="Missing values (%)" labels={charts.missing_before_after.map((item) => item.name)} values={charts.missing_before_after.map((item) => item.before)} variant="numeric" /></section>}
  </section>;
}
function FeaturesStep({ columns, target, setTarget, task, setTask, setSelectedModels, exclude, include, flaggedColumns, toggleExclude, excludeFlagged, setExcludeFlagged }) {
  const titanic = target.toLowerCase() === "survived";
  return <>
    <section className="card">
      <SectionTitle title="What do you want to predict?" hint="Choose the kind of problem" />
      <div className="task-grid">{[["classification", "target", "Classification", "Predict a category"], ["regression", "chart", "Regression", "Predict a number"]].map(([value, icon, name, description]) => <button className={`task ${task === value ? "selected" : ""}`} key={value} onClick={() => { setTask(value); setSelectedModels([]); }}><b><Icon name={icon} size={24} /></b><strong>{name}</strong><span>{description}</span></button>)}</div>
      <label className="field">Target column<select value={target} onChange={(event) => setTarget(event.target.value)}><option value="">Select a column</option>{columns.map((column) => <option key={column.name}>{column.name}</option>)}</select></label>
      {titanic && <div className="info"><b>Titanic setup:</b> <code>Survived</code> is the target. The other columns are features used to predict whether a passenger survived.</div>}
    </section>
    <section className="card">
      <SectionTitle title="Input columns" hint="Choose which columns to include in this run" />
      <div className="chips">{columns.filter((column) => column.name !== target).map((column) => {
        const autoExcluded = excludeFlagged && flaggedColumns.includes(column.name) && !include.includes(column.name);
        const isExcluded = exclude.includes(column.name) || autoExcluded;
        return <button type="button" title={isExcluded ? "Excluded from this run" : include.includes(column.name) ? "Included for this run" : "Included in training"} className={`chip ${isExcluded ? "selected" : ""}`} key={column.name} onClick={() => toggleExclude(column.name)}>{isExcluded ? <Icon name="target" size={13} /> : <Icon name="check" size={13} />}{column.name}<em>{autoExcluded ? "auto excluded" : column.kind}</em></button>;
      })}</div>
      <label className="switch"><input type="checkbox" checked={excludeFlagged} onChange={(event) => setExcludeFlagged(event.target.checked)} /><span />Exclude flagged columns automatically</label>
      {include.length > 0 && <div className="info">Manually included columns override automatic exclusions: {include.join(", ")}</div>}
    </section>
  </>;
}
function TrainStep({ dataset, task, target, startTraining, busy, runAll, setRunAll, selectedModels, setSelectedModels, cleaningDirty }) {
  const models = task === "classification"
    ? [["Logistic Regression", "Fast, explainable"], ["Decision Tree", "Readable rules"], ["Random Forest", "Strong all-rounder"], ["Gradient Boosting", "Powerful ensemble"], ["KNN", "Nearest neighbours"], ["SVM", "Strong boundary model"]]
    : [["Linear Regression", "Simple baseline"], ["Decision Tree", "Readable rules"], ["Random Forest", "Captures curves"], ["Gradient Boosting", "Powerful ensemble"], ["KNN", "Nearest neighbours"], ["SVR", "Nonlinear regression"]];
  function toggleModel(name) {
    setSelectedModels((current) => current.includes(name) ? current.filter((model) => model !== name) : [...current, name]);
  }
  return <section className="card train-card"><SectionTitle title="Ready to train" hint="Choose individual models or compare every compatible model" /><div className="train-summary"><div><small>Dataset</small><b>{dataset?.original_name || "Not selected"}</b></div><div><small>Task</small><b>{task}</b></div><div><small>Target</small><b>{target || "Not selected"}</b></div></div>{cleaningDirty && <div className="warning">You have unapplied cleaning changes. Open Clean and apply them before training.</div>}<label className="switch model-mode"><input type="checkbox" checked={runAll} onChange={(event) => setRunAll(event.target.checked)} /><span />Run all compatible models</label><div className="model-grid">{models.map(([name, description]) => <button type="button" className={`model ${runAll || selectedModels.includes(name) ? "chosen" : ""}`} key={name} onClick={() => !runAll && toggleModel(name)}><b>{name}</b><span>{description}</span><em>{runAll || selectedModels.includes(name) ? "Selected" : "Click to select"}</em></button>)}</div><button className="btn primary train-button" disabled={!dataset || !target || busy || cleaningDirty || (!runAll && selectedModels.length === 0)} onClick={startTraining}>{busy ? "Starting..." : <><Icon name="play" size={15} />Start training</>}</button></section>;
}

function ResultsStep({ job, results, predictionRows, setPredictionRows, predictions, predict }) {
  if (job && job.status !== "completed") return <section className="card job-card"><SectionTitle title={job.status === "failed" ? "Training failed" : "Training in progress"} hint={job.status === "failed" ? "Review the error and adjust your settings" : job.stage} /><div className="big-progress"><i style={{ width: `${job.progress}%` }} /></div><div className="progress-label"><span>{job.progress}%</span><b>{job.status}</b></div><pre className="log">{job.logs.join("\n")}</pre></section>;
  if (!results) return <EmptyState text="Start a training job to see results here." />;
  const metrics = Object.entries(results.test_metrics || {}).filter(([key]) => !["labels", "confusion_matrix", "status", "reason"].includes(key));
  const validScores = (results.leaderboard || []).filter((row) => row.cv_mean !== null && row.cv_mean !== undefined);
  const usedFeatures = results.feature_columns || [...(results.numeric_columns || []), ...(results.categorical_columns || [])];
  async function downloadModel() {
    try {
      const response = await fetch(`${API_URL}/models/${results.model_id}/download`, { headers: { Authorization: `Bearer ${getAccessToken() || ""}` } });
      if (!response.ok) throw new Error("Model download failed. Please sign in again.");
      const blob = await response.blob(); const url = URL.createObjectURL(blob); const link = document.createElement("a"); link.href = url; link.download = "pipeline.joblib"; link.click(); URL.revokeObjectURL(url);
    } catch (error) { window.alert(error.message); }
  }
  return <><div className="card winner"><div><span className="kicker">BEST MODEL</span><h2>{results.best_model}</h2></div><button className="btn secondary" onClick={downloadModel}><Icon name="download" size={15} />Download model</button><div className="metric-grid">{metrics.map(([key, value]) => <div className="metric" key={key}><b>{value}</b><small>{key.replaceAll("_", " ")}</small></div>)}</div></div>
    <section className="card"><SectionTitle title="Features used for this run" hint="This is the exact feature set used to produce the results below" /><div className="feature-run-details"><div><b>Included ({usedFeatures.length})</b><p>{usedFeatures.length ? usedFeatures.join(", ") : "No features reported"}</p></div><div><b>Excluded ({results.excluded_columns?.length || 0})</b><p>{results.excluded_columns?.length ? results.excluded_columns.join(", ") : "None"}</p></div></div></section>
    {!results.test_evaluation_available && <div className="card info"><b>Test set not scored</b><br />This dataset has no labeled test target. Cross-validation scores below are available for run comparison.</div>}
    <section className="card"><SectionTitle title="Model comparison" hint={`${results.cv_folds}-fold cross-validation`} /><div className="chart-grid">{validScores.length > 0 && <BarChart title="Cross-validation scores" labels={validScores.map((row) => row.model)} values={validScores.map((row) => row.cv_mean)} variant="category" />}{validScores.length > 0 && <BarChart title="Score variability" labels={validScores.map((row) => row.model)} values={validScores.map((row) => row.cv_std ?? 0)} variant="category" />}{validScores.length > 0 && <BarChart title="Training time (seconds)" labels={validScores.map((row) => row.model)} values={validScores.map((row) => row.seconds ?? 0)} variant="category" />}</div><div className="table-wrap"><table><thead><tr><th>Model</th><th>CV score</th><th>Std</th><th>Time</th><th>Evaluation metrics</th><th>Parameters</th></tr></thead><tbody>{(results.leaderboard || []).map((row) => <tr key={row.model}><td>{row.model}{row.model === results.best_model && <span className="best-tag">Best</span>}</td><td>{row.cv_mean ?? row.error}</td><td>{row.cv_std ?? "-"}</td><td>{row.seconds ?? "-"}s</td><td><code>{JSON.stringify(row.evaluation_metrics || {})}</code>{row.evaluation_split && <small>{row.evaluation_split} split</small>}</td><td><code>{JSON.stringify(row.params || {})}</code></td></tr>)}</tbody></table></div></section>
    {(results.charts?.confusion_matrix || results.charts?.roc || results.charts?.feature_importance?.length || results.charts?.residuals || results.charts?.prediction_scatter) && <section className="card"><SectionTitle title="Model evaluation charts" hint="Evaluation data saved with this model run" /><div className="chart-grid">{results.charts.confusion_matrix && <ConfusionChart chart={results.charts.confusion_matrix} />}{results.charts.roc && <RocChart chart={results.charts.roc} />}{results.charts.feature_importance?.length > 0 && <BarChart title="Feature importance" labels={results.charts.feature_importance.map((x) => x.feature)} values={results.charts.feature_importance.map((x) => x.importance)} variant="category" />}{results.charts.residuals && <BarChart title="Residual distribution" labels={results.charts.residuals.predicted.map((_, i) => `${i + 1}`)} values={results.charts.residuals.residual} variant="category" />}{results.charts.prediction_scatter && <ScatterPlot chart={results.charts.prediction_scatter} />}</div></section>}
    <section className="card predict-box"><SectionTitle title="Try the trained model" hint="Use the feature column names in a JSON object" /><textarea value={predictionRows} onChange={(event) => setPredictionRows(event.target.value)} /><button className="btn primary" onClick={predict}><Icon name="play" size={15} />Run prediction</button>{predictions && <pre className="prediction">{JSON.stringify(predictions, null, 2)}</pre>}</section></>;
}
function HistoryStep({ history = [], datasetId, selectedRunIds, setSelectedRunIds, openRun }) {
  const [datasetOnly, setDatasetOnly] = useState(Boolean(datasetId));
  const visibleHistory = datasetOnly && datasetId ? history.filter((run) => run.dataset_id === datasetId) : history;
  const selected = visibleHistory.filter((run) => selectedRunIds.includes(run.job_id) && run.status === "completed");
  const toggle = (id) => setSelectedRunIds((current) => current.includes(id) ? current.filter((item) => item !== id) : [...current, id].slice(-3));
  return <section className="card run-history"><SectionTitle title="Run history" hint="Training runs, per model scores, hyperparameters, and saved evaluation results" />
    {datasetId && <label className="switch history-filter"><input type="checkbox" checked={datasetOnly} onChange={(event) => setDatasetOnly(event.target.checked)} /><span />Show this dataset only <small className="history-count">{visibleHistory.length} of {history.length} runs</small></label>}
    {!visibleHistory.length && <div className="empty small">No model runs found{datasetOnly ? " for this dataset" : ""}.</div>}
    {selected.length > 1 && <div className="table-wrap run-compare"><table><thead><tr><th>Run</th><th>Best model</th><th>CV folds</th><th>Test metrics</th><th>Included columns</th><th>Excluded columns</th><th>Preprocessing</th><th>Best model parameters</th></tr></thead><tbody>{selected.map((run) => <tr key={run.job_id}><td>{new Date(run.created_at).toLocaleString()}<small>{run.target} · {run.task}</small></td><td>{run.best_model}</td><td>{run.cv_folds ?? "-"}</td><td><code>{JSON.stringify(run.metrics)}</code></td><td>{run.feature_columns?.length ? run.feature_columns.join(", ") : "—"}</td><td>{run.excluded_columns?.length ? run.excluded_columns.join(", ") : "None"}</td><td><code>{JSON.stringify(run.options)}</code></td><td><code>{JSON.stringify(run.params)}</code></td></tr>)}</tbody></table></div>}
    <div className="run-list">{visibleHistory.map((run) => <details className="run-item" key={run.job_id}><summary><label className="run-select" onClick={(event) => event.stopPropagation()}><input type="checkbox" checked={selectedRunIds.includes(run.job_id)} disabled={run.status !== "completed"} onChange={() => toggle(run.job_id)} aria-label={`Select ${run.job_id} for comparison`} /></label><span className="run-date">{new Date(run.created_at).toLocaleString()}</span><b>{run.best_model || run.status}</b><span>{run.target} · {run.task}</span><span className={`status ${run.status}`}>{run.status}</span></summary>{run.status === "completed" ? <div className="run-detail"><div className="run-detail-head"><h4>Run evaluation and settings</h4><button className="btn secondary" onClick={() => openRun(run)}>Open full results</button></div><div className="run-meta"><span><small>Evaluation</small><b>{Object.keys(run.metrics || {}).length ? JSON.stringify(run.metrics) : "No labeled test set. Compare cross-validation scores below."}</b></span><span><small>Preprocessing</small><b>{JSON.stringify(run.options)}</b></span><span><small>Included columns</small><b>{run.feature_columns?.length ? run.feature_columns.join(", ") : "Not available"}</b></span><span><small>Excluded columns</small><b>{run.excluded_columns?.length ? run.excluded_columns.join(", ") : "None"}</b></span></div><h4>Model results and hyperparameters</h4><div className="table-wrap"><table><thead><tr><th>Model</th><th>CV score</th><th>CV std</th><th>Time</th><th>Evaluation metrics</th><th>Parameters</th></tr></thead><tbody>{(run.leaderboard || []).map((row) => <tr key={row.model}><td>{row.model}{row.model === run.best_model && <span className="best-tag">Best</span>}</td><td>{row.cv_mean ?? row.error ?? "-"}</td><td>{row.cv_std ?? "-"}</td><td>{row.seconds ?? "-"}s</td><td><code>{JSON.stringify(row.evaluation_metrics || {})}</code>{row.evaluation_split && <small>{row.evaluation_split} split</small>}</td><td><code>{JSON.stringify(row.params || {})}</code></td></tr>)}</tbody></table></div></div> : <div className="run-detail">{run.error || "This run has no saved evaluation results."}</div>}</details>)}</div>
  </section>;
}

const CHART_COLORS = ["#3568a8", "#e07a32", "#39856b", "#8d5caf", "#cf5260", "#c4a12e", "#3c9cad", "#75624d", "#d05b9b", "#678b43"];
function BarChart({ title, labels = [], values = [], series, variant = "default" }) {
  const rows = (series || [{ name: "Values", values }]).filter((item) => Array.isArray(item.values));
  const count = Math.min(labels.length, ...rows.map((item) => item.values.length));
  const max = Math.max(1, ...rows.flatMap((item) => item.values.slice(0, count).map((value) => Math.abs(Number(value) || 0))));
  return <div className="chart-card"><b>{title}</b><div className="chart-axis-label">Count / value</div><div className="chart-bars">{Array.from({ length: count }, (_, index) => <div className="chart-bar-group" key={`${labels[index]}-${index}`} title={`${labels[index]}: ${rows.map((row) => `${row.name} ${row.values[index]}`).join(", ")}`}><div className="chart-bar-stack">{rows.map((row, seriesIndex) => <i key={row.name} style={{ height: `${Math.max(2, Math.abs(Number(row.values[index]) || 0) / max * 100)}%`, background: variant === "category" && rows.length === 1 ? CHART_COLORS[index % CHART_COLORS.length] : CHART_COLORS[seriesIndex % CHART_COLORS.length] }} />)}</div><small>{String(labels[index]).slice(0, 12)}</small></div>)}</div>{!(variant === "category" && rows.length === 1) && <div className="chart-legend">{rows.map((row, index) => <span key={row.name}><i style={{ background: CHART_COLORS[index % CHART_COLORS.length] }} />{row.name}</span>)}</div>}</div>;
}
function DonutChart({ title, items = [] }) {
  const total = items.reduce((sum, item) => sum + (Number(item.value) || 0), 0) || 1;
  const circumference = 2 * Math.PI * 44;
  let offset = 0;
  return <div className="chart-card"><b>{title} · composition</b><div className="donut-wrap"><svg viewBox="0 0 120 120" role="img" aria-label={`${title} category composition`}><circle cx="60" cy="60" r="44" fill="none" stroke="#e6eaf0" strokeWidth="18" />{items.map((item, index) => { const length = (Number(item.value) || 0) / total * circumference; const circle = <circle key={item.label} cx="60" cy="60" r="44" fill="none" stroke={CHART_COLORS[index % CHART_COLORS.length]} strokeWidth="18" strokeDasharray={`${length} ${circumference - length}`} strokeDashoffset={-offset} transform="rotate(-90 60 60)" />; offset += length; return circle; })}<text x="60" y="57" textAnchor="middle">{total.toLocaleString()}</text><text x="60" y="70" textAnchor="middle">values</text></svg><div className="donut-legend">{items.slice(0, 10).map((item, index) => <span key={item.label}><i style={{ background: CHART_COLORS[index % CHART_COLORS.length] }} />{item.label} <b>{item.value}</b></span>)}</div></div></div>;
}
function BoxPlot({ item }) { const span = item.max - item.min || 1; const pct = (value) => `${8 + (value - item.min) / span * 84}%`; return <div className="chart-card"><b>{item.name} · spread</b><div className="boxplot"><i className="box-whisker" style={{ left: pct(item.min), width: `${(item.max - item.min) / span * 84}%` }} /><i className="box-range" style={{ left: pct(item.q1), width: `${Math.max(1, (item.q3 - item.q1) / span * 84)}%` }} /><i className="box-median" style={{ left: pct(item.median) }} /><i className="box-mean" style={{ left: pct(item.mean) }} /></div><div className="box-labels"><span>Min {item.min}</span><span>Q1 {item.q1}</span><span>Median {item.median}</span><span>Q3 {item.q3}</span><span>Max {item.max}</span></div><div className="chart-legend"><span><i style={{ background: "#3568a8" }} />Interquartile range</span><span><i style={{ background: "#cf5260" }} />Median</span><span><i style={{ background: "#e07a32" }} />Mean</span></div></div>; }
function Heatmap({ data, labels }) { const values = Object.fromEntries(data.map((item) => [`${item.x}:${item.y}`, item.value])); return <div className="chart-card heatmap-card"><b>Numeric correlation</b><div className="heatmap" style={{ gridTemplateColumns: `100px repeat(${labels.length}, minmax(34px, 1fr))` }}><span />{labels.map((label) => <small key={label}>{label}</small>)}{labels.map((row) => <Fragment key={row}><small>{row}</small>{labels.map((col) => { const value = values[`${row}:${col}`] ?? 0; return <span key={`${row}:${col}`} title={`${row} / ${col}: ${value}`} style={{ background: value < 0 ? `rgba(49,105,168,${Math.abs(value)})` : `rgba(207,82,96,${value})` }}>{value.toFixed(2)}</span>; })}</Fragment>)}</div><div className="chart-legend"><span>Blue: negative</span><span>Red: positive</span></div></div>; }
function ScatterPlot({ chart }) {
  if (!chart.actual?.length || !chart.predicted?.length) return null;
  const min = Math.min(...chart.actual, ...chart.predicted);
  const max = Math.max(...chart.actual, ...chart.predicted);
  const span = max - min || 1;
  return <div className="chart-card"><b>Actual vs predicted</b><svg className="line-chart scatter-chart" viewBox="0 0 270 200" role="img" aria-label="Actual versus predicted values"><line x1="22" y1="176" x2="258" y2="26" stroke="#98a2b3" strokeDasharray="5 5"/>{chart.actual.map((value, index) => { const cx = 22 + ((value - min) / span) * 236; const cy = 176 - ((chart.predicted[index] - min) / span) * 150; return <circle key={index} cx={cx} cy={cy} r="3.2" fill={CHART_COLORS[index % CHART_COLORS.length]} opacity=".78" />; })}<text x="115" y="197">Actual</text><text x="2" y="18">Predicted</text></svg></div>;
}function ConfusionChart({ chart }) { const size = Math.max(1, ...chart.matrix.flatMap((row) => row)); return <div className="chart-card"><b>Confusion matrix</b><div className="matrix">{chart.matrix.flatMap((row, y) => row.map((value, x) => { const color = y === x ? "57,133,107" : "207,82,96"; return <div key={`${y}-${x}`} title={`Actual ${chart.labels[y]}, predicted ${chart.labels[x]}`} style={{ background: `rgba(${color},${0.12 + 0.75 * value / size})` }}>{value}<small>Actual {chart.labels[y]} · Pred {chart.labels[x]}</small></div>; }))}</div></div>; }
function RocChart({ chart }) { const points = chart.fpr.map((x, i) => `${32 + x * 220},${168 - chart.tpr[i] * 136}`).join(" "); return <div className="chart-card"><b>ROC curve · AUC {chart.auc}</b><svg className="line-chart" viewBox="0 0 270 190" role="img" aria-label="ROC curve"><line x1="32" y1="168" x2="252" y2="32" stroke="#d8d0c4" strokeDasharray="4 4"/><polyline points={points} fill="none" stroke={CHART_COLORS[0]} strokeWidth="3"/><line x1="32" y1="168" x2="252" y2="168" stroke="#938b80"/><line x1="32" y1="168" x2="32" y2="32" stroke="#938b80"/><text x="120" y="187">False positive rate</text><text x="3" y="20">True positive</text></svg></div>; }

function Aside({ profile, job, results, activity, selectedProfile, assistantQuestion, setAssistantQuestion, assistantMessages, assistantBusy, askAssistant, assistantChatRef }) {
  return <aside className="right">
    <section className="card">
      <SectionTitle title="Workspace" hint={profile ? `${profile.n_rows.toLocaleString()} rows loaded` : "Waiting for data"} />
      {profile ? <><div className="mini-stat"><b>{profile.n_columns}</b><span>columns detected</span></div><div className="mini-stat"><b>{profile.warnings.length}</b><span>quality warnings</span></div>{selectedProfile && <div className="ai"><b>{selectedProfile.name}</b><br />{selectedProfile.kind} · {selectedProfile.missing_pct}% missing</div>}</> : <div className="empty small">Upload a CSV to activate the workspace.</div>}
    </section>
    <section className="card assistant">
      <SectionTitle title="AI assistant" hint="Context-aware help" />
      <div className="assistant-chat" ref={assistantChatRef}>
        {assistantMessages.map((message, index) => <div className={`assistant-message ${message.role}`} key={`${message.role}-${index}`}><span className="message-avatar"><Icon name={message.role === "user" ? "user" : "sparkle"} size={14} /><b>{message.role === "user" ? "You" : "Assistant"}</b></span><p>{message.content}</p></div>)}
        {assistantBusy && <div className="assistant-message assistant"><span className="message-avatar"><Icon name="sparkle" size={14} /><b>Assistant</b></span><p>Thinking…</p></div>}
      </div>
      <textarea id="assistant-question" value={assistantQuestion} onChange={(event) => setAssistantQuestion(event.target.value)} placeholder="Ask what to do next..." onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); askAssistant(); } }} />
      <button className="btn primary" onClick={askAssistant} disabled={assistantBusy}><Icon name="send" size={15} />{assistantBusy ? "Thinking…" : "Send message"}</button>
    </section>
    <section className="card">
      <SectionTitle title="Activity" hint="Live workflow updates" />
      {activity.length ? activity.slice(-7).reverse().map((item, index) => <div className="timeline" key={`${item}-${index}`}><i />{item}</div>) : <div className="empty small">No activity yet.</div>}
      {job && <span className={`status ${job.status}`}>{job.status}</span>}{results && <div className="success">✓ Model ready</div>}
    </section>
  </aside>;
}
function SectionTitle({ title, hint }) {
  const normalized = title.toLowerCase();
  const icon = normalized.includes("assistant") ? "sparkle" : normalized.includes("workspace") || normalized.includes("dataset") ? "database" : normalized.includes("activity") || normalized.includes("history") ? "clock" : normalized.includes("missing") || normalized.includes("warning") ? "target" : normalized.includes("numeric") || normalized.includes("categorical") || normalized.includes("string") || normalized.includes("distribution") || normalized.includes("evaluation") ? "chart" : normalized.includes("feature") || normalized.includes("column") ? "settings" : normalized.includes("run") || normalized.includes("model") || normalized.includes("train") ? "play" : "sparkle";
  return <div className="section-title"><span className="section-icon"><Icon name={icon} size={18} /></span><div><h3>{title}</h3><p>{hint}</p></div></div>;
}
function Notice({ type = "success", message, onDismiss, className = "" }) {
  const icon = type === "error" ? "target" : type === "info" ? "sparkle" : "check";
  return <div className={`notice notice-${type} ${className}`} role={type === "error" ? "alert" : "status"}><span className="notice-mark"><Icon name={icon} size={16} /></span><b>{message}</b>{onDismiss && <button type="button" onClick={onDismiss} aria-label="Dismiss message">×</button>}</div>;
}
function Control({ label, value, options, setValue }) { return <label className="field">{label}<div className="seg">{options.map(([option, name]) => <button type="button" className={value === option ? "active" : ""} key={option} onClick={() => setValue(option)}>{name}</button>)}</div></label>; }
function Preview({ profile, file }) { return <><p className="preview-name">{file?.name} · detected column types</p><div className="preview-grid">{profile.columns.map((column) => <div className="preview-column" key={column.name}><b title={column.name}>{column.name}</b><span className="pill">{column.display_kind || column.kind}</span><small className={column.missing_pct ? "missing-value" : ""}>{column.missing_pct ? `${column.missing_pct}% missing` : "Ready"}</small></div>)}</div></>; }
function EmptyState({ text }) { return <section className="card empty-state"><Icon name="database" size={28} /><h2>{text}</h2><p>Complete the data step to continue.</p></section>; }

const AUTH_API_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";

function AuthScreen() {
  const [path, setPath] = useState(window.location.pathname);
  const [email, setEmail] = useState(sessionStorage.getItem("automl_signup_email") || "");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [verificationCode, setVerificationCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [resetToken, setResetToken] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [verified, setVerified] = useState(false);
  const oauthCallbackHandled = useRef(false);
  const navigate = (next) => { window.history.pushState({}, "", next); setPath(next.split("?")[0]); setMessage(""); setError(""); };

  useEffect(() => {
    const pop = () => setPath(window.location.pathname);
    window.addEventListener("popstate", pop);
    return () => window.removeEventListener("popstate", pop);
  }, []);
  useEffect(() => {
    if (!message) return undefined;
    const timer = setTimeout(() => setMessage(""), 2000);
    return () => clearTimeout(timer);
  }, [message]);
  useEffect(() => {
    if (!error || (path === "/login" && error.toLowerCase().includes("verify your email"))) return undefined;
    const timer = setTimeout(() => setError(""), 2000);
    return () => clearTimeout(timer);
  }, [error, path]);
  useEffect(() => {
    if (path === "/auth/verify") {
      const token = new URLSearchParams(location.search).get("token"); history.replaceState({}, "", path);
      if (!token) { setError("Verification link is missing its token."); return; }
      api(`/auth/verify?token=${encodeURIComponent(token)}`).then((result) => { setVerified(true); setMessage(result.message); }).catch((e) => setError(e.message));
    } else if (path === "/auth/reset-password") {
      setResetToken(new URLSearchParams(location.search).get("token") || ""); history.replaceState({}, "", path);
    } else if (path === "/oauth/callback" || path === "/auth/callback") {
      // React StrictMode replays effects in development. Consume one-time OAuth
      // callbacks once so the second pass cannot read the already-cleared query.
      if (oauthCallbackHandled.current) return;
      oauthCallbackHandled.current = true;
      const params = new URLSearchParams(location.search); const code = params.get("code"); const oauthError = params.get("error"); history.replaceState({}, "", path);
      if (oauthError) { setError(`${oauthError} sign-in could not be completed. Please try again.`); return; }
      if (!code) { setError("Sign-in code is missing. Please try again."); return; }
      setBusy(true);
      api("/auth/exchange", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code }) }).then((result) => { saveAccessToken(result.access_token); location.assign("/"); }).catch((e) => setError(e.message)).finally(() => setBusy(false));
    }
  }, [path]);

  async function submit(event) {
    event.preventDefault(); setBusy(true); setError(""); setMessage("");
    try {
      if (path === "/signup") {
        await api("/auth/signup", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password }) });
        sessionStorage.setItem("automl_signup_email", email); navigate("/auth/check-email"); setMessage("Your six-digit verification code is on its way.");
      } else if (path === "/auth/forgot-password") {
        const result = await api("/auth/forgot-password", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email }) }); setMessage(result.message);
      } else if (path === "/auth/reset-password") {
        const result = await api("/auth/reset-password", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ token: resetToken, new_password: newPassword }) }); setMessage(result.message); setNewPassword("");
      } else {
        const result = await api("/auth/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password }) });
        saveAccessToken(result.access_token); location.assign("/");
      }
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  async function resend() {
    setBusy(true); setError("");
    try {
      const result = await api("/auth/resend-verification", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email }) });
      sessionStorage.setItem("automl_signup_email", email);
      if (path !== "/auth/check-email") navigate("/auth/check-email");
      setMessage(result.message);
    }
    catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  async function verifyOtp(event) {
    event.preventDefault(); setBusy(true); setError(""); setMessage("");
    try {
      const result = await api("/auth/verify-otp", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, otp: verificationCode }) });
      setMessage(result.message); setVerified(true); setVerificationCode("");
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  }
  const signup = path === "/signup", checkEmail = path === "/auth/check-email", verify = path === "/auth/verify", callback = path === "/oauth/callback" || path === "/auth/callback", forgot = path === "/auth/forgot-password", reset = path === "/auth/reset-password";
  const title = signup ? "Create your account" : checkEmail ? "Verify your email" : verify ? "Email verification" : callback ? "Signing you in" : forgot ? "Reset your password" : reset ? "Choose a new password" : "Welcome back";
  const needsVerification = path === "/login" && error.toLowerCase().includes("verify your email");
  return <main className="auth-shell"><div className="auth-decor decor-dots dots-top" /><div className="auth-decor decor-dots dots-bottom" /><div className="auth-orbit orbit-top" /><div className="auth-orbit orbit-bottom" />
    <div className="auth-brand"><span className="brand-mark"><Icon name="sparkle" size={40} /></span><div><b>AutoML Studio</b><small>Build <i aria-hidden="true">&bull;</i> Train <i aria-hidden="true">&bull;</i> Deploy</small></div></div>
    <section className="auth-card"><header className="auth-heading"><span className="auth-accent" /><h1>{title === "Welcome back" ? "Welcome back!" : title}</h1><p>{checkEmail ? `Enter the six-digit code sent to ${email || "your email address"}. It expires in 10 minutes.` : "Your workspace and model runs, ready when you are."}</p></header>
    {error && (needsVerification ? <div className="verification-alert"><Icon name="mail" size={30} /><div><b>Please verify your email before logging in.</b><span>You can request a new verification code.</span></div></div> : <Notice type="error" message={error} />)}{message && <Notice type="success" message={message} />}
    {needsVerification && <button className="btn secondary auth-submit verification-resend" disabled={busy || !email} onClick={resend}>{busy ? "Sending code..." : "Resend verification code"}</button>}
    {checkEmail ? <><form onSubmit={verifyOtp} className="auth-form"><label className="auth-field"><span>Email address</span><div className="auth-input-wrap"><Icon name="mail" size={22} /><input type="email" value={email} autoComplete="email" required onChange={(e) => setEmail(e.target.value)} /></div></label><label className="auth-field"><span>6-digit verification code</span><input className="otp-input" type="text" inputMode="numeric" autoComplete="one-time-code" pattern="[0-9]{6}" maxLength="6" minLength="6" placeholder="000000" value={verificationCode} required onChange={(e) => setVerificationCode(e.target.value.replace(/\D/g, "").slice(0, 6))} /></label><button className="btn primary auth-submit" disabled={busy || verified}>{busy ? "Verifying..." : verified ? "Email verified" : "Verify email"}</button></form><button className="btn secondary auth-submit" disabled={busy || verified} onClick={resend}>{busy ? "Sending..." : "Send a new code"}</button><button className="auth-link" onClick={() => navigate("/login")}>Back to sign in</button></>
      : verify ? <button className="btn primary auth-submit" disabled={!verified} onClick={() => navigate("/login")}>Continue to sign in</button>
      : callback ? <><div className="auth-message">{busy ? "Completing secure sign-in..." : "Return to sign in and retry if needed."}</div>{!busy && <button className="auth-link" onClick={() => navigate("/login")}>Back to sign in</button>}</>
      : <form onSubmit={submit} className="auth-form">
        {(signup || forgot || (!reset && !checkEmail && !verify && !callback)) && <label className="auth-field"><span>Email address</span><div className="auth-input-wrap"><Icon name="mail" size={22} /><input type="email" value={email} autoComplete="email" required onChange={(e) => setEmail(e.target.value)} /></div></label>}
        {!forgot && !reset && !checkEmail && !verify && !callback && <label className="auth-field"><span>Password</span><div className="auth-input-wrap"><Icon name="lock" size={22} /><input type={showPassword ? "text" : "password"} value={password} autoComplete={signup ? "new-password" : "current-password"} minLength={signup ? 8 : 1} required onChange={(e) => setPassword(e.target.value)} /><button className="password-toggle" type="button" onClick={() => setShowPassword((shown) => !shown)} aria-label={showPassword ? "Hide password" : "Show password"}><Icon name="eye" size={22} /></button></div></label>}
        {reset && <label className="auth-field"><span>New password</span><div className="auth-input-wrap"><Icon name="lock" size={22} /><input type={showPassword ? "text" : "password"} value={newPassword} autoComplete="new-password" minLength="8" required onChange={(e) => setNewPassword(e.target.value)} /><button className="password-toggle" type="button" onClick={() => setShowPassword((shown) => !shown)} aria-label={showPassword ? "Hide password" : "Show password"}><Icon name="eye" size={22} /></button></div></label>}
        <button className="btn primary auth-submit" disabled={busy}>{busy ? "Please wait..." : signup ? "Create account" : forgot ? "Send reset link" : reset ? "Update password" : <>Sign in <Icon name="arrowRight" size={22} /></>}</button>
      </form>}
    {!forgot && !reset && !checkEmail && !verify && !callback && <><div className="auth-divider"><span>or continue with</span></div><div className="oauth-buttons"><a className="btn secondary" href={`${AUTH_API_URL}/auth/github`}><ProviderIcon provider="github" />Continue with GitHub</a><a className="btn secondary" href={`${AUTH_API_URL}/auth/google`}><ProviderIcon provider="google" />Continue with Google</a></div></>}
    <div className="auth-footer">{signup ? <>Already registered? <button onClick={() => navigate("/login")}>Sign in</button></> : !checkEmail && !verify && !callback && <>{!reset && !forgot && <button onClick={() => navigate("/auth/forgot-password")}>Forgot password?</button>}<span>New to AutoML Studio? <button onClick={() => navigate("/signup")}>Create account</button></span></>}</div>
    </section></main>;
}

export default function App() {
  const [state, setState] = useState("checking");
  const [authPath, setAuthPath] = useState(location.pathname);
  const [account, setAccount] = useState(null);
  useEffect(() => {
    const onPop = () => setAuthPath(location.pathname); window.addEventListener("popstate", onPop);
    const token = getAccessToken();
    if (!token) setState("signed-out");
    else api("/auth/me").then((user) => { setAccount(user); setState("signed-in"); }).catch(() => { clearAccessToken(); setState("signed-out"); });
    return () => window.removeEventListener("popstate", onPop);
  }, []);
  async function signOut() {
    try { await api("/auth/logout", { method: "POST" }); } catch {}
    clearAccessToken(); sessionStorage.removeItem(SESSION_KEY); location.assign("/login");
  }
  if (state === "checking") return <main className="auth-shell"><section className="auth-card"><h1>Loading your workspace...</h1></section></main>;
  if (state === "signed-in") return <Workspace onLogout={signOut} initialAccount={account} />;
  if (authPath === "/") history.replaceState({}, "", "/login");
  return <AuthScreen key={authPath} />;
}
