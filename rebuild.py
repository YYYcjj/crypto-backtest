import json, os
from collections import defaultdict

with open('journal_trades.json') as f: trades = json.load(f)
with open('trade_paths.json') as f: paths = json.load(f)

data_json = json.dumps(trades, ensure_ascii=False)
paths_json = json.dumps([p if p else [] for p in paths], ensure_ascii=False, indent=1)

total = len(trades); wins = sum(1 for t in trades if t['pnl_usdt'] > 0)
total_pnl = sum(t['pnl_usdt'] for t in trades)
win_rate = round(wins/total*100) if total else 0

coin_stats = defaultdict(lambda: {"pnl": 0, "count": 0})
for t in trades: coin_stats[t['coin']]['pnl'] += t['pnl_usdt']; coin_stats[t['coin']]['count'] += 1

daily_pnl = defaultdict(float)
for t in trades: daily_pnl[t['entry_time'][:10]] += t['pnl_usdt']
daily_data, cum = [], 0
for day, pnl in sorted(daily_pnl.items()):
    cum += pnl; daily_data.append({"day": day[5:], "pnl": round(pnl,1), "cum": round(cum,1)})

mae_vals = [t.get('mae_pct',0) for t in trades]; mfe_vals = [t.get('mfe_pct',0) for t in trades]
avg_mae = sum(abs(v) for v in mae_vals)/len(mae_vals); avg_mfe = sum(mfe_vals)/len(mfe_vals)
coins = [{"name": k, "pnl": round(v['pnl'],1), "count": v['count']} for k,v in coin_stats.items()]
coins.sort(key=lambda x: x['pnl'], reverse=True)
coins_json = json.dumps(coins, ensure_ascii=False)
daily_json = json.dumps(daily_data, ensure_ascii=False)

def esc(s):
    for tag in ['/b>', '/span>', '/td>', '/tr>', '/strong>', '/div>', '/table>', '/tbody>', '/thead>', '/th>', '/a>', '/p>', '/h1>', '/h2>', '/h3>', '/option>', '/select>', '/input>', '/canvas>', '/html>', '/body>', '/head>', '/title>', '/style>', '/script>']:
        s = s.replace('<' + tag, '<\\' + tag)
    return s

# PATHS as separate JSON
with open('paths_data.json', 'w') as f:
    f.write(paths_json)
print(f'PATHS: {len(paths_json)} bytes')

# Build JS
js_lines = []
js_lines.append('var D=' + esc(data_json) + ';')
js_lines.append('var PATHS=null;')
js_lines.append('var curIdx=null,pc=null,sc=null;')
js_lines.append('fetch("paths_data.json").then(function(r){return r.json()}).then(function(d){PATHS=d;R();});')

# Chart IIFE
js_lines.append('(function(){')
js_lines.append('var cd=' + daily_json + ',cs=' + coins_json + ';')
js_lines.append('new Chart(cCum,{type:"line",data:{labels:cd.map(function(x){return x.day}),datasets:[{data:cd.map(function(x){return x.cum}),borderColor:"#0d6efd",backgroundColor:"rgba(13,110,253,.1)",fill:true,tension:.3,pointRadius:0}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{ticks:{maxTicksLimit:15,color:"#6c757d"}},y:{ticks:{color:"#6c757d",callback:function(v){return v+"U"}}}}}});')
js_lines.append('cs.sort(function(a,b){return b.pnl-a.pnl});')
js_lines.append('new Chart(cCoin,{type:"bar",data:{labels:cs.map(function(c){return c.name}),datasets:[{data:cs.map(function(c){return c.pnl}),backgroundColor:cs.map(function(c){return c.pnl>0?"rgba(25,135,84,.7)":"rgba(220,53,69,.7)"}),borderColor:cs.map(function(c){return c.pnl>0?"#198754":"#dc3545"}),borderWidth:1,borderRadius:3}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{ticks:{color:"#6c757d"}},y:{ticks:{color:"#6c757d",callback:function(v){return v+"U"}}}}}});')
js_lines.append('var md=D.map(function(t){return{x:t.mae_pct||0,y:t.mfe_pct||0,c:t.coin}});')
js_lines.append('new Chart(cMAE,{type:"scatter",data:{datasets:[{data:md,backgroundColor:md.map(function(d){return d.y>0?"rgba(25,135,84,.5)":"rgba(220,53,69,.5)"}),pointRadius:5}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{callbacks:{label:function(c){return c.raw.c+" MAE:"+c.raw.x+"% MFE:"+c.raw.y+"%"}}}},scales:{x:{title:{display:true,text:"MAE%",color:"#6c757d"},ticks:{color:"#6c757d",callback:function(v){return v+"%"}}},y:{title:{display:true,text:"MFE%",color:"#6c757d"},ticks:{color:"#6c757d",callback:function(v){return v+"%"}}}}}});')
js_lines.append('new Chart(cDay,{type:"bar",data:{labels:cd.map(function(x){return x.day}),datasets:[{data:cd.map(function(x){return x.pnl}),backgroundColor:cd.map(function(x){return x.pnl>0?"rgba(25,135,84,.6)":"rgba(220,53,69,.6)"}),borderWidth:1,borderRadius:3}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{ticks:{maxTicksLimit:12,color:"#6c757d"}},y:{ticks:{color:"#6c757d",callback:function(v){return v+"U"}}}}}});')
js_lines.append('})();')

# RT function
js_lines.append('function RT(){')
js_lines.append('if(!D||!PATHS)return;')
js_lines.append('var q=document.getElementById("search").value.toLowerCase();')
js_lines.append('var d=document.getElementById("fDir").value,r=document.getElementById("fRes").value;')
js_lines.append('var df=document.getElementById("dFrom").value,dt2=document.getElementById("dTo").value;')
js_lines.append('var f=[];for(var i=D.length-1;i>=0;i--){var t=D[i];')
js_lines.append('if(df&&t.entry_time<df+" 00:00")continue;if(dt2&&t.entry_time>dt2+" 23:59")continue;')
js_lines.append('if(q&&t.coin.toLowerCase().indexOf(q)<0)continue;')
js_lines.append('if(d!=="all"&&t.direction!==d)continue;')
js_lines.append('if(r==="win"&&t.pnl_usdt<=0)continue;if(r==="lose"&&t.pnl_usdt>=0)continue;')
js_lines.append('f.push({trade:t,idx:i});}')
js_lines.append('document.getElementById("rowCount").textContent=f.length+"/"+D.length+"\u7b14";')
js_lines.append('var tb=document.getElementById("tbody");tb.innerHTML="";')
js_lines.append('f.forEach(function(x){var t=x.trade,oi=x.idx;')
js_lines.append('var r2=document.createElement("tr");r2.className="clickable";')
js_lines.append('r2.onclick=function(idx){return function(){TD(idx,this)}(oi);}(oi);')
js_lines.append('var c1=document.createElement("td");c1.textContent=t.entry_time.substr(0,16);r2.appendChild(c1);')
js_lines.append('var c2=document.createElement("td");c2.innerHTML="<b>"+t.coin+"<\/b>";r2.appendChild(c2);')
js_lines.append('var c3=document.createElement("td");c3.innerHTML="<span class=badge "+(t.direction==="\u505a\u591a"?"badge-long":"badge-short")+">"+t.direction+"<\/span>";r2.appendChild(c3);')
js_lines.append('var c4=document.createElement("td");c4.textContent=t.trend_1h+"/"+t.trend_4h+"/"+t.trend_1d;r2.appendChild(c4);')
js_lines.append('var c5=document.createElement("td");c5.textContent=t.srsi_1h+"/"+t.srsi_4h+"/"+t.srsi_1d;r2.appendChild(c5);')
js_lines.append('var c6=document.createElement("td");c6.textContent=""+t.entry_price;r2.appendChild(c6);')
js_lines.append('var c7=document.createElement("td");c7.textContent=""+t.exit_price;r2.appendChild(c7);')
js_lines.append('var c8=document.createElement("td");c8.textContent=t.pnl_pct.toFixed(1)+"%";c8.className=t.pnl_usdt>0?"green":"red";r2.appendChild(c8);')
js_lines.append('var c9=document.createElement("td");c9.textContent=(t.mae_pct||0).toFixed(1)+"%";c9.className="red";r2.appendChild(c9);')
js_lines.append('var ca=document.createElement("td");ca.textContent=(t.mfe_pct||0).toFixed(1)+"%";ca.className="green";r2.appendChild(ca);')
js_lines.append('var cb=document.createElement("td");cb.innerHTML="<span class=badge "+(t.pnl_usdt>0?"badge-win":"badge-lose")+">"+(t.pnl_usdt>0?"\u8d62":"\u4e8f")+"<\/span>";r2.appendChild(cb);')
js_lines.append('tb.appendChild(r2);')
js_lines.append('var dr=document.createElement("tr");dr.className="detail-row";dr.id="dr-"+oi;')
js_lines.append('var dtc=document.createElement("td");dtc.colSpan=11;var dd=document.createElement("div");dd.id="dc-"+oi;dtc.appendChild(dd);dr.appendChild(dtc);tb.appendChild(dr);')
js_lines.append('});}')

# TD
js_lines.append('function TD(idx,row){')
js_lines.append('if(!PATHS)return;var dr=document.getElementById("dr-"+idx),vis=dr.classList.contains("show");')
js_lines.append('var all=document.querySelectorAll(".detail-row.show");for(var i=0;i<all.length;i++)all[i].classList.remove("show");')
js_lines.append('var al2=document.querySelectorAll("tr.expanded");for(var i=0;i<al2.length;i++)al2[i].classList.remove("expanded");')
js_lines.append('if(pc){try{pc.destroy()}catch(e){}}if(sc){try{sc.destroy()}catch(e){}}pc=null;sc=null;')
js_lines.append('if(vis){curIdx=null;return}row.classList.add("expanded");dr.classList.add("show");curIdx=idx;')
js_lines.append('var t=D[idx],p=PATHS[idx],cd2=document.getElementById("dc-"+idx);cd2.innerHTML="";')
js_lines.append('if(!p||!p.bars||!p.bars.length){var nd=document.createElement("div");nd.style.padding="20px";nd.textContent="\u65e0\u6570\u636e";cd2.appendChild(nd);return}')
js_lines.append('var bars=p.bars,sv=p.srsi||[],times=p.time_labels||[],ex=p.exit_idx;')
js_lines.append('var lbs=[];for(var i=0;i<times.length;i++)lbs.push(i%8===0?times[i]:"");')
js_lines.append('var hm=p.hold_mae||0,hx=p.hold_mfe||0,pm=p.post_mae||0,px=p.post_mfe||0;')
js_lines.append('var d2=document.createElement("div");d2.className="detail-info";')
js_lines.append('d2.innerHTML="<span><b>\u6301\u4ed3<\/b> \u6700\u5927\u4e8f\u635f:<b class=red>"+hm+"%<\/b> \u6700\u5927\u76c8\u5229:<b class=green>"+hx+"%<\/b><\/span><span style=border-left:2px dashed #dc3545;padding-left:8px><b>\u79bb\u573a\u540e2\u5929<\/b> \u6700\u5927\u4e8f\u635f:<b class=red>"+pm+"%<\/b> \u6700\u5927\u76c8\u5229:<b class=green>"+px+"%<\/b><\/span>";')
js_lines.append('cd2.appendChild(d2);')
js_lines.append('var pd=document.createElement("div");pd.className="price-chart";cd2.appendChild(pd);var pv=document.createElement("canvas");pd.appendChild(pv);')
js_lines.append('var hl=ex!=null?ex+1:bars.length,mi=Infinity,mx=-Infinity,hi=-1,hj=-1;')
js_lines.append('for(var i=0;i<hl&&i<bars.length;i++){if(bars[i]<mi){mi=bars[i];hi=i}if(bars[i]>mx){mx=bars[i];hj=i}}')
js_lines.append('var mkd=Array(bars.length).fill(null),mxd=Array(bars.length).fill(null);if(hi>=0)mkd[hi]=mi;if(hj>=0)mxd[hj]=mx;')
js_lines.append('var lp={id:"ln",afterDraw:function(chart){var c=chart.ctx,x=chart.scales.x,y=chart.scales.y,y0=y.getPixelForValue(0);c.save();c.beginPath();c.setLineDash([4,4]);c.strokeStyle="rgba(108,117,125,.3)";c.lineWidth=1;c.moveTo(x.left,y0);c.lineTo(x.right,y0);c.stroke();c.restore();c.save();c.beginPath();c.setLineDash([6,3]);c.strokeStyle="rgba(25,135,84,.6)";c.lineWidth=2;var xe=x.getPixelForValue(0);c.moveTo(xe,y.top);c.lineTo(xe,y.bottom);c.stroke();c.fillStyle="rgba(25,135,84,.9)";c.font="bold 10px sans-serif";c.fillText("\u5165\u573a",xe+4,y.top+16);c.restore();if(ex!=null){c.save();var xe2=x.getPixelForValue(ex);c.fillStyle="rgba(200,200,200,.08)";c.fillRect(xe2,y.top,x.right-xe2,y.bottom-y.top);c.beginPath();c.setLineDash([6,4]);c.strokeStyle="#dc3545";c.lineWidth=2.5;c.moveTo(xe2,y.top);c.lineTo(xe2,y.bottom);c.stroke();c.fillStyle="#dc3545";c.font="bold 10px sans-serif";c.fillText("\u79bb\u573a",xe2+4,y.top+16);c.restore();}}};')
js_lines.append('pc=new Chart(pv.getContext("2d"),{type:"line",plugins:[lp],data:{labels:lbs,datasets:[{data:bars,borderColor:"#0d6efd",backgroundColor:"rgba(13,110,253,.08)",fill:true,tension:.2,pointRadius:0,borderWidth:2,label:"\u4ef7\u683c%"},{data:mkd,borderColor:"#dc3545",backgroundColor:"#dc3545",pointRadius:6,pointStyle:"rectRot",showLine:false,label:"\u6700\u5927\u4e8f\u635f"},{data:mxd,borderColor:"#198754",backgroundColor:"#198754",pointRadius:6,pointStyle:"triangle",showLine:false,label:"\u6700\u5927\u76c8\u5229"}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:true,position:"top",labels:{boxWidth:12,font:{size:10},usePointStyle:true}}},scales:{x:{display:false,grid:{display:false}},y:{ticks:{color:"#6c757d",callback:function(v){return v+"%"}},title:{display:true,text:"\u4ef7\u683c%",color:"#6c757d"}}}}});')
js_lines.append('var sd=document.createElement("div");sd.className="srsi-chart";cd2.appendChild(sd);var sv2=document.createElement("canvas");sd.appendChild(sv2);')
js_lines.append('sc=new Chart(sv2.getContext("2d"),{type:"line",data:{labels:lbs,datasets:[{data:sv,borderColor:"rgba(245,159,0,.7)",backgroundColor:"rgba(245,159,0,.1)",fill:true,tension:.1,pointRadius:0,borderWidth:1.5,label:"SRSI K"}]},options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:true,position:"top",labels:{boxWidth:12,font:{size:10}}}}},scales:{x:{ticks:{color:"#6c757d",maxTicksLimit:10,maxRotation:45},grid:{display:false}},y:{min:0,max:100,ticks:{color:"#6c757d",stepSize:25},grid:{color:"rgba(0,0,0,.05)"}}}}});')
js_lines.append('}')

js = '\n'.join(js_lines)
assert '</' not in js, 'FATAL'

with open('app.js', 'w') as f:
    f.write(js)
print(f'JS: {len(js)} chars, max line: {max(len(l) for l in js.split(chr(10)))}')

# HTML
html = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>交易日记 · 6月</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
:root{--bg:#f8f9fa;--card:#fff;--text:#212529;--muted:#6c757d;--green:#198754;--red:#dc3545;--blue:#0d6efd;--border:#dee2e6}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC',sans-serif;background:var(--bg);color:var(--text);padding:16px;max-width:1200px;margin:0 auto}
h1{font-size:22px;margin-bottom:4px}.sub{color:var(--muted);font-size:13px;margin-bottom:16px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-bottom:16px}
.card{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:14px;text-align:center}
.card .label{font-size:11px;color:var(--muted)}.card .value{font-size:24px;font-weight:700}
.green{color:var(--green)}.red{color:var(--red)}
.charts{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px}
@media(max-width:768px){.charts{grid-template-columns:1fr}}
.chart-box{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:14px}
.chart-box h3{font-size:13px;margin-bottom:8px;color:var(--muted)}
.chart-wrap{position:relative;height:240px}canvas{width:100%!important}
table{width:100%;border-collapse:collapse;font-size:12px;background:var(--card);border-radius:8px;overflow:hidden;border:1px solid var(--border)}
th{background:#e9ecef;padding:8px 10px;text-align:left;font-weight:600;color:var(--muted);border-bottom:2px solid var(--blue);font-size:11px;white-space:nowrap}
td{padding:6px 10px;border-bottom:1px solid var(--border)}
tr.clickable{cursor:pointer}tr.clickable:hover td{background:#e7f1ff}
tr:nth-child(even) td{background:var(--bg)}tr:nth-child(even):hover td{background:#e7f1ff}
tr.expanded td{background:#e7f1ff!important;border-bottom:2px solid var(--blue)}
.detail-row{display:none;background:#f0f7ff}.detail-row.show{display:table-row}
.detail-row td{padding:0 10px 16px}
.price-chart{height:240px;margin-top:8px}.srsi-chart{height:120px}
.badge{display:inline-block;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:600}
.badge-win{background:#d1e7dd;color:var(--green)}.badge-lose{background:#f8d7da;color:var(--red)}
.badge-long{background:#d1e7dd;color:var(--green)}.badge-short{background:#f8d7da;color:var(--red)}
.btn{display:inline-block;padding:8px 18px;border-radius:6px;font-size:13px;font-weight:600;text-decoration:none;margin-right:8px}
.btn-down{background:var(--green);color:#fff}
.toolbar{display:flex;justify-content:space-between;align-items:center;margin:16px 0 8px;flex-wrap:wrap;gap:8px}
.toolbar input{padding:6px 12px;border:1px solid var(--border);border-radius:6px;font-size:12px;outline:none;width:200px}
.toolbar input:focus{border-color:var(--blue)}
.toolbar select{padding:6px 12px;border:1px solid var(--border);border-radius:6px;font-size:12px;outline:none;background:var(--card)}
.detail-info{display:flex;gap:16px;flex-wrap:wrap;font-size:12px;margin:8px 0;color:var(--muted)}
</style>
</head>
<body>
<h1>6月交易记录</h1>
<div class="sub">OKX · 2x · ''' + str(total) + '''笔</div>
<div class="cards">
<div class="card"><div class="label">总交易</div><div class="value">''' + str(total) + '''</div></div>
<div class="card"><div class="label">胜率</div><div class="value ''' + ('green' if win_rate>=50 else 'red') + '''">''' + str(win_rate) + '''%</div></div>
<div class="card"><div class="label">净盈亏</div><div class="value ''' + ('green' if total_pnl>0 else 'red') + '''">''' + format(total_pnl, '+.1f') + '''U</div></div>
<div class="card"><div class="label">均最大亏损</div><div class="value red">''' + format(avg_mae, '.1f') + '''%</div></div>
<div class="card"><div class="label">均最大盈利</div><div class="value green">''' + format(avg_mfe, '.1f') + '''%</div></div>
</div>
<a href="交易记录_06.xlsx" class="btn btn-down" download>下载 Excel</a>
<div class="charts">
<div class="chart-box"><h3>累计盈亏走势</h3><div class="chart-wrap"><canvas id="cCum"></canvas></div></div>
<div class="chart-box"><h3>品种盈亏</h3><div class="chart-wrap"><canvas id="cCoin"></canvas></div></div>
<div class="chart-box"><h3>最大亏损 vs 最大盈利</h3><div class="chart-wrap"><canvas id="cMAE"></canvas></div></div>
<div class="chart-box"><h3>日盈亏</h3><div class="chart-wrap"><canvas id="cDay"></canvas></div></div>
</div>
<div class="toolbar">
从 <input type="date" id="dFrom" onchange="RT()" style="width:130px"> 到 <input type="date" id="dTo" onchange="RT()" style="width:130px">
<input type="text" id="search" placeholder="搜索..." oninput="RT()">
<select id="fDir" onchange="RT()"><option value="all">全部</option><option value="做多">做多</option><option value="做空">做空</option></select>
<select id="fRes" onchange="RT()"><option value="all">全部</option><option value="win">盈利</option><option value="lose">亏损</option></select>
<span style="font-size:11px;color:var(--muted)" id="rowCount"></span>
</div>
<table><thead><tr><th>日期</th><th>币种</th><th>方向</th><th>趋势</th><th>SRSI</th><th>入场价</th><th>离场价</th><th>盈亏%</th><th>最大亏损</th><th>最大盈利</th><th>结果</th></tr></thead><tbody id="tbody"></tbody></table>
<script src="app.js"></script>
</body></html>'''

with open('index.html', 'w') as f:
    f.write(html)
print(f'HTML: {len(html)} chars')
print('DONE')
