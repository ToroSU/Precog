(function (global) {
  "use strict";

  function asArray(value) { if (value == null) return []; return Array.isArray(value) ? value : [value]; }
  function cleanText(value) { return value == null ? '' : String(value).trim(); }
  function joinDetails(values) { return values.map(cleanText).filter(Boolean).join(' | '); }
  function bytesToGB(value) { const n = Number(value); return Number.isFinite(n) && n > 0 ? `${(n / 1073741824).toFixed(1)} GB` : ''; }
  function normalizeAppKey(value) { return cleanText(value).toLowerCase().replace(/[^a-z0-9]+/g, ' ').trim(); }
  function appDisplayName(app) { return cleanText(app.DisplayName || app.Name || app.PackageFamilyName || app.PackageName || 'Unknown App'); }
  function appPublisher(app) { return cleanText(app.Publisher || app.publisher || ''); }
  function isMicrosoftApp(app) { const publisher = appPublisher(app); const name = appDisplayName(app); return /Microsoft/i.test(publisher) || /^Microsoft/i.test(name) || /CN=Microsoft/i.test(publisher); }
  function appVersion(app) { return cleanText(app.DisplayVersion || app.Version || app.version || ''); }
  function parseWindowsVersionReg(text) { const obj = {}; String(text || '').split(/\r?\n/).forEach(line => { const m = line.match(/^\s*(\w+)\s+REG_\w+\s+(.+)$/); if (m) obj[m[1]] = m[2].trim(); }); return obj; }
  function splitCsvLine(line) { const out=[]; let cur='', inQ=false; for(let i=0;i<line.length;i++){ const ch=line[i]; if(ch==='"' && line[i+1]==='"'){cur+='"';i++;continue;} if(ch==='"'){inQ=!inQ;continue;} if(ch===','&&!inQ){out.push(cur);cur='';continue;} cur+=ch;} out.push(cur); return out.map(s=>s.trim()); }
  function parseCsv(text) { const rows=[]; const lines=String(text||'').replace(/^\uFEFF/,'').split(/\r?\n/).filter(l=>l.trim()); if(!lines.length)return rows; const headers=splitCsvLine(lines[0]).map(h=>h.trim()); for(let i=1;i<lines.length;i++){ const values=splitCsvLine(lines[i]); const row={}; headers.forEach((h,idx)=>row[h]=values[idx]||''); rows.push(row);} return rows; }
  function normalizeProblem(...vals) { const s=vals.filter(Boolean).join(' '); if(!s||/CM_PROB_NONE/i.test(s))return ''; return s; }
  function isProblemStatus(status, problem, cm) { const s=[status,problem,cm].filter(Boolean).join(' '); return !!s && !/\bOK\b/i.test(status||'') && !/CM_PROB_NONE/i.test(s); }
  function firstMeaningfulLine(text) { return String(text||'').split(/\r?\n/).map(s=>s.trim()).find(Boolean)||'Loaded'; }
  function getDxDiagHeadline(text) { const model=(String(text||'').match(/System Model:\s*(.+)/i)||[])[1]; const os=(String(text||'').match(/Operating System:\s*(.+)/i)||[])[1]; return [model,os].filter(Boolean).join(' | ')||'Display / audio diagnostics available'; }
  function getDeviceHuntInfo(rawId) { if(!rawId)return null; const id=String(rawId).toUpperCase(); const pci=id.match(/^PCI\\VEN_([0-9A-F]{4})&DEV_([0-9A-F]{4})/); if(pci)return {type:'pci',vendor:pci[1],device:pci[2],url:`https://devicehunt.com/view/type/pci/vendor/${pci[1]}/device/${pci[2]}`}; const usb=id.match(/^USB\\VID_([0-9A-F]{4})&PID_([0-9A-F]{4})/); if(usb)return {type:'usb',vendor:usb[1],device:usb[2],url:`https://devicehunt.com/view/type/usb/vendor/${usb[1]}/device/${usb[2]}`}; return null; }

  global.PrecogUtils={asArray,cleanText,joinDetails,bytesToGB,normalizeAppKey,appDisplayName,appPublisher,isMicrosoftApp,appVersion,parseWindowsVersionReg,parseCsv,splitCsvLine,normalizeProblem,isProblemStatus,firstMeaningfulLine,getDxDiagHeadline,getDeviceHuntInfo};
})(window);
