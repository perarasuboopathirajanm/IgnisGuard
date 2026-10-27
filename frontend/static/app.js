/*
 * IgnisGuard - Fire & PPE safety detection
 * Copyright (c) 2026 Perarasu Boopathirajan. All rights reserved.
 * Author: Perarasu Boopathirajan. See LICENSE.
 */
/* IgnisGuard front-end */
const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const COLORS = {fire:"#ff4500",smoke:"#a0a0a0",person:"#00b4ff",helmet:"#3cc850",no_helmet:"#e62828",
                fire_jacket:"#c8c83c",no_fire_jacket:"#dc28b4"};
let CLASSES = Object.keys(COLORS), ALERTS = {};

function toast(msg, err=false){
  const t=document.createElement("div");t.className="toast"+(err?" err":"");t.textContent=msg;
  document.body.appendChild(t);setTimeout(()=>t.remove(),err?6000:3000);
}
/* backend location: settings (saved in this browser) > config.js > same origin */
const store = { get(k){ try{return localStorage.getItem(k);}catch{return null;} },
                set(k,v){ try{ v ? localStorage.setItem(k,v) : localStorage.removeItem(k); }catch{} } };
const API = (store.get("ignis_api") || window.IGNIS_API || "").replace(/\/+$/,"");
const KEY = store.get("ignis_key") || window.IGNIS_KEY || "";
const u = path => API + path + (KEY ? (path.includes("?")?"&":"?") + "key=" + encodeURIComponent(KEY) : "");
async function api(url, opts={}){
  const headers = {...(opts.headers||{})}; if(KEY) headers["X-API-Key"] = KEY;
  const r = await fetch(API + url, {...opts, headers});
  let j; try{ j = await r.json(); }catch{ j = {}; }
  if(!r.ok){
    const d = j.detail;
    throw new Error(Array.isArray(d) ? d.map(x=>x.msg).join("; ") : (d || r.statusText || `HTTP ${r.status}`));
  }
  return j;
}
const jpost = (url, body) => api(url,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
// Escape text before putting it into innerHTML: model class names, file names and
// imported dataset labels come from uploads and must never be able to inject HTML/JS
// (which could steal the API key saved in this browser).
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const pretty = s => esc(String(s ?? "").replace(/_/g," "));
const safeColor = c => /^#[0-9a-f]{3,8}$|^var\(--[a-z0-9-]+\)$/i.test(c||"") ? c : "#666";
function dropzone(zone, input, onFiles){
  zone.onclick = () => input.click();
  input.onchange = () => { if(input.files.length) onFiles([...input.files]); input.value=""; };
  zone.ondragover = e => {e.preventDefault(); zone.classList.add("over");};
  zone.ondragleave = () => zone.classList.remove("over");
  zone.ondrop = e => {e.preventDefault(); zone.classList.remove("over"); onFiles([...e.dataTransfer.files]);};
}

/* ---------- tabs & header ---------- */
$$("nav button").forEach(b => b.onclick = () => {
  $$("nav button").forEach(x=>x.classList.toggle("active",x===b));
  $$(".tab").forEach(t=>t.classList.toggle("active", t.id==="tab-"+b.dataset.tab));
  if(b.dataset.tab==="training"){ loadDataset(); loadModels(); }
});
async function refreshInfo(){
  try{
    const j = await api("/api/info");
    CLASSES = j.classes; ALERTS = j.alert_classes;
    const d = j.detector;
    $("#modelDot").className = "dot " + (d.mode || "none");
    $("#modelName").textContent = d.model ? `Model: ${d.model}` : (d.error || "No model");
    $("#modelPill").title = d.error || d.model || "";
    $("#offline").style.display = "none";
    return true;
  }catch(e){
    $("#modelDot").className = "dot none";
    $("#modelName").textContent = e.message.includes("key") ? "Wrong API key" : "Backend offline";
    $("#offline").style.display = "block";
    $("#offlineMsg").textContent = e.message.includes("key")
      ? "The backend rejected the API key. Open ⚙ Settings and enter the correct key."
      : `Can't reach the backend at ${API || location.origin}. A free Hugging Face Space falls asleep after a while, and waking it takes about 1–2 minutes. Retrying automatically…`;
    setTimeout(refreshInfo, 8000);
    return false;
  }
}

/* =================== ANALYSIS =================== */
const conf = $("#conf");
conf.oninput = () => $("#confVal").textContent = (+conf.value).toFixed(2);
function analysisForm(blob, name, withImage=true){
  const f = new FormData();
  f.append("file", blob, name);
  f.append("conf", conf.value);
  f.append("fire", $("#chkFire").checked);
  f.append("helmet", $("#chkHelmet").checked);
  f.append("jacket", $("#chkJacket").checked);
  f.append("return_image", withImage);
  return f;
}
function renderAlerts(res){
  const box = $("#alerts"); box.innerHTML = "";
  const entries = Object.entries(res.alerts);
  if(!entries.length){ box.innerHTML = `<span class="badge ok">✔ No hazards or violations detected</span>`; }
  const icon = {"FIRE":"🔥","SMOKE":"💨","NO HELMET":"⛑️","NO FIRE JACKET":"🦺"};
  for(const [k,v] of entries) box.innerHTML += `<span class="badge bad pulse">${icon[k]||"⚠"} ${esc(k)} × ${esc(v)}</span>`;
  box.innerHTML += `<span class="badge info">👷 ${esc(res.people)} people</span><span class="badge info">⏱ ${esc(res.ms)} ms</span>`;
}
function renderTable(res){
  const tb = $("#detTable");
  if(!res.detections.length){ tb.innerHTML = `<tr><td colspan="4" class="muted">Nothing detected</td></tr>`; return; }
  tb.innerHTML = res.detections.map(d => `<tr>
    <td><span class="chip" style="background:${safeColor(COLORS[d.label])}">${pretty(d.label)}</span></td>
    <td>${(+d.conf*100).toFixed(0)}%</td><td class="muted">${d.box.map(v=>Math.round(+v)).join(", ")}</td>
    <td class="muted">${d.derived ? "rule: person without item" : "model"}</td></tr>`).join("");
}
function showResult(res){
  stopLive();
  $("#placeholder").style.display="none";
  const img = $("#resultImg"); img.src = res.image; img.style.display="block";
  renderAlerts(res); renderTable(res);
}
const anResults = [];
async function analyzeFiles(files){
  files = files.filter(f=>f.type.startsWith("image/"));
  if(!files.length) return;
  $("#alerts").innerHTML = `<span class="muted">Analysing ${files.length} image(s)…</span>`;
  anResults.length = 0; $("#anGallery").innerHTML = "";
  for(const f of files){
    try{
      const res = await api("/api/analyze",{method:"POST",body:analysisForm(f,f.name)});
      res.name = f.name; anResults.push(res);
      const i = anResults.length-1, bad = Object.keys(res.alerts).length;
      const g = document.createElement("div"); g.className="g";
      g.innerHTML = `<img alt=""><span class="tag ${bad?'bad':'ok'}">${bad?esc(Object.keys(res.alerts).join(", ")):"SAFE"}</span>`;
      g.querySelector("img").src = res.image;
      g.onclick = () => { $$("#anGallery .g").forEach(x=>x.classList.remove("sel")); g.classList.add("sel"); showResult(anResults[i]); };
      $("#anGallery").appendChild(g);
      if(i===0){ g.classList.add("sel"); showResult(res); }
    }catch(e){ toast(`${f.name}: ${e.message}`, true); $("#alerts").innerHTML=""; }
  }
  if(files.length===1) $("#anGallery").innerHTML="";
}
dropzone($("#anDrop"), $("#anFile"), analyzeFiles);

$$("#srcSeg button").forEach(b => b.onclick = () => {
  $$("#srcSeg button").forEach(x=>x.classList.toggle("active",x===b));
  ["image","video","webcam"].forEach(s => $("#src"+s[0].toUpperCase()+s.slice(1)).style.display = s===b.dataset.src?"block":"none");
});

/* live (video / webcam): grab frames, send without image, draw boxes client-side */
const video = $("#video"), lc = $("#liveCanvas"), lctx = lc.getContext("2d");
let live = false, stream = null, lastDets = [], busy = false, frames = 0, fpsT = performance.now();
const grab = document.createElement("canvas");
function startLive(){
  live = true; lastDets = [];
  $("#placeholder").style.display="none"; $("#resultImg").style.display="none"; $("#anGallery").innerHTML="";
  $("#liveBox").style.display="block"; $("#liveCtl").style.display="flex"; $("#playBtn").textContent="Pause";
  requestAnimationFrame(drawLoop); inferLoop();
}
function stopLive(){
  live = false;
  if(stream){ stream.getTracks().forEach(t=>t.stop()); stream=null; $("#camBtn").textContent="Start webcam"; }
  video.pause(); $("#liveBox").style.display="none"; $("#liveCtl").style.display="none";
}
function drawLoop(){
  if(!live) return;
  if(video.videoWidth){
    lc.width = video.videoWidth; lc.height = video.videoHeight;
    lctx.drawImage(video,0,0);
    const lw = Math.max(2, lc.width/320);
    lctx.font = `bold ${Math.max(12, lc.width/55)}px sans-serif`;
    for(const d of lastDets){
      const [x1,y1,x2,y2] = d.box, c = COLORS[d.label]||"#fff";
      lctx.strokeStyle=c; lctx.lineWidth=lw; lctx.strokeRect(x1,y1,x2-x1,y2-y1);
      const t = `${pretty(d.label).toUpperCase()} ${d.conf.toFixed(2)}`, tw = lctx.measureText(t).width, th = Math.max(12, lc.width/55)+6;
      lctx.fillStyle=c; lctx.fillRect(x1, Math.max(0,y1-th), tw+8, th);
      lctx.fillStyle="#fff"; lctx.fillText(t, x1+4, Math.max(th-5, y1-5));
    }
  }
  requestAnimationFrame(drawLoop);
}
async function inferLoop(){
  while(live){
    if(video.paused || video.ended || !video.videoWidth || busy){ await new Promise(r=>setTimeout(r,80)); continue; }
    busy = true;
    const scale = Math.min(1, 960/video.videoWidth);
    grab.width = video.videoWidth*scale; grab.height = video.videoHeight*scale;
    grab.getContext("2d").drawImage(video,0,0,grab.width,grab.height);
    const blob = await new Promise(r=>grab.toBlob(r,"image/jpeg",0.8));
    try{
      const res = await api("/api/analyze",{method:"POST",body:analysisForm(blob,"frame.jpg",false)});
      res.detections.forEach(d => d.box = d.box.map(v=>v/scale));
      lastDets = res.detections; renderAlerts(res); renderTable(res);
      frames++; const now = performance.now();
      if(now-fpsT>1000){ $("#fps").textContent = `${(frames*1000/(now-fpsT)).toFixed(1)} analysed frames/s`; frames=0; fpsT=now; }
    }catch(e){ toast(e.message,true); stopLive(); }
    busy = false;
  }
}
dropzone($("#vidDrop"), $("#vidFile"), files => {
  const f = files.find(f=>f.type.startsWith("video/")); if(!f) return;
  stopLive(); video.srcObject = null; video.src = URL.createObjectURL(f); video.loop = true;
  video.play().then(startLive);
});
$("#camBtn").onclick = async () => {
  if(stream){ stopLive(); return; }
  try{
    stream = await navigator.mediaDevices.getUserMedia({video:{width:1280,height:720}});
    video.src=""; video.srcObject = stream; await video.play();
    $("#camBtn").textContent="Stop webcam"; startLive();
  }catch(e){ toast("Webcam unavailable: "+e.message, true); }
};
$("#playBtn").onclick = () => { if(video.paused){video.play();$("#playBtn").textContent="Pause";} else {video.pause();$("#playBtn").textContent="Play";} };
$("#stopLive").onclick = () => { stopLive(); $("#placeholder").style.display="block"; };

/* =================== TRAINING =================== */
$$(".step").forEach(s => s.onclick = () => showPane(s.dataset.pane));
function showPane(p){
  $$(".step").forEach(x=>x.classList.toggle("active",x.dataset.pane===p));
  $$(".pane").forEach(x=>x.classList.toggle("active",x.id==="pane-"+p));
  if(p==="label"){ renderThumbs(); if(!cur && items.length) openItem(filtered()[0]?.id || items[0].id); else fitCanvas(); }
  if(p==="train"){ loadModels(); if(lastTrain) renderTrain(lastTrain); }
}

let items = [], stats = null, cur = null, filter = "all";
async function loadDataset(){
  const j = await api("/api/dataset");
  items = j.items; stats = j.stats;
  renderStats(); renderThumbs();
}
function renderStats(){
  const s = stats;
  $("#dsStat").innerHTML = `<div><b>${s.total}</b><span class="muted small">images</span></div>
    <div><b style="color:var(--ok)">${s.labeled}</b><span class="muted small">labelled</span></div>
    <div><b>${s.unlabeled}</b><span class="muted small">still to label</span></div>
    <div><b style="color:var(--info)">${s.background}</b><span class="muted small">no-object images</span></div>`;
  const max = Math.max(1, ...Object.values(s.per_class));
  $("#dsBars").innerHTML = CLASSES.map(c => { const n = s.per_class[c]||0;
    return `<div class="bar"><span class="name">${pretty(c)}</span><div class="track"><div class="fill" style="width:${n/max*100}%;background:${COLORS[c]}"></div></div><b style="width:40px;text-align:right">${n}</b>${n<20?'<span class="muted" title="Add more examples">⚠</span>':'<span>&nbsp;&nbsp;</span>'}</div>`;}).join("");
  $("#stepUp").textContent = `${s.total} images`;
  $("#stepLab").textContent = `${s.labeled + s.background} done · ${s.unlabeled} to do`;
}
const filtered = () => items.filter(i => filter==="all" || (filter==="unlabeled" ? i.status==="unlabeled" : i.status!=="unlabeled"));
$$("#thumbFilter button").forEach(b => b.onclick = () => {
  filter = b.dataset.f; $$("#thumbFilter button").forEach(x=>x.classList.toggle("active",x===b)); renderThumbs();
});
function renderThumbs(){
  const tag = {unlabeled:["unl","TODO"],labeled:["lab","✔"],background:["bg","NONE"]};
  $("#thumbs").innerHTML = filtered().map(i => `<div class="g ${cur&&cur.id===i.id?'sel':''}" data-id="${i.id}">
    <img loading="lazy" src="${u(`/api/dataset/image/${i.id}`)}"><span class="tag ${tag[i.status][0]}">${tag[i.status][1]}${i.boxes.length?' '+i.boxes.length:''}</span></div>`).join("")
    || `<p class="muted small" style="grid-column:1/-1">No images here.</p>`;
  $$("#thumbs .g").forEach(g => g.onclick = () => openItem(g.dataset.id));
}
async function uploadTraining(files){
  files = files.filter(f=>f.type.startsWith("image/")); if(!files.length) return;
  toast(`Uploading ${files.length} image(s)…`);
  for(let i=0;i<files.length;i+=20){
    const fd = new FormData(); files.slice(i,i+20).forEach(f=>fd.append("files",f));
    const j = await api("/api/dataset/upload",{method:"POST",body:fd});
    j.errors.forEach(e=>toast(e,true));
  }
  await loadDataset(); toast(`Uploaded ${files.length} image(s). Go to step 2 to label them.`);
}
dropzone($("#trDrop"), $("#trFile"), uploadTraining);
dropzone($("#zipDrop"), $("#zipFile"), async files => {
  const f = files.find(f=>f.name.endsWith(".zip")); if(!f) return toast("Please choose a .zip",true);
  $("#importResult").textContent = "Importing… (large datasets can take a minute)";
  const fd = new FormData(); fd.append("file", f);
  try{
    const j = await api("/api/dataset/import",{method:"POST",body:fd});
    const map = Object.entries(j.class_mapping).map(([a,b])=>`${esc(a)} → ${esc(b)}`).join(", ") || "none matched!";
    $("#importResult").innerHTML = `✔ Imported <b>${esc(j.added)}</b> images. Class mapping: ${map}`;
    loadDataset();
  }catch(e){ $("#importResult").textContent = ""; toast(e.message,true); }
});

/* ---------- annotator ---------- */
const cv = $("#annCanvas"), ctx = cv.getContext("2d");
let img = new Image(), boxes = [], sel = -1, curCls = "fire", scale = 1, drag = null, dirty = false;
$("#clsList").innerHTML = CLASSES.map((c,i)=>`<button data-c="${c}"><span class="sw" style="background:${COLORS[c]}"></span>${pretty(c)}<kbd>${i+1}</kbd></button>`).join("");
function setCls(c){
  curCls = c; $$("#clsList button").forEach(b=>b.classList.toggle("active",b.dataset.c===c));
  if(sel>=0 && boxes[sel].cls !== c){ boxes[sel].cls = c; dirty = true; redraw(); }
}
$$("#clsList button").forEach(b => b.onclick = () => setCls(b.dataset.c));
setCls("fire");

async function openItem(id){
  if(!id) return;
  if(dirty && cur) await save(false);
  cur = items.find(i=>i.id===id); if(!cur) return;
  boxes = cur.boxes.map(b=>({...b})); sel = -1; dirty = false;
  img = new Image();
  img.onload = () => { $("#annPh").style.display="none"; cv.style.display="block"; fitCanvas(); };
  img.crossOrigin = "anonymous";
  img.src = u(`/api/dataset/image/${id}?v=${Date.now()}`);
  const idx = filtered().findIndex(i=>i.id===id);
  $("#annInfo").textContent = `${cur.name}  ·  ${cur.w}×${cur.h}  ·  ${idx+1}/${filtered().length}  ·  ${cur.status}`;
  renderThumbs();
  document.querySelector(`#thumbs .g[data-id="${id}"]`)?.scrollIntoView({block:"nearest"});
}
function fitCanvas(){
  if(!img.naturalWidth) return;
  const wrap = $("#annWrap"), maxW = wrap.clientWidth - 4, maxH = window.innerHeight * 0.68;
  scale = Math.min(maxW/img.naturalWidth, maxH/img.naturalHeight, 1.5);
  cv.width = Math.round(img.naturalWidth*scale); cv.height = Math.round(img.naturalHeight*scale);
  redraw();
}
window.addEventListener("resize", fitCanvas);
function redraw(){
  ctx.clearRect(0,0,cv.width,cv.height); ctx.drawImage(img,0,0,cv.width,cv.height);
  ctx.font = "bold 12px sans-serif";
  boxes.forEach((b,i)=>{
    const x=b.x1*scale,y=b.y1*scale,w=(b.x2-b.x1)*scale,h=(b.y2-b.y1)*scale,c=COLORS[b.cls];
    ctx.fillStyle = c+"22"; ctx.fillRect(x,y,w,h);
    ctx.strokeStyle=c; ctx.lineWidth = i===sel?3:2; ctx.setLineDash(i===sel?[6,3]:[]); ctx.strokeRect(x,y,w,h); ctx.setLineDash([]);
    const t = pretty(b.cls), tw = ctx.measureText(t).width;
    ctx.fillStyle=c; ctx.fillRect(x, Math.max(0,y-16), tw+8, 16); ctx.fillStyle="#fff"; ctx.fillText(t, x+4, Math.max(12,y-4));
    if(i===sel){ ctx.fillStyle="#fff"; handles(b).forEach(([hx,hy])=>ctx.fillRect(hx*scale-4,hy*scale-4,8,8)); }
  });
  if(drag && drag.type==="new"){
    const {x0,y0,x1,y1} = drag; ctx.strokeStyle=COLORS[curCls]; ctx.lineWidth=2; ctx.setLineDash([5,4]);
    ctx.strokeRect(x0*scale,y0*scale,(x1-x0)*scale,(y1-y0)*scale); ctx.setLineDash([]);
    // crosshair guide
  }
  $("#boxList").innerHTML = boxes.length ? boxes.map((b,i)=>`<div class="${i===sel?'sel':''}" data-i="${i}"><span><span class="chip" style="background:${COLORS[b.cls]}">${pretty(b.cls)}</span></span><span class="muted">${Math.round(b.x2-b.x1)}×${Math.round(b.y2-b.y1)} <a data-del="${i}" style="cursor:pointer;color:var(--bad)">✕</a></span></div>`).join("") : `<span class="muted">None. Drag on the image to add one.</span>`;
  $$("#boxList div").forEach(d => d.onclick = e => {
    const i = +d.dataset.i;
    if(e.target.dataset.del!==undefined){ boxes.splice(i,1); sel=-1; dirty=true; } else { sel=i; }
    redraw();
  });
}
const handles = b => [[b.x1,b.y1],[b.x2,b.y1],[b.x1,b.y2],[b.x2,b.y2]];
function pos(e){ const r = cv.getBoundingClientRect(); return [(e.clientX-r.left)*(img.naturalWidth/r.width), (e.clientY-r.top)*(img.naturalHeight/r.height)]; }
cv.onmousedown = e => {
  const [x,y] = pos(e), tol = 8/scale;
  if(sel>=0){
    const hi = handles(boxes[sel]).findIndex(([hx,hy])=>Math.abs(hx-x)<tol && Math.abs(hy-y)<tol);
    if(hi>=0){ drag = {type:"resize", hi}; return; }
  }
  // topmost (smallest) box under cursor
  let hit = -1, best = Infinity;
  boxes.forEach((b,i)=>{ if(x>=b.x1&&x<=b.x2&&y>=b.y1&&y<=b.y2){ const a=(b.x2-b.x1)*(b.y2-b.y1); if(a<best){best=a;hit=i;} } });
  if(hit>=0 && e.shiftKey){ sel = hit; drag = {type:"move", sx:x, sy:y, orig:{...boxes[hit]}}; return; }
  // otherwise: drag draws a new box (even inside another box); a plain click selects the box under the cursor
  drag = {type:"new", x0:x, y0:y, x1:x, y1:y, hit};
};
window.addEventListener("mousemove", e => {
  if(!drag || !cur) return;
  let [x,y] = pos(e);
  x = Math.max(0, Math.min(img.naturalWidth, x)); y = Math.max(0, Math.min(img.naturalHeight, y));
  if(drag.type==="new"){ drag.x1=x; drag.y1=y; }
  else if(drag.type==="move"){
    const o = drag.orig, b = boxes[sel], w=o.x2-o.x1, h=o.y2-o.y1;
    let nx = Math.max(0, Math.min(img.naturalWidth-w, o.x1 + x - drag.sx));
    let ny = Math.max(0, Math.min(img.naturalHeight-h, o.y1 + y - drag.sy));
    Object.assign(b, {x1:nx, y1:ny, x2:nx+w, y2:ny+h}); dirty = true;
  } else if(drag.type==="resize"){
    const b = boxes[sel], hi = drag.hi;
    if(hi===0||hi===2) b.x1=x; else b.x2=x;
    if(hi===0||hi===1) b.y1=y; else b.y2=y;
    dirty = true;
  }
  redraw();
});
window.addEventListener("mouseup", () => {
  if(!drag) return;
  if(drag.type==="new"){
    const {x0,y0,x1,y1} = drag;
    if(Math.abs(x1-x0)*scale>5 && Math.abs(y1-y0)*scale>5){
      boxes.push({cls:curCls, x1:Math.min(x0,x1), y1:Math.min(y0,y1), x2:Math.max(x0,x1), y2:Math.max(y0,y1)});
      sel = -1; dirty = true;   // stay in drawing mode; click a box to select it
    } else if(drag.hit>=0){ sel = drag.hit; const c = boxes[sel].cls; drag = null; setCls(c); }
    else sel = -1;
  } else if(drag.type==="resize"){
    const b = boxes[sel];
    [b.x1,b.x2] = [Math.min(b.x1,b.x2),Math.max(b.x1,b.x2)]; [b.y1,b.y2] = [Math.min(b.y1,b.y2),Math.max(b.y1,b.y2)];
  }
  drag = null; redraw();
});

async function save(advance=true, background=false){
  if(!cur) return;
  const j = await jpost(`/api/dataset/${cur.id}/boxes`, {boxes, background});
  Object.assign(cur, j); dirty = false;
  const it = items.find(i=>i.id===cur.id); Object.assign(it, j);
  stats = (await api("/api/dataset")).stats; renderStats(); renderThumbs();
  if(advance){ const list = filtered(), idx = list.findIndex(i=>i.id===cur.id);
    const next = list[idx+1] || (filter==="unlabeled" ? list[0] : null);
    if(next && next.id!==cur.id) openItem(next.id); else toast("Saved ✔"); }
}
function step(d){ const list = filtered(); if(!list.length) return; const idx = list.findIndex(i=>i.id===cur?.id);
  const n = list[Math.max(0,Math.min(list.length-1, idx+d))]; if(n) openItem(n.id); }
$("#saveBtn").onclick = () => save(true);
$("#bgBtn").onclick = () => { boxes = []; sel=-1; redraw(); save(true, true); };
$("#clearBtn").onclick = () => { boxes = []; sel=-1; dirty=true; redraw(); };
$("#prevImg").onclick = () => step(-1);
$("#nextImg").onclick = () => step(1);
$("#delImg").onclick = async () => {
  if(!cur) return;
  const list = filtered(), idx = list.findIndex(i=>i.id===cur.id), next = list[idx+1] || list[idx-1];
  await api(`/api/dataset/${cur.id}`,{method:"DELETE"}); dirty=false; cur=null;
  await loadDataset();
  if(next) openItem(next.id); else { cv.style.display="none"; $("#annPh").style.display="block"; $("#annInfo").textContent="No image selected"; }
};
$("#autoBtn").onclick = async () => {
  if(!cur) return;
  try{
    const j = await jpost(`/api/dataset/${cur.id}/autolabel`, {conf: 0.3});
    boxes = boxes.concat(j.boxes); dirty = true; redraw();
    toast(j.boxes.length ? `Added ${j.boxes.length} suggested box(es). Check and fix them before saving.` : "The model found nothing on this image.");
  }catch(e){ toast(e.message,true); }
};
document.addEventListener("keydown", e => {
  if(!$("#pane-label").classList.contains("active") || !$("#tab-training").classList.contains("active")) return;
  if(["INPUT","SELECT","TEXTAREA"].includes(document.activeElement.tagName)) return;
  const k = e.key.toLowerCase();
  if(k>="1" && k<=String(CLASSES.length)) setCls(CLASSES[+k-1]);
  else if((k==="delete"||k==="backspace") && sel>=0){ boxes.splice(sel,1); sel=-1; dirty=true; redraw(); e.preventDefault(); }
  else if(k==="s"){ save(true); e.preventDefault(); }
  else if(k==="a"||k==="arrowleft") step(-1);
  else if(k==="d"||k==="arrowright") step(1);
  else if(k==="escape"){ sel=-1; redraw(); }
});

/* ---------- training job ---------- */
$("#trainBtn").onclick = async () => {
  try{
    await jpost("/api/train/start", {epochs:+$("#tEpochs").value, imgsz:+$("#tImg").value,
      base:$("#tBase").value, batch:+$("#tBatch").value, device:$("#tDev").value});
    toast("Training started"); pollTrain();
  }catch(e){ toast(e.message,true); }
};
$("#stopBtn").onclick = () => jpost("/api/train/stop", {});
let polling = false, lastStatus = null;
async function pollTrain(){
  if(polling) return; polling = true;
  while(true){
    let s; try{ s = await api("/api/train/status"); }catch{ break; }
    renderTrain(s);
    if(!s.running){
      if(lastStatus && lastStatus !== s.status && (s.status==="done"||s.status==="error")){
        toast(s.message, s.status==="error"); refreshInfo(); loadModels();
      }
      lastStatus = s.status; break;
    }
    lastStatus = s.status;
    await new Promise(r=>setTimeout(r,1500));
  }
  polling = false;
}
let lastTrain = null;
function renderTrain(s){
  lastTrain = s;
  const label = {idle:"Idle",starting:"Starting…",training:"Training",done:"Finished ✔",error:"Error"}[s.status]||s.status;
  $("#tStatus").textContent = s.running && s.epochs ? `${label} · epoch ${Math.min(s.epoch+1,s.epochs)}/${s.epochs}` : label;
  $("#tStatus").style.color = s.status==="error"?"var(--bad)":s.status==="done"?"var(--ok)":"";
  const frac = s.epochs ? (s.status==="done" ? 1 : (s.epoch + (s.batches? s.batch/s.batches : 0))/s.epochs) : 0;
  $("#tBar").style.width = (Math.min(1,frac)*100).toFixed(1)+"%";
  $("#tMsg").textContent = s.message || "";
  if(s.running && s.started && frac>0.01){
    const el = Date.now()/1000 - s.started, rem = el/frac - el;
    $("#tEta").textContent = `≈ ${rem>3600? (rem/3600).toFixed(1)+" h" : Math.ceil(rem/60)+" min"} left`;
  } else $("#tEta").textContent = "";
  $("#trainBtn").disabled = s.running; $("#stopBtn").disabled = !s.running;
  $("#stepTr").textContent = s.running ? `Training ${Math.round(frac*100)}%` : "Train and manage models";
  drawChart(s.history||[]);
}
function drawChart(h){
  const c = $("#chart"), g = c.getContext("2d"), dpr = devicePixelRatio||1;
  const W = c.clientWidth, H = 220; c.width = W*dpr; c.height = H*dpr; g.scale(dpr,dpr);
  g.clearRect(0,0,W,H);
  const pad = {l:40,r:40,t:10,b:24}, iw = W-pad.l-pad.r, ih = H-pad.t-pad.b;
  g.strokeStyle="#2a2f3a"; g.fillStyle="#8b93a3"; g.font="11px sans-serif"; g.lineWidth=1;
  for(let i=0;i<=4;i++){ const y = pad.t+ih*i/4; g.beginPath(); g.moveTo(pad.l,y); g.lineTo(W-pad.r,y); g.stroke();
    g.textAlign="left"; g.fillText(((1-i/4)*100).toFixed(0)+"%", W-pad.r+6, y+4); }
  if(!h.length){ g.textAlign="center"; g.fillText("Chart appears after the first epoch", W/2, H/2); return; }
  const n = Math.max(2, h.length), X = i => pad.l + iw*i/(n-1);
  const losses = h.map(e=>e.loss).filter(v=>v!=null), lmax = Math.max(...losses, 1e-6);
  g.textAlign="right"; for(let i=0;i<=4;i++) g.fillText((lmax*(1-i/4)).toFixed(2), pad.l-6, pad.t+ih*i/4+4);
  g.textAlign="center"; g.fillText("epoch "+h[h.length-1].epoch, W/2, H-6);
  const line = (vals, col, max) => { g.strokeStyle=col; g.lineWidth=2; g.beginPath();
    vals.forEach((v,i)=>{ if(v==null) return; const y = pad.t + ih*(1-v/max); i?g.lineTo(X(i),y):g.moveTo(X(i),y); }); g.stroke();
    const last = vals.length-1, v = vals[last]; if(v!=null){ g.fillStyle=col; g.beginPath(); g.arc(X(last), pad.t+ih*(1-v/max), 3.5, 0, 7); g.fill(); } };
  line(h.map(e=>e.loss), "#ff5a1f", lmax);
  line(h.map(e=>e.mAP50), "#3ecf6e", 1);
}

/* ---------- models ---------- */
async function loadModels(){
  const j = await api("/api/models");
  $("#modelTable").innerHTML = j.models.length ? j.models.map(m => `<tr>
    <td>${esc(m.name)} ${m.active?'<span class="chip" style="background:var(--ok);color:#06200f">ACTIVE</span>':''}</td>
    <td class="muted">${esc(m.size_mb)} MB</td><td class="muted">${esc(new Date(m.created*1000).toLocaleString())}</td>
    <td style="text-align:right"><button class="btn sm" data-act="${esc(m.name)}" ${m.active?'disabled':''}>Use</button>
    <a class="btn sm" href="${esc(u(`/api/models/download/${encodeURIComponent(m.name)}`))}" style="text-decoration:none">Download</a></td></tr>`).join("")
    : `<tr><td colspan="4" class="muted">No trained models yet. Label some images and press Start training.</td></tr>`;
  $$("[data-act]").forEach(b => b.onclick = async () => { b.disabled = true; toast("Loading model…");
    try{ await jpost("/api/models/activate",{name:b.dataset.act}); await refreshInfo(); loadModels(); toast("Model activated"); }
    catch(e){ toast(e.message,true); b.disabled=false; } });
}
$("#starterBtn").onclick = async () => { toast("Loading starter model…");
  try{ const d = await jpost("/api/models/activate",{name:"__starter__"}); await refreshInfo(); loadModels();
       if(d.error) toast(d.error,true); }
  catch(e){ toast(e.message,true); } };
$("#upModelBtn").onclick = () => $("#upModel").click();
$("#upModel").onchange = async () => { const f = $("#upModel").files[0]; if(!f) return;
  const fd = new FormData(); fd.append("file", f);
  try{ await api("/api/models/upload",{method:"POST",body:fd}); toast("Model uploaded. Press Use to activate it."); loadModels(); }
  catch(e){ toast(e.message,true); } $("#upModel").value=""; };

/* ---------- settings ---------- */
$("#setBtn").onclick = () => { $("#setApi").value = store.get("ignis_api") || window.IGNIS_API || ""; $("#setKey").value = KEY; $("#settings").showModal(); };
$("#setCancel").onclick = () => $("#settings").close();
$("#setSave").onclick = () => { store.set("ignis_api", $("#setApi").value.trim()); store.set("ignis_key", $("#setKey").value.trim()); location.reload(); };

/* ---------- boot ---------- */
refreshInfo().then(ok=>{ if(ok){ loadDataset(); pollTrain(); } });
