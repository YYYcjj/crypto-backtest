import json
from collections import defaultdict

# Load data
with open('results/journal_trades.json') as f: trades = json.load(f)
with open('results/trade_paths.json') as f: paths = json.load(f)

data_json = json.dumps(trades, ensure_ascii=False, separators=(',', ':'))
# PATHS as separate JSON file, not inline
paths_clean = []
for p in paths:
    if p:
        paths_clean.append({
            'b': p['bars'],
            's': p['srsi'],
            't': p['time_labels'],
            'ex': p['exit_idx'],
            'hm': p['hold_mae'],
            'hx': p['hold_mfe'],
            'pm': p['post_mae'],
            'px': p['post_mfe']
        })
    else:
        paths_clean.append(None)
paths_json = json.dumps(paths_clean, ensure_ascii=False, indent=1)
with open('results/paths_data.json', 'w') as f:
    f.write(paths_json)
print(f'PATHS: {len(paths_json)} bytes')

# Stats
total = len(trades)
wins = sum(1 for t in trades if t['pnl_usdt'] > 0)
total_pnl = sum(t['pnl_usdt'] for t in trades)
win_rate = round(wins/total*100)

coin_stats = defaultdict(lambda: {"pnl": 0, "count": 0})
for t in trades: coin_stats[t['coin']]['pnl'] += t['pnl_usdt']; coin_stats[t['coin']]['count'] += 1

daily_pnl = defaultdict(float)
for t in trades: daily_pnl[t['entry_time'][:10]] += t['pnl_usdt']
daily_data, cum = [], 0
for day, pnl in sorted(daily_pnl.items()):
    cum += pnl; daily_data.append({"d": day[5:], "p": round(pnl,1), "c": round(cum,1)})

mae_vals = [t.get('mae_pct',0) for t in trades]; mfe_vals = [t.get('mfe_pct',0) for t in trades]
avg_mae = sum(abs(v) for v in mae_vals)/len(mae_vals); avg_mfe = sum(mfe_vals)/len(mfe_vals)

coins = [{"n": k, "p": round(v['pnl'],1), "c": v['count']} for k,v in coin_stats.items()]
coins.sort(key=lambda x: x['p'], reverse=True)

daily_json = json.dumps(daily_data, ensure_ascii=False, separators=(',', ':'))
coins_json = json.dumps(coins, ensure_ascii=False, separators=(',', ':'))

html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>交易日记 · 6月</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"><\/script>
<style>
:root{{--bg:#f8f9fa;--card:#fff;--text:#212529;--muted:#6c757d;--green:#198754;--red:#dc3545;--blue:#0d6efd;--border:#dee2e6}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC',sans-serif;background:var(--bg);color:var(--text);padding:16px;max-width:1200px;margin:0 auto}}
h1{{font-size:22px;margin-bottom:4px}}.sub{{color:var(--muted);font-size:13px;margin-bottom:16px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-bottom:16px}}
.card{{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:14px;text-align:center}}
.card .label{{font-size:11px;color:var(--muted)}}.card .value{{font-size:24px;font-weight:700}}
.green{{color:var(--green)}}.red{{color:var(--red)}}
.charts{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:16px}}
@media(max-width:768px){{.charts{{grid-template-columns:1fr}}}}
.chart-box{{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:14px}}
.chart-box h3{{font-size:13px;margin-bottom:8px;color:var(--muted)}}
.chart-wrap{{position:relative;height:240px}}canvas{{width:100%!important}}
table{{width:100%;border-collapse:collapse;font-size:12px;background:var(--card);border-radius:8px;overflow:hidden;border:1px solid var(--border)}}
th{{background:#e9ecef;padding:8px 10px;text-align:left;font-weight:600;color:var(--muted);border-bottom:2px solid var(--blue);font-size:11px;white-space:nowrap}}
td{{padding:6px 10px;border-bottom:1px solid var(--border)}}
tr.clickable{{cursor:pointer}}tr.clickable:hover td{{background:#e7f1ff}}
tr:nth-child(even) td{{background:var(--bg)}}tr:nth-child(even):hover td{{background:#e7f1ff}}
tr.expanded td{{background:#e7f1ff!important;border-bottom:2px solid var(--blue)}}
.detail-row{{display:none;background:#f0f7ff}}.detail-row.show{{display:table-row}}
.detail-row td{{padding:0 10px 16px}}
.price-chart{{height:240px;margin-top:8px}}.srsi-chart{{height:120px;margin-top:0}}
.badge{{display:inline-block;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:600}}
.badge-win{{background:#d1e7dd;color:var(--green)}}.badge-lose{{background:#f8d7da;color:var(--red)}}
.badge-long{{background:#d1e7dd;color:var(--green)}}.badge-short{{background:#f8d7da;color:var(--red)}}
.btn{{display:inline-block;padding:8px 18px;border-radius:6px;font-size:13px;font-weight:600;text-decoration:none;margin-right:8px}}
.btn-down{{background:var(--green);color:#fff}}
.toolbar{{display:flex;justify-content:space-between;align-items:center;margin:16px 0 8px;flex-wrap:wrap;gap:8px}}
.toolbar input{{padding:6px 12px;border:1px solid var(--border);border-radius:6px;font-size:12px;outline:none;width:200px}}
.toolbar input:focus{{border-color:var(--blue)}}
.toolbar select{{padding:6px 12px;border:1px solid var(--border);border-radius:6px;font-size:12px;outline:none;background:var(--card)}}
.detail-info{{display:flex;gap:16px;flex-wrap:wrap;font-size:12px;margin:8px 0;color:var(--muted)}}
</style>
</head>
<body>
<h1>6月交易记录</h1>
<div class="sub">OKX · 2x · {total}笔交易</div>
<div class="cards">
<div class="card"><div class="label">总交易</div><div class="value">{total}</div></div>
<div class="card"><div class="label">胜率</div><div class="value {'green' if win_rate>=50 else 'red'}">{win_rate}%</div></div>
<div class="card"><div class="label">净盈亏</div><div class="value {'green' if total_pnl>0 else 'red'}">{total_pnl:+.1f}U</div></div>
<div class="card"><div class="label">均最大亏损</div><div class="value red">{avg_mae:.1f}%</div></div>
<div class="card"><div class="label">均最大盈利</div><div class="value green">{avg_mfe:.1f}%</div></div>
</div>
<a href="交易记录_06.xlsx" class="btn btn-down" download>下载 Excel</a>
<div class="charts">
<div class="chart-box"><h3>累计盈亏走势</h3><div class="chart-wrap"><canvas id="c0"></canvas></div></div>
<div class="chart-box"><h3>品种盈亏</h3><div class="chart-wrap"><canvas id="c1"></canvas></div></div>
<div class="chart-box"><h3>最大亏损 vs 最大盈利</h3><div class="chart-wrap"><canvas id="c2"></canvas></div></div>
<div class="chart-box"><h3>日盈亏</h3><div class="chart-wrap"><canvas id="c3"></canvas></div></div>
</div>
<div class="toolbar">
从 <input type="date" id="df" onchange="R()" style="width:130px"> 到 <input type="date" id="dt" onchange="R()" style="width:130px">
<input type="text" id="sq" placeholder="搜索品种..." oninput="R()">
<select id="fd" onchange="R()"><option value="all">全部方向</option><option value="做多">做多</option><option value="做空">做空</option></select>
<select id="fr" onchange="R()"><option value="all">全部结果</option><option value="win">盈利</option><option value="lose">亏损</option></select>
<span style="font-size:11px;color:var(--muted)" id="rc"></span>
</div>
<table><thead><tr><th>日期</th><th>币种</th><th>方向</th><th>趋势</th><th>SRSI</th><th>入场价</th><th>离场价</th><th>盈亏%</th><th>最大亏损</th><th>最大盈利</th><th>结果</th></tr></thead><tbody id="tb"></tbody></table>
<script>
var D={data_json};
var PATHS=null;
var curIdx=null,pc=null,sc=null;
fetch("paths_data.json").then(function(r){{return r.json()}}).then(function(d){{PATHS=d;R()}});
</script>
<script>
(function(){{
var cd={daily_json},cs={coins_json};
new Chart(c0,{{type:"line",data:{{labels:cd.map(function(x){{return x.d}}),datasets:[{{data:cd.map(function(x){{return x.c}}),borderColor:"#0d6efd",backgroundColor:"rgba(13,110,253,.1)",fill:true,tension:.3,pointRadius:0}}]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}}}},scales:{{x:{{ticks:{{maxTicksLimit:15,color:"#6c757d"}}}},y:{{ticks:{{color:"#6c757d",callback:function(v){{return v+"U"}}}}}}}}}}}});
cs.sort(function(a,b){{return b.p-a.p}});
new Chart(c1,{{type:"bar",data:{{labels:cs.map(function(c){{return c.n}}),datasets:[{{data:cs.map(function(c){{return c.p}}),backgroundColor:cs.map(function(c){{return c.p>0?"rgba(25,135,84,.7)":"rgba(220,53,69,.7)"}}),borderColor:cs.map(function(c){{return c.p>0?"#198754":"#dc3545"}}),borderWidth:1,borderRadius:3}}]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}}}},scales:{{x:{{ticks:{{color:"#6c757d"}}}},y:{{ticks:{{color:"#6c757d",callback:function(v){{return v+"U"}}}}}}}}}}}});
var md=D.map(function(t){{return{{x:t.mae_pct||0,y:t.mfe_pct||0,c:t.coin}}}});
new Chart(c2,{{type:"scatter",data:{{datasets:[{{data:md,backgroundColor:md.map(function(d){{return d.y>0?"rgba(25,135,84,.5)":"rgba(220,53,69,.5)"}}),pointRadius:5}}]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{label:function(c){{return c.raw.c+" MAE:"+c.raw.x+"% MFE:"+c.raw.y+"%"}}}}}}}},scales:{{x:{{title:{{display:true,text:"最大亏损%",color:"#6c757d"}},ticks:{{color:"#6c757d",callback:function(v){{return v+"%"}}}}}},y:{{title:{{display:true,text:"最大盈利%",color:"#6c757d"}},ticks:{{color:"#6c757d",callback:function(v){{return v+"%"}}}}}}}}}}}});
new Chart(c3,{{type:"bar",data:{{labels:cd.map(function(x){{return x.d}}),datasets:[{{data:cd.map(function(x){{return x.p}}),backgroundColor:cd.map(function(x){{return x.p>0?"rgba(25,135,84,.6)":"rgba(220,53,69,.6)"}}),borderWidth:1,borderRadius:3}}]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}}}},scales:{{x:{{ticks:{{maxTicksLimit:12,color:"#6c757d"}}}},y:{{ticks:{{color:"#6c757d",callback:function(v){{return v+"U"}}}}}}}}}}}});
}})();
</script>
<script>
function R(){{
if(!D||!PATHS)return;
var q=document.getElementById("sq").value.toLowerCase();
var d=document.getElementById("fd").value,r=document.getElementById("fr").value;
var df=document.getElementById("df").value,dt2=document.getElementById("dt").value;
var f=[];
for(var i=D.length-1;i>=0;i--){{
var t=D[i];
if(df&&t.entry_time<df+" 00:00")continue;if(dt2&&t.entry_time>dt2+" 23:59")continue;
if(q&&t.coin.toLowerCase().indexOf(q)<0)continue;
if(d!=="all"&&t.direction!==d)continue;
if(r==="win"&&t.pnl_usdt<=0)continue;if(r==="lose"&&t.pnl_usdt>=0)continue;
f.push({{trade:t,idx:i}});
}}
document.getElementById("rc").textContent=f.length+"/"+D.length+"笔";
var tb=document.getElementById("tb");tb.innerHTML="";
f.forEach(function(x){{var t=x.trade,oi=x.idx;
var row=document.createElement("tr");row.className="clickable";
row.onclick=function(idx){{return function(){{TD(idx,this)}}(oi);}}(oi);
appendCell(row,"td",t.entry_time.substr(0,16),null,"t");
appendCell(row,"td","<b>"+t.coin+"<\\/b>",null,"h");
appendCell(row,"td","<span class=badge "+(t.direction==="做多"?"badge-long":"badge-short")+">"+t.direction+"<\\/span>",null,"h");
appendCell(row,"td",t.trend_1h+"/"+t.trend_4h+"/"+t.trend_1d,null,"t");
appendCell(row,"td",t.srsi_1h+"/"+t.srsi_4h+"/"+t.srsi_1d,null,"t");
appendCell(row,"td",""+t.entry_price,null,"t");
appendCell(row,"td",""+t.exit_price,null,"t");
appendCell(row,"td",t.pnl_pct.toFixed(1)+"%",t.pnl_usdt>0?"green":"red","t");
appendCell(row,"td",(t.mae_pct||0).toFixed(1)+"%","red","t");
appendCell(row,"td",(t.mfe_pct||0).toFixed(1)+"%","green","t");
appendCell(row,"td","<span class=badge "+(t.pnl_usdt>0?"badge-win":"badge-lose")+">"+(t.pnl_usdt>0?"赢":"亏")+"<\\/span>",null,"h");
tb.appendChild(row);
var dr=document.createElement("tr");dr.className="detail-row";dr.id="dr-"+oi;
var dtc=document.createElement("td");dtc.colSpan=11;var dd=document.createElement("div");dd.id="dc-"+oi;
dtc.appendChild(dd);dr.appendChild(dtc);tb.appendChild(dr);
}});
}}
function appendCell(row,tag,val,cls,type){{
var c=document.createElement(tag);
if(type==="h")c.innerHTML=val;else c.textContent=val;
if(cls)c.className=cls;row.appendChild(c);
}}
R();
</script>
<script>
function TD(idx,row){{
if(!PATHS)return;
var dr=document.getElementById("dr-"+idx),vis=dr.classList.contains("show");
var all=document.querySelectorAll(".detail-row.show");for(var i=0;i<all.length;i++)all[i].classList.remove("show");
var al2=document.querySelectorAll("tr.expanded");for(var i=0;i<al2.length;i++)al2[i].classList.remove("expanded");
if(pc){{try{{pc.destroy()}}catch(e){{}}}}if(sc){{try{{sc.destroy()}}catch(e){{}}}}pc=null;sc=null;
if(vis){{curIdx=null;return}}
row.classList.add("expanded");dr.classList.add("show");curIdx=idx;
var t=D[idx],p=PATHS[idx],cd2=document.getElementById("dc-"+idx);cd2.innerHTML="";
if(!p||!p.b||!p.b.length){{var nd=document.createElement("div");nd.style.padding="20px";nd.textContent="无数据";cd2.appendChild(nd);return}}
var bars=p.b,sv=p.s||[],times=p.t||[],ex=p.ex;
var lbs=[];for(var i=0;i<times.length;i++)lbs.push(i%8===0?times[i]:"");
var hm=p.hm||0,hx=p.hx||0,pm=p.pm||0,px=p.px||0;
var d2=document.createElement("div");d2.className="detail-info";
d2.innerHTML="<span><b>持仓<\\/b> 最大亏损:<b class=red>"+hm+"%<\\/b> 最大盈利:<b class=green>"+hx+"%<\\/b><\\/span><span style=border-left:2px dashed #dc3545;padding-left:8px><b>离场后2天<\\/b> 最大亏损:<b class=red>"+pm+"%<\\/b> 最大盈利:<b class=green>"+px+"%<\\/b><\\/span>";
cd2.appendChild(d2);
var pd=document.createElement("div");pd.className="price-chart";cd2.appendChild(pd);var pv=document.createElement("canvas");pd.appendChild(pv);
var hl=ex!=null?ex+1:bars.length,mi=Infinity,mx=-Infinity,hi=-1,hj=-1;
for(var i=0;i<hl&&i<bars.length;i++){{if(bars[i]<mi){{mi=bars[i];hi=i}}if(bars[i]>mx){{mx=bars[i];hj=i}}}}
var mkd=Array(bars.length).fill(null),mxd=Array(bars.length).fill(null);if(hi>=0)mkd[hi]=mi;if(hj>=0)mxd[hj]=mx;
var lp={{id:"ln",afterDraw:function(chart){{
var ctx=chart.ctx,x=chart.scales.x,y=chart.scales.y,y0=y.getPixelForValue(0);
ctx.save();ctx.beginPath();ctx.setLineDash([4,4]);ctx.strokeStyle="rgba(108,117,125,.3)";ctx.lineWidth=1;ctx.moveTo(x.left,y0);ctx.lineTo(x.right,y0);ctx.stroke();ctx.restore();
ctx.save();ctx.beginPath();ctx.setLineDash([6,3]);ctx.strokeStyle="rgba(25,135,84,.6)";ctx.lineWidth=2;var xe=x.getPixelForValue(0);ctx.moveTo(xe,y.top);ctx.lineTo(xe,y.bottom);ctx.stroke();ctx.fillStyle="rgba(25,135,84,.9)";ctx.font="bold 10px sans-serif";ctx.fillText("入场",xe+4,y.top+16);ctx.restore();
if(ex!=null){{ctx.save();var xe2=x.getPixelForValue(ex);ctx.fillStyle="rgba(200,200,200,.08)";ctx.fillRect(xe2,y.top,x.right-xe2,y.bottom-y.top);ctx.beginPath();ctx.setLineDash([6,4]);ctx.strokeStyle="#dc3545";ctx.lineWidth=2.5;ctx.moveTo(xe2,y.top);ctx.lineTo(xe2,y.bottom);ctx.stroke();ctx.fillStyle="#dc3545";ctx.font="bold 10px sans-serif";ctx.fillText("离场",xe2+4,y.top+16);ctx.restore();}}
}}}};
pc=new Chart(pv.getContext("2d"),{{type:"line",plugins:[lp],data:{{labels:lbs,datasets:[{{data:bars,borderColor:"#0d6efd",backgroundColor:"rgba(13,110,253,.08)",fill:true,tension:.2,pointRadius:0,borderWidth:2,label:"价格%"}},{{data:mkd,borderColor:"#dc3545",backgroundColor:"#dc3545",pointRadius:6,pointStyle:"rectRot",showLine:false,label:"最大亏损"}},{{data:mxd,borderColor:"#198754",backgroundColor:"#198754",pointRadius:6,pointStyle:"triangle",showLine:false,label:"最大盈利"}}]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:true,position:"top",labels:{{boxWidth:12,font:{{size:10}},usePointStyle:true}}}}}},scales:{{x:{{display:false,grid:{{display:false}}}},y:{{ticks:{{color:"#6c757d",callback:function(v){{return v+"%"}}}},title:{{display:true,text:"价格%",color:"#6c757d"}}}}}}}}}});
var sd=document.createElement("div");sd.className="srsi-chart";cd2.appendChild(sd);var sv2=document.createElement("canvas");sd.appendChild(sv2);
sc=new Chart(sv2.getContext("2d"),{{type:"line",data:{{labels:lbs,datasets:[{{data:sv,borderColor:"rgba(245,159,0,.7)",backgroundColor:"rgba(245,159,0,.1)",fill:true,tension:.1,pointRadius:0,borderWidth:1.5,label:"SRSI K"}}]}},options:{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:true,position:"top",labels:{{boxWidth:12,font:{{size:10}}}}}}}},scales:{{x:{{ticks:{{color:"#6c757d",maxTicksLimit:10,maxRotation:45}},grid:{{display:false}}}},y:{{min:0,max:100,ticks:{{color:"#6c757d",stepSize:25}},grid:{{color:"rgba(0,0,0,.05)"}}}}}}}}}});
}}
</script>
</body></html>'''

with open('results/index.html', 'w') as f:
    f.write(html)

# Verify script blocks only
script_start = html.find('<script>')
script_end = html.rfind('</script>')
script_content = html[script_start:script_end]
assert '</b>' not in script_content, 'FATAL: unescaped </b>'
assert '</span>' not in script_content, 'FATAL: unescaped </span>'
print(f'HTML: {len(html)} chars, PATHS: {len(paths_json)} bytes, SAFE')
