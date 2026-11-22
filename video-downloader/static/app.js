const $ = (id) => document.getElementById(id);

let parsedItems = [];
let envReady = true;
let downloadFolderName = "";

function payload() {
  return {
    url: $("url").value.trim(),
    browser: $("browser").value,
    quality: $("quality").value,
  };
}

function showError(msg) {
  const el = $("error");
  if (!msg) {
    el.classList.add("hidden");
    el.textContent = "";
    return;
  }
  el.textContent = msg;
  el.classList.remove("hidden");
}

function formatDuration(sec) {
  if (!sec) return "";
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m} 分 ${s} 秒`;
}

function formatBytes(bytes) {
  if (bytes == null || Number.isNaN(bytes) || bytes <= 0) return "大小未知";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  const digits = value >= 100 || unit === 0 ? 0 : value >= 10 ? 1 : 2;
  return `${value.toFixed(digits)} ${units[unit]}`;
}

function selectedTotalBytes() {
  const selected = new Set(selectedUrls());
  return parsedItems
    .filter((item) => selected.has(item.url))
    .reduce((sum, item) => sum + (item.filesize_bytes || 0), 0);
}

function setThumbnailImage(img, url) {
  if (!url) {
    img.classList.add("hidden");
    img.removeAttribute("src");
    return;
  }
  img.classList.remove("hidden", "thumb-broken");
  img.referrerPolicy = "no-referrer";
  img.loading = "lazy";
  img.alt = "";
  const proxied = `/api/thumbnail?url=${encodeURIComponent(url)}`;
  img.onerror = () => {
    img.classList.add("thumb-broken");
    img.removeAttribute("src");
  };
  img.src = proxied;
}

function selectedUrls() {
  return [...document.querySelectorAll(".entry-check:checked")].map((el) => el.value);
}

function updateDownloadButton() {
  const n = selectedUrls().length;
  $("btnDownload").disabled = !envReady || n === 0;
  if (n === 0) {
    $("btnDownload").textContent = "下载选中项";
    return;
  }
  const total = selectedTotalBytes();
  const sizeHint = total > 0 ? `，约 ${formatBytes(total)}` : "";
  $("btnDownload").textContent = `下载选中项（${n}${sizeHint}）`;
  updateEntriesSummary();
}

function updateEntriesSummary() {
  if (!parsedItems.length) return;
  const selected = selectedUrls().length;
  const totalAll = parsedItems.reduce((s, i) => s + (i.filesize_bytes || 0), 0);
  const totalSel = selectedTotalBytes();
  const parts = [`已选 ${selected}/${parsedItems.length} 个`];
  if (totalSel > 0) parts.push(`合计约 ${formatBytes(totalSel)}`);
  else if (totalAll > 0) parts.push(`全部约 ${formatBytes(totalAll)}`);
  const hint = $("entriesSummary").dataset.hint;
  if (hint) parts.push(hint);
  $("entriesSummary").textContent = `${$("entriesSummary").dataset.base || ""} ${parts.join(" · ")}`.trim();
}

function renderEntries(data) {
  parsedItems = data.items || [];
  $("entriesCard").classList.remove("hidden");
  const base = data.is_playlist
    ? `合集「${data.title}」共 ${parsedItems.length} 个视频，勾选要下载的条目`
  : `已解析 1 个视频（清晰度：${data.quality || $("quality").value}）`;
  $("entriesSummary").dataset.base = base;
  $("entriesSummary").dataset.hint = data.platform_hint || "";
  $("entriesSummary").textContent = base;

  const list = $("entriesList");
  list.innerHTML = "";
  parsedItems.forEach((item) => {
    const li = document.createElement("li");
    li.className = "entry-item";

    const left = document.createElement("label");
    left.className = "entry-label";

    const cb = document.createElement("input");
    cb.type = "checkbox";
    cb.className = "entry-check";
    cb.value = item.url;
    cb.checked = true;
    cb.addEventListener("change", updateDownloadButton);

    const thumb = document.createElement("img");
    thumb.className = "entry-thumb";
    if (item.thumbnail) setThumbnailImage(thumb, item.thumbnail);

    const body = document.createElement("div");
    body.className = "entry-body";
    const title = document.createElement("strong");
    title.textContent = item.title;
    const meta = document.createElement("span");
    meta.className = "entry-meta";
    const metaParts = [];
    if (item.duration) metaParts.push(formatDuration(item.duration));
    if (item.filesize_bytes) metaParts.push(`约 ${formatBytes(item.filesize_bytes)}`);
    meta.textContent = metaParts.join(" · ");

    body.appendChild(title);
    body.appendChild(meta);
    left.appendChild(cb);
    if (item.thumbnail) left.appendChild(thumb);
    left.appendChild(body);
    li.appendChild(left);
    list.appendChild(li);
  });

  updateDownloadButton();
  updateEntriesSummary();
}

function setAllChecks(checked) {
  document.querySelectorAll(".entry-check").forEach((el) => {
    el.checked = checked;
  });
  updateDownloadButton();
}

function renderRequirements(data) {
  const items = data.items || [];
  const missing = items.filter((i) => i.required && !i.installed);
  envReady = data.ready === true;

  $("btnAnalyze").disabled = !envReady;
  $("btnDownload").disabled = !envReady || selectedUrls().length === 0;

  const banner = $("setupBanner");
  const list = $("setupList");
  list.innerHTML = "";

  items.forEach((item) => {
    const li = document.createElement("li");
    li.className = `setup-item ${item.installed ? "ok" : "missing"}`;
    const title = document.createElement("h3");
    title.textContent = item.installed
      ? `✓ ${item.name} 已安装`
      : `✗ ${item.name} 未安装`;
    li.appendChild(title);
    if (item.installed && item.version) {
      const v = document.createElement("p");
      v.className = "meta";
      v.textContent = `${item.path} · ${item.version}`;
      li.appendChild(v);
    } else if (!item.installed) {
      const cmd = document.createElement("code");
      cmd.textContent = item.install_mac;
      li.appendChild(cmd);
      if (item.install_note) {
        const note = document.createElement("p");
        note.className = "meta";
        note.textContent = item.install_note;
        li.appendChild(note);
      }
    }
    list.appendChild(li);
  });

  if (missing.length > 0) {
    banner.classList.remove("hidden");
    $("setupIntro").textContent = `缺少 ${missing.length} 项必要工具，请在本机终端安装后再使用。`;
  } else {
    banner.classList.add("hidden");
  }

  const hints = [];
  if (data.hints?.browser_login) hints.push(data.hints.browser_login);
  if (data.hints?.homebrew) hints.push(data.hints.homebrew);
  $("setupHint").textContent = hints.join("\n\n");
}

async function checkRequirements() {
  try {
    const res = await fetch("/api/requirements");
    const data = await res.json();
    if (!res.ok) throw new Error("无法检测环境");
    renderRequirements(data);
  } catch {
    envReady = false;
    $("setupBanner").classList.remove("hidden");
    $("setupIntro").textContent = "无法连接本机服务，请先运行 ./run.sh 启动网页。";
    $("btnAnalyze").disabled = true;
    $("btnDownload").disabled = true;
  }
}

async function analyze() {
  showError("");
  if (!envReady) {
    showError("请先按页面上方提示安装缺失依赖，或重新检测环境。");
    return;
  }
  const body = payload();
  if (!body.url) {
    showError("请先输入链接");
    return;
  }
  $("btnAnalyze").disabled = true;
  $("btnAnalyze").textContent = "正在估算大小…";
  $("btnDownload").disabled = true;
  try {
    const res = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: body.url,
        browser: body.browser,
        quality: body.quality,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "解析失败");

    const showSeriesCard = data.is_playlist && data.entry_count > 1;
    if (showSeriesCard) {
      $("infoCard").classList.remove("hidden");
      $("infoTitle").textContent = data.title;
      const parts = [];
      if (data.uploader) parts.push(`UP：${data.uploader}`);
      if (data.platform_label) parts.push(`来源：${data.platform_label}`);
      if (data.entry_count) parts.push(`共 ${data.entry_count} 个视频`);
      if (data.total_filesize_bytes) parts.push(`合计约 ${formatBytes(data.total_filesize_bytes)}`);
      if (data.platform_hint) parts.push(data.platform_hint);
      $("infoMeta").textContent = parts.join(" · ") || data.webpage_url;
      if (data.thumbnail) setThumbnailImage($("thumb"), data.thumbnail);
      else $("thumb").classList.add("hidden");
    } else {
      $("infoCard").classList.add("hidden");
    }

    downloadFolderName = data.folder_name || data.title || "";
    renderEntries(data);
  } catch (e) {
    showError(e.message || String(e));
  } finally {
    $("btnAnalyze").disabled = !envReady;
    $("btnAnalyze").textContent = "获取视频列表";
  }
}

function parsePercent(p) {
  const m = String(p || "").match(/([\d.]+)/);
  return m ? parseFloat(m[1]) : 0;
}

let pollTimer = null;

function stopPoll() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

function renderDownloadLinks(jobId, files) {
  const box = $("dlLinks");
  box.innerHTML = "";
  if (!files?.length) {
    box.classList.add("hidden");
    return;
  }
  files.forEach((_file, idx) => {
    const a = document.createElement("a");
    a.className = "btn secondary";
    a.href = `/api/jobs/${jobId}/file?index=${idx}`;
    const size = _file.size_bytes ? ` · ${formatBytes(_file.size_bytes)}` : "";
    a.textContent = `打开 ${_file.name}${size}`;
    a.download = _file.name;
    box.appendChild(a);
  });
  box.classList.remove("hidden");
}

async function pollJob(jobId) {
  const res = await fetch(`/api/jobs/${jobId}`);
  const job = await res.json();
  if (!res.ok) throw new Error(job.detail || "查询失败");

  const statusEl = $("jobStatus");
  statusEl.textContent =
    {
      pending: "排队中",
      downloading: "下载中",
      merging: "合并音视频中",
      done: "完成",
      error: "失败",
    }[job.status] || job.status;
  statusEl.className = `status ${job.status}`;

  const batch =
    job.total > 1
      ? `第 ${job.current_index || 0}/${job.total} 个`
      : "";
  $("jobProgress").textContent = [batch, job.progress, job.speed, job.eta ? `剩余 ${job.eta}` : ""]
    .filter(Boolean)
    .join(" · ");

  const overall =
    job.total > 1 && job.current_index
      ? Math.round(((job.current_index - 1) / job.total) * 100 + parsePercent(job.progress) / job.total)
      : parsePercent(job.progress);
  $("barFill").style.width = `${Math.min(100, overall)}%`;

  const detail = [];
  if (job.folder_name) detail.push(`文件夹：${job.folder_name}`);
  else if (job.total <= 1) detail.push("保存位置：~/Downloads/video-web");
  if (job.current_title) detail.push(job.current_title);
  if (job.current_total_bytes) detail.push(`当前约 ${formatBytes(job.current_total_bytes)}`);
  if (job.output_name) {
    const last = job.output_files?.at(-1);
    const size = last?.size_bytes ? `（${formatBytes(last.size_bytes)}）` : "";
    detail.push(`最新文件：${job.output_name}${size}`);
  }
  $("jobDetail").textContent = detail.join(" — ");

  if (job.log_tail?.length) {
    $("log").classList.remove("hidden");
    $("log").textContent = job.log_tail.join("\n");
  }

  if (job.status === "done") {
    stopPoll();
    updateDownloadButton();
    renderDownloadLinks(jobId, job.output_files);
    return;
  }

  if (job.status === "error") {
    stopPoll();
    updateDownloadButton();
    showError(job.error || "下载失败");
  }
}

async function download() {
  showError("");
  if (!envReady) {
    showError("请先按页面上方提示安装缺失依赖。");
    return;
  }
  stopPoll();
  const urls = selectedUrls();
  if (!urls.length) {
    showError("请至少勾选一个视频");
    return;
  }

  const body = payload();
  $("btnDownload").disabled = true;
  $("jobCard").classList.remove("hidden");
  $("dlLinks").classList.add("hidden");
  $("barFill").style.width = "0%";
  $("jobStatus").textContent = "提交中";
  $("jobProgress").textContent = "";

  try {
    const res = await fetch("/api/download", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        urls,
        quality: body.quality,
        browser: body.browser,
        folder_name: downloadFolderName,
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "无法创建任务");

    const jobId = data.job_id;
    await pollJob(jobId);
    pollTimer = setInterval(() => pollJob(jobId).catch(() => {}), 1500);
  } catch (e) {
    showError(e.message || String(e));
    updateDownloadButton();
  }
}

$("btnAnalyze").addEventListener("click", analyze);
$("btnDownload").addEventListener("click", download);
$("btnSelectAll").addEventListener("click", () => setAllChecks(true));
$("btnSelectNone").addEventListener("click", () => setAllChecks(false));

checkRequirements();
setInterval(checkRequirements, 15000);