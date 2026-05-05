import json, re, sys, os
from datetime import datetime, timezone, timedelta

SKIP_KAS = {"45678", "123456", "TEST", "ticket link", "-", ""}

# Load suggestions from JSON file (next to this script)
_sugg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "suggestions.json")
try:
    with open(_sugg_path) as _f:
        SUGGESTIONS = json.load(_f)
except Exception:
    SUGGESTIONS = {}

def clean_text(text):
    text = re.sub(r'<([^|>]+)\|([^>]+)>', r'\2', text)
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()

def extract_field(text, field_name):
    stop_fields = ["KA","Ticket Link","Product Area","Issue Summary","Relevant Links","What have you tried so far"]
    stop_pat = "|".join(re.escape(f) for f in stop_fields if f != field_name)
    pat = rf'\*{re.escape(field_name)}\*\s*\n([\s\S]*?)(?=\*(?:{stop_pat})\*|Thread:|Reactions:|Files:|\Z)'
    m = re.search(pat, text)
    return m.group(1).strip() if m else ""

def parse_tried(raw):
    lines = []
    for line in raw.split('\n'):
        line = line.strip().lstrip('•').strip()
        line = clean_text(line)
        if line and line not in ('•', '-', ''):
            lines.append(line)
    return lines

def parse_messages(raw_text):
    pattern = r'=== Message(?:[^=]*)? at ([^=]+?) ===\s*([\s\S]*?)(?====|$)'
    results = []
    for date_str, body in re.findall(pattern, raw_text):
        if 'needs help!' not in body:
            continue
        req_m = re.search(r'<@[^|]+\|([^>]+)> needs help!', body)
        if not req_m:
            continue
        ka = extract_field(body, "KA").strip()
        if not ka or ka in SKIP_KAS:
            continue
        area = clean_text(extract_field(body, "Product Area"))
        if not area or area == '-':
            continue
        summary = clean_text(extract_field(body, "Issue Summary").replace('\n', ' '))[:400]
        tried = parse_tried(extract_field(body, "What have you tried so far"))
        ticket_raw = extract_field(body, "Ticket Link")
        ticket_url = ""
        lm = re.search(r'<([^|>]+)(?:\|[^>]+)?>', ticket_raw)
        if lm: ticket_url = lm.group(1)
        date_m = re.search(r'\d{4}-\d{2}-\d{2}', date_str)
        date_clean = date_m.group(0) if date_m else date_str.strip()[:10]
        reply_m = re.search(r'Thread:\s*(\d+)\s*repl', body)
        ts_m = re.search(r'Message TS:\s*(\d+\.\d+)', body)
        ts = ts_m.group(1) if ts_m else ""
        suggestions = SUGGESTIONS.get(ts, [])
        results.append({
            "date": date_clean, "requester": req_m.group(1), "ka": ka,
            "area": area, "summary": summary, "tried": tried,
            "ticket_url": ticket_url, "replies": int(reply_m.group(1)) if reply_m else 0,
            "has_files": bool(re.search(r'Files:', body)),
            "suggestions": suggestions,
        })
    return results

raw_text = sys.stdin.read()
questions = parse_messages(raw_text)
questions.sort(key=lambda q: q['date'], reverse=True)

aest = timezone(timedelta(hours=10))
now = datetime.now(tz=aest)
generated_at = now.strftime("%-d %b %Y %I:%M %p AEST")
js_data = json.dumps(questions, ensure_ascii=False)
count = len(questions)
dates = sorted(q['date'] for q in questions)
if dates:
    earliest = datetime.strptime(dates[0], "%Y-%m-%d").strftime("%b %Y")
    latest = datetime.strptime(dates[-1], "%Y-%m-%d").strftime("%b %Y")
    date_range = f"{earliest} – {latest}"
else:
    date_range = "No data"
label = f"{date_range} \xb7 {count} questions \xb7 refreshed {generated_at}"

# Use __LABEL__ and __JS_DATA__ as placeholders to avoid f-string brace conflicts with CSS/JS
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Pod 41 · Questions Dashboard</title>
<style>
  :root { color-scheme: light; }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f5f5f7; color: #1d1d1f; font-size: 14px; min-height: 100vh; }
  header { background: #fff; border-bottom: 1px solid #e5e5ea; padding: 16px 20px; display: flex; align-items: center; justify-content: space-between; position: sticky; top: 0; z-index: 100; }
  .header-left { display: flex; align-items: center; gap: 10px; }
  .channel-badge { background: #4A154B; color: #fff; font-size: 11px; font-weight: 600; padding: 3px 8px; border-radius: 12px; letter-spacing: 0.3px; white-space: nowrap; }
  header h1 { font-size: 16px; font-weight: 700; color: #1d1d1f; }
  .last-updated { font-size: 11px; color: #8e8e93; margin-top: 2px; }
  .main { padding: 20px; }
  .stats-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin-bottom: 20px; }
  .stat-card { background: #fff; border-radius: 12px; padding: 14px 16px; border: 1px solid #e5e5ea; }
  .stat-card .stat-label { font-size: 11px; font-weight: 500; color: #8e8e93; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 4px; }
  .stat-card .stat-value { font-size: 26px; font-weight: 700; line-height: 1; color: #1d1d1f; }
  .stat-card.purple .stat-value { color: #4A154B; }
  .stat-card.green  .stat-value { color: #34c759; }
  .stat-card.orange .stat-value { color: #ff9500; }
  .stat-card.blue   .stat-value { color: #007aff; }
  .filter-bar { background: #fff; border: 1px solid #e5e5ea; border-radius: 12px; padding: 12px 16px; display: flex; gap: 10px; flex-wrap: wrap; align-items: center; margin-bottom: 16px; }
  .search-wrap { position: relative; flex: 1; min-width: 180px; }
  .search-wrap input { width: 100%; border: 1px solid #d1d1d6; border-radius: 8px; padding: 7px 10px 7px 30px; font-size: 13px; color: #1d1d1f; outline: none; transition: border-color 0.15s; }
  .search-wrap input:focus { border-color: #4A154B; }
  .search-icon { position: absolute; left: 9px; top: 50%; transform: translateY(-50%); color: #8e8e93; font-size: 13px; }
  .filter-select { border: 1px solid #d1d1d6; border-radius: 8px; padding: 7px 10px; font-size: 13px; color: #1d1d1f; background: #fff; outline: none; cursor: pointer; min-width: 140px; }
  .filter-select:focus { border-color: #4A154B; }
  .filter-count { font-size: 12px; color: #8e8e93; white-space: nowrap; }
  .table-wrap { background: #fff; border: 1px solid #e5e5ea; border-radius: 12px; overflow: hidden; }
  table { width: 100%; border-collapse: collapse; }
  thead { background: #f5f5f7; border-bottom: 1px solid #e5e5ea; }
  th { text-align: left; padding: 10px 14px; font-size: 11px; font-weight: 600; color: #8e8e93; text-transform: uppercase; letter-spacing: 0.5px; cursor: pointer; user-select: none; white-space: nowrap; }
  th:hover { color: #4A154B; }
  tbody tr { border-bottom: 1px solid #f0f0f0; cursor: pointer; transition: background 0.1s; }
  tbody tr:last-child { border-bottom: none; }
  tbody tr:hover { background: #faf5fb; }
  tbody tr.expanded-row { background: #faf5fb; }
  td { padding: 11px 14px; vertical-align: top; }
  .td-date { color: #8e8e93; font-size: 12px; white-space: nowrap; }
  .td-requester { font-weight: 600; font-size: 13px; white-space: nowrap; }
  .td-ka { font-family: "SF Mono","Fira Code",monospace; font-size: 12px; color: #4A154B; white-space: nowrap; }
  .td-summary { font-size: 13px; color: #3a3a3c; max-width: 320px; line-height: 1.4; }
  .td-summary-text { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
  .ticket-link { color: #4A154B; text-decoration: none; font-size: 12px; font-weight: 500; }
  .ticket-link:hover { text-decoration: underline; }
  .area-tag { display: inline-block; background: #f0e8f1; color: #4A154B; border-radius: 6px; padding: 2px 7px; font-size: 11px; font-weight: 500; max-width: 180px; word-break: break-word; }
  .expand-row td { padding: 0; background: #fdf8fe; border-bottom: 2px solid #e5d6e8; }
  .expand-content { padding: 16px 18px; display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 14px; }
  .expand-section h4 { font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.6px; color: #4A154B; margin-bottom: 5px; }
  .expand-section p { font-size: 13px; color: #3a3a3c; line-height: 1.5; }
  .expand-section p + p { margin-top: 3px; }
  .expand-section ul { padding-left: 16px; }
  .expand-section li { font-size: 13px; color: #3a3a3c; line-height: 1.5; margin-bottom: 4px; }
  .expand-full { grid-column: 1 / -1; }
  .empty-state { text-align: center; padding: 40px; color: #8e8e93; font-size: 13px; }
  .suggestion-speaker { font-weight: 600; color: #4A154B; }
  .no-suggestions { color: #c7c7cc; font-size: 12px; font-style: italic; }
</style>
</head>
<body>
<header>
  <div class="header-left">
    <span class="channel-badge">#support-pod-41-ctrl-alt-elite</span>
    <div><h1>Questions Dashboard</h1><div class="last-updated">__LABEL__</div></div>
  </div>
</header>
<div class="main">
  <div class="stats-row">
    <div class="stat-card purple"><div class="stat-label">Total Questions</div><div class="stat-value" id="statTotal">–</div></div>
    <div class="stat-card blue"><div class="stat-label">Product Areas</div><div class="stat-value" id="statAreas">–</div></div>
    <div class="stat-card green"><div class="stat-label">Ash Arraiza</div><div class="stat-value" id="statAsh">–</div></div>
    <div class="stat-card orange"><div class="stat-label">Chris Yinfoo</div><div class="stat-value" id="statChris">–</div></div>
    <div class="stat-card" style="border-color:#e5e5ea"><div class="stat-label">Meher Gambhir</div><div class="stat-value" id="statMeher" style="color:#af52de">–</div></div>
  </div>
  <div class="filter-bar">
    <div class="search-wrap"><span class="search-icon">🔍</span><input type="text" id="searchInput" placeholder="Search issue, product area, KA, requester…" oninput="renderTable()"></div>
    <select class="filter-select" id="requesterFilter" onchange="renderTable()"><option value="">All Requesters</option></select>
    <select class="filter-select" id="areaFilter" onchange="renderTable()"><option value="">All Product Areas</option></select>
    <select class="filter-select" id="monthFilter" onchange="renderTable()"><option value="">All Months</option></select>
    <span class="filter-count" id="filterCount"></span>
  </div>
  <div class="table-wrap" id="tableContainer"></div>
</div>
<script>
const QUESTIONS=__JS_DATA__;
let sortCol="date",sortDir="desc",expandedIdx=null;
function esc(s){return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");}
function fmtDate(s){const d=new Date(s+"T00:00:00");return d.toLocaleDateString("en-AU",{day:"2-digit",month:"short",year:"numeric"});}
function buildFilters(){
  const req=[...new Set(QUESTIONS.map(q=>q.requester))].sort();
  const areas=[...new Set(QUESTIONS.map(q=>q.area))].sort();
  const months=[...new Set(QUESTIONS.map(q=>q.date.slice(0,7)))].sort().reverse();
  document.getElementById("requesterFilter").innerHTML='<option value="">All Requesters</option>'+req.map(r=>`<option value="${esc(r)}">${esc(r)}</option>`).join("");
  document.getElementById("areaFilter").innerHTML='<option value="">All Product Areas</option>'+areas.map(a=>`<option value="${esc(a)}">${esc(a)}</option>`).join("");
  document.getElementById("monthFilter").innerHTML='<option value="">All Months</option>'+months.map(m=>{const d=new Date(m+"-01T00:00:00");return`<option value="${m}">${d.toLocaleDateString("en-AU",{month:"long",year:"numeric"})}</option>`;}).join("");
}
function updateStats(){
  document.getElementById("statTotal").textContent=QUESTIONS.length;
  document.getElementById("statAreas").textContent=new Set(QUESTIONS.map(q=>q.area)).size;
  document.getElementById("statAsh").textContent=QUESTIONS.filter(q=>q.requester==="Ash Arraiza").length;
  document.getElementById("statChris").textContent=QUESTIONS.filter(q=>q.requester==="Chris Yinfoo").length;
  document.getElementById("statMeher").textContent=QUESTIONS.filter(q=>q.requester==="Meher Gambhir").length;
}
function getFiltered(){
  const s=document.getElementById("searchInput").value.toLowerCase();
  const req=document.getElementById("requesterFilter").value;
  const area=document.getElementById("areaFilter").value;
  const month=document.getElementById("monthFilter").value;
  return QUESTIONS.filter(q=>{
    if(req&&q.requester!==req)return false;
    if(area&&q.area!==area)return false;
    if(month&&!q.date.startsWith(month))return false;
    if(s){const hay=[q.requester,q.area,q.summary,q.ka,...q.tried,...(q.suggestions||[])].join(" ").toLowerCase();if(!hay.includes(s))return false;}
    return true;
  });
}
function sortRows(rows){return[...rows].sort((a,b)=>{let va=a[sortCol],vb=b[sortCol];if(va<vb)return sortDir==="asc"?-1:1;if(va>vb)return sortDir==="asc"?1:-1;return 0;});}
function handleSort(col){if(sortCol===col)sortDir=sortDir==="asc"?"desc":"asc";else{sortCol=col;sortDir="desc";}renderTable();}
function si(col){return sortCol===col?(sortDir==="asc"?"↑":"↓"):'<span style="opacity:0.35">↕</span>';}
function renderSuggestions(suggestions){
  if(!suggestions||!suggestions.length)return'<p class="no-suggestions">No suggestions recorded</p>';
  return'<ul>'+suggestions.map(s=>{
    const colon=s.indexOf(":");
    if(colon===-1)return`<li>${esc(s)}</li>`;
    const speaker=s.slice(0,colon);
    const text=s.slice(colon+1).trim();
    return`<li><span class="suggestion-speaker">${esc(speaker)}:</span> ${esc(text)}</li>`;
  }).join("")+'</ul>';
}
function renderTable(){
  const filtered=sortRows(getFiltered());
  document.getElementById("filterCount").textContent=`Showing ${filtered.length} of ${QUESTIONS.length}`;
  const c=document.getElementById("tableContainer");
  if(!filtered.length){c.innerHTML='<div class="empty-state">No questions match your filters.</div>';return;}
  let html=`<table><thead><tr><th onclick="handleSort('date')" class="${sortCol==='date'?'sorted':''}">Date ${si('date')}</th><th onclick="handleSort('requester')" class="${sortCol==='requester'?'sorted':''}">Requester ${si('requester')}</th><th>KA</th><th onclick="handleSort('area')" class="${sortCol==='area'?'sorted':''}">Product Area ${si('area')}</th><th>Issue Summary</th><th>Ticket</th></tr></thead><tbody>`;
  filtered.forEach(q=>{
    const oi=QUESTIONS.indexOf(q),isExp=expandedIdx===oi;
    html+=`<tr onclick="toggleExpand(${oi})" class="${isExp?'expanded-row':''}"><td class="td-date">${fmtDate(q.date)}</td><td class="td-requester">${esc(q.requester)}</td><td class="td-ka">${esc(q.ka)}</td><td><span class="area-tag">${esc(q.area)}</span></td><td class="td-summary"><div class="td-summary-text">${esc(q.summary)}</div></td><td>${q.ticket_url?`<a class="ticket-link" href="${esc(q.ticket_url)}" target="_blank" onclick="event.stopPropagation()">View ↗</a>`:'<span style="color:#c7c7cc;font-size:12px">–</span>'}</td></tr>`;
    if(isExp)html+=`<tr class="expand-row"><td colspan="6"><div class="expand-content">`
      +`<div class="expand-section expand-full"><h4>Issue Summary</h4><p>${esc(q.summary)}</p></div>`
      +`<div class="expand-section"><h4>What Has Been Tried</h4>${q.tried.length?'<ul>'+q.tried.map(t=>`<li>${esc(t)}</li>`).join('')+'</ul>':'<p style="color:#c7c7cc">No steps recorded</p>'}</div>`
      +`<div class="expand-section"><h4>What Was Suggested</h4>${renderSuggestions(q.suggestions)}</div>`
      +`<div class="expand-section"><h4>Details</h4><p><strong>KA:</strong> ${esc(q.ka)}</p><p><strong>Requester:</strong> ${esc(q.requester)}</p><p><strong>Date:</strong> ${fmtDate(q.date)}</p>${q.has_files?'<p><strong>Attachments:</strong> ✓ Files attached</p>':''}${q.ticket_url?`<p><strong>Ticket:</strong> <a class="ticket-link" href="${esc(q.ticket_url)}" target="_blank">Open in Zendesk ↗</a></p>`:''}</div>`
      +`</div></td></tr>`;
  });
  html+="</tbody></table>";
  c.innerHTML=html;
}
function toggleExpand(idx){expandedIdx=expandedIdx===idx?null:idx;renderTable();}
buildFilters();updateStats();renderTable();
</script>
</body>
</html>"""

html = HTML_TEMPLATE.replace("__LABEL__", label).replace("__JS_DATA__", js_data)
print(html)
