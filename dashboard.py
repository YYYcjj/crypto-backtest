"""
入场精度可视化仪表盘生成器 v2 — 热度图 + 最优推荐 + 评分矩阵
"""
import json
import os
from typing import List, Dict


def build_dashboard(json_path: str = "results/entry_analysis.json",
                    output_dir: str = "results"):
    with open(json_path, "r") as f:
        data = json.load(f)
    if not data:
        print("No data found")
        return

    summaries = []
    for item in data:
        s = {k: v for k, v in item.items() if k != "results"}
        s["sample_results"] = item.get("results", [])[:15]
        summaries.append(s)

    data_json_path = os.path.join(output_dir, "dashboard_data.json")
    with open(data_json_path, "w") as f:
        json.dump(summaries, f, ensure_ascii=False, default=str)
    print(f"📦 数据: {data_json_path} ({len(summaries)} 条)")

    symbols = sorted(set(s["symbol"] for s in summaries))
    sl_pcts = sorted(set(s["sl_pct"] for s in summaries))
    # Embed summary data (without sample_results) directly for reliability
    inline_summaries = [{k:v for k,v in s.items() if k != 'sample_results'} for s in summaries]
    inline_data = json.dumps(inline_summaries, ensure_ascii=False, default=str)
    # Escape any </script> in the data
    inline_data = inline_data.replace('</', '<\\/')

    output_path = os.path.join(output_dir, "dashboard.html")
    with open(output_path, "w") as f:
        html = _render_html(symbols, sl_pcts)
        html = html.replace('__DATA_PLACEHOLDER__', inline_data)
        f.write(html)

    print(f"✅ 仪表盘: {output_path}")
    return output_path


def _render_html(symbols, sl_pcts):
    # Coin groups
    mainstream = ['BTC-USDT', 'ETH-USDT', 'SOL-USDT']
    altcoins = [s for s in symbols if s not in mainstream]
    sym_label = {s: s.replace('-USDT','') for s in symbols}
    sym_grouped = mainstream if altcoins else symbols
    sym_alt = altcoins

    sym_chk_main = ''.join(f'<label class="chk" data-group="main"><input type="checkbox" value="{s}" checked onchange="refilter()"><span class="ticker">{sym_label[s]}</span></label>' for s in sym_grouped if s in symbols)
    sym_chk_alt = ''.join(f'<label class="chk" data-group="alt"><input type="checkbox" value="{s}" checked onchange="refilter()"><span class="ticker">{sym_label[s]}</span></label>' for s in sym_alt if s in symbols) if sym_alt else ''

    sl_chk = ''.join(f'<label class="chk"><input type="checkbox" value="{p}" checked onchange="refilter()"><span>{p*100:.1f}%</span></label>' for p in sl_pcts)
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>入场精度分析仪表盘 v2</title>
</head>
<style>
:root{{--bg:#080d16;--card:#0f1623;--border:#1a2436;--text:#dce5f0;--muted:#5e6d82;--accent:#4da8f7;--green:#2dd47c;--red:#f5475d;--yellow:#f5a623;--purple:#9b6dff;--orange:#ff7849}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;display:flex}}
.sidebar{{width:240px;background:var(--card);border-right:1px solid var(--border);padding:16px;position:sticky;top:0;height:100vh;overflow-y:auto;flex-shrink:0}}
.sidebar h3{{font-size:13px;color:var(--muted);margin:14px 0 6px;text-transform:uppercase;letter-spacing:1px}}
.sidebar h3:first-child{{margin-top:0}}
.chk{{display:flex;align-items:center;gap:6px;font-size:12px;padding:3px 0;cursor:pointer;color:var(--text);transition:.1s}}
.chk:hover{{color:var(--accent)}}
.chk input{{accent-color:var(--accent);width:14px;height:14px;cursor:pointer}}
.chk .ticker{{font-weight:600;letter-spacing:.5px}}
.chk-group{{margin-bottom:4px}}
.sidebar-hdr{{display:flex;align-items:center;gap:8px;margin-bottom:14px;padding-bottom:10px;border-bottom:1px solid var(--border)}}
.sidebar-hdr .s-logo{{font-size:16px}}
.sidebar-hdr span{{font-size:13px;font-weight:600}}
.s-count{{margin-left:auto;background:var(--accent);color:#080d16;font-size:10px!important;padding:2px 8px;border-radius:8px}}
.s-btn{{background:var(--bg);color:var(--muted);border:1px solid var(--border);border-radius:4px;padding:2px 8px;font-size:10px;cursor:pointer;transition:.15s}}
.s-btn:hover{{color:var(--accent);border-color:var(--accent)}}
.s-btn-xs{{margin-left:4px}}
.s-stat{{display:flex;align-items:center;gap:6px;font-size:11px;color:var(--muted);padding:2px 0}}
.s-dot{{display:inline-block;width:8px;height:8px;border-radius:50%;flex-shrink:0}}
.chk{{display:flex;align-items:center;gap:6px;font-size:12px;padding:3px 0;cursor:pointer;color:var(--text)}}
.chk input{{accent-color:var(--accent);width:14px;height:14px;cursor:pointer}}
.main{{flex:1;padding:16px 20px;overflow-y:auto}}
.header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:12px}}
.header h1{{font-size:20px;font-weight:700}}
.header .badge{{font-size:11px;background:var(--accent);color:#080d16;padding:3px 10px;border-radius:10px;font-weight:600}}
.tabs{{display:flex;gap:2px;margin-bottom:12px;flex-wrap:wrap}}
.tab{{padding:7px 14px;font-size:12px;cursor:pointer;border:1px solid var(--border);border-radius:6px 6px 0 0;background:var(--bg);color:var(--muted);transition:.15s}}
.tab:hover{{color:var(--text)}}
.tab.active{{background:var(--card);color:var(--accent);font-weight:600}}
.panel{{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:16px;margin-bottom:14px}}
.panel h3{{font-size:14px;margin-bottom:10px;color:var(--text);display:flex;align-items:center;gap:8px}}
.panel h3 .tag{{font-size:10px;padding:2px 8px;border-radius:4px;background:var(--accent);color:#080d16;font-weight:600}}
.chart-wrap{{position:relative;height:340px}}
.chart-wrap canvas{{width:100%!important}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin-bottom:14px}}
.card{{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:12px}}
.card .l{{font-size:11px;color:var(--muted);margin-bottom:2px}}
.card .v{{font-size:22px;font-weight:700}}
.card .s{{font-size:11px;color:var(--muted);margin-top:2px}}
.heatmap{{display:grid;gap:2px;font-size:12px;overflow-x:auto}}
.heatmap .hdr{{font-weight:600;text-align:center;padding:6px 10px;color:var(--muted)}}
.heatmap .cell{{text-align:center;padding:10px 12px;border-radius:4px;cursor:pointer;transition:.2s;font-weight:600}}
.heatmap .cell:hover{{transform:scale(1.05);z-index:2;box-shadow:0 0 12px rgba(0,0,0,.4)}}
.heatmap .rowlabel{{display:flex;align-items:center;padding:6px 10px;font-weight:600;white-space:nowrap}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{background:var(--bg);padding:8px 10px;text-align:left;border-bottom:2px solid var(--border);color:var(--muted);font-weight:600;cursor:pointer}}
th:hover{{color:var(--accent)}}
td{{padding:6px 10px;border-bottom:1px solid var(--border)}}
tr:hover{{background:rgba(77,168,247,.05)}}
.green{{color:var(--green)}}.red{{color:var(--red)}}.yellow{{color:var(--yellow)}}
.rec-badge{{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600}}
.rec-a{{background:rgba(45,212,124,.15);color:var(--green);border:1px solid rgba(45,212,124,.3)}}
.rec-b{{background:rgba(245,166,35,.15);color:var(--yellow);border:1px solid rgba(245,166,35,.3)}}
.rec-c{{background:rgba(245,71,93,.15);color:var(--red);border:1px solid rgba(245,71,93,.3)}}
.toolbar{{display:flex;gap:8px;margin-bottom:8px;align-items:center}}
.toolbar input{{background:var(--bg);border:1px solid var(--border);color:var(--text);padding:5px 10px;border-radius:5px;font-size:12px;outline:none;width:180px}}
.toolbar input:focus{{border-color:var(--accent)}}
.btn{{background:var(--accent);color:#080d16;border:none;padding:5px 12px;border-radius:5px;font-size:11px;cursor:pointer;font-weight:600}}
.btn.outline{{background:transparent;border:1px solid var(--border);color:var(--text)}}
.score-dot{{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:4px}}
</style>
</head>
<body>

<div class="sidebar">
    <div class="sidebar-hdr">
        <span class="s-logo">&#9776;</span>
        <span>筛选面板</span>
        <span class="s-count" id="totalItems">0</span>
    </div>
    <h3>&#128314; 品种
        <button class="s-btn s-btn-xs" onclick="toggleGroup('main',true)">全选</button>
        <button class="s-btn s-btn-xs" onclick="toggleGroup('main',false)">清空</button>
    </h3>
    <div class="chk-group" id="groupMain">
    {sym_chk_main}
    </div>
    <h3>&#127760; 山寨
        <button class="s-btn s-btn-xs" onclick="toggleGroup('alt',true)">全选</button>
        <button class="s-btn s-btn-xs" onclick="toggleGroup('alt',false)">清空</button>
    </h3>
    <div class="chk-group" id="groupAlt">
    {sym_chk_alt}
    </div>
    <h3>&#128207; 止损档位
        <button class="s-btn s-btn-xs" onclick="toggleGroup('sl',true)">全选</button>
        <button class="s-btn s-btn-xs" onclick="toggleGroup('sl',false)">清空</button>
    </h3>
    <div class="chk-group" id="groupSL">
    {sl_chk}
    </div>
    <h3>&#128260; 方向</h3>
    <label class="chk"><input type="checkbox" value="LONG" checked onchange="refilter()">做多</label>
    <label class="chk"><input type="checkbox" value="SHORT" checked onchange="refilter()">做空</label>
    <div style="margin-top:16px;border-top:1px solid var(--border);padding-top:12px;">
        <div class="s-stat"><span class="s-dot" style="background:var(--green)"></span>存活 ≥70%</div>
        <div class="s-stat"><span class="s-dot" style="background:var(--yellow)"></span>存活 45-70%</div>
        <div class="s-stat"><span class="s-dot" style="background:var(--red)"></span>存活 &lt;45%</div>
    </div>
    <div style="margin-top:14px">
        <button class="btn outline" onclick="exportCSV()" style="width:100%">&#128229; 导出 CSV</button>
    </div>
    <div style="margin-top:8px">
        <button class="btn outline" onclick="resetFilters()" style="width:100%">&#128260; 重置筛选</button>
    </div>
</div>

<div class="main">
    <div class="header">
        <h1>📊 入场精度分析 <span class="badge">v2</span></h1>
    </div>

    <div class="tabs">
        <div class="tab active" onclick="switchTab('heatmap')">🔥 热度图</div>
        <div class="tab" onclick="switchTab('picks')">⭐ 最优推荐</div>
        <div class="tab" onclick="switchTab('curve')">📈 存活曲线</div>
        <div class="tab" onclick="switchTab('distribution')">📊 盈利分布</div>
        <div class="tab" onclick="switchTab('triggers')">🎯 触发对比</div>
        <div class="tab" onclick="switchTab('stoptime')">⏱ 止损时机</div>
        <div class="tab" onclick="switchTab('data')">📋 明细</div>
    </div>

    <div class="cards" id="summaryCards"></div>

    <div id="tab-heatmap" class="panel"><h3>🔥 存活率热度图 <span class="tag">核心</span></h3><div id="heatmapContainer"></div></div>
    <div id="tab-picks" class="panel" style="display:none"><h3>⭐ 各品种最优止损推荐</h3><div style="overflow-x:auto"><table id="picksTable"><thead><tr><th>品种</th><th>推荐止损</th><th>存活率</th><th>均盈</th><th>综合评分</th><th>等级</th><th>建议仓位</th></tr></thead><tbody></tbody></table></div></div>
    <div id="tab-curve" class="panel" style="display:none"><h3>📈 存活率 vs 止损宽度</h3><div class="chart-wrap"><canvas id="chartCurve"></canvas></div></div>
    <div id="tab-distribution" class="panel" style="display:none"><h3>📊 盈利区间分布</h3><div class="chart-wrap"><canvas id="chartDist"></canvas></div></div>
    <div id="tab-triggers" class="panel" style="display:none"><h3>🎯 触发类型对比</h3><div style="display:grid;grid-template-columns:1fr 1fr;gap:14px"><div class="chart-wrap"><canvas id="chartTrigStop"></canvas></div><div class="chart-wrap"><canvas id="chartTrigProfit"></canvas></div></div></div>
    <div id="tab-stoptime" class="panel" style="display:none"><h3>⏱ 止损发生时间分布</h3><div class="chart-wrap"><canvas id="chartStopTime"></canvas></div></div>
    <div id="tab-data" class="panel" style="display:none">
        <h3>📋 信号明细</h3>
        <div class="toolbar"><input type="text" id="tblSearch" placeholder="搜索..." oninput="renderTable()"><span style="font-size:11px;color:var(--muted);margin-left:auto" id="tblInfo"></span></div>
        <div style="max-height:450px;overflow:auto"><table id="dataTable"><thead><tr><th onclick="sortTable('symbol')">品种↕</th><th onclick="sortTable('sl_pct')">止损↕</th><th onclick="sortTable('trigger')">触发↕</th><th>1H</th><th>4H</th><th>1D</th><th>SRSI K</th><th onclick="sortTable('stopped')">结果↕</th><th onclick="sortTable('profit')">浮盈↕</th></tr></thead><tbody></tbody></table></div>
    </div>
</div>

<script>
var D=__DATA_PLACEHOLDER__;
var C=['#4da8f7','#2dd47c','#f5a623','#f5475d','#9b6dff','#ff7849','#e040fb','#00e5ff'];

// Init with embedded data, then try to refresh from JSON
D=D;refilter();
fetch('dashboard_data.json').then(r=>r.json()).then(d=>{{if(d&&d.length)D=d;refilter();}}).catch(()=>{{}});

function getFiltered(){{
    var chkS=[...document.querySelectorAll('.sidebar input[value]:checked')];
    var syms=new Set(),sls=new Set(),dirs=new Set();
    chkS.forEach(cb=>{{
        var v=cb.value;
        if(v.includes('-'))syms.add(v);
        else if(!isNaN(parseFloat(v)))sls.add(parseFloat(v));
        else dirs.add(v);
    }});
    return D.filter(d=>syms.has(d.symbol)&&sls.has(d.sl_pct)&&dirs.has(d.direction||'LONG'));
}}

function refilter(){{updateCards();redraw();if(curTab==='data')renderTable();if(curTab==='heatmap')drawHeatmap();if(curTab==='picks')drawPicks();
    // Update total count
    var f=getFiltered();
    document.getElementById('totalItems').textContent=f.length;
}}

function toggleGroup(grp,on){{
    var sel=grp==='main'?'#groupMain':grp==='alt'?'#groupAlt':'#groupSL';
    document.querySelectorAll(sel+' input').forEach(cb=>{{cb.checked=on;}});
    refilter();
}}

function resetFilters(){{
    document.querySelectorAll('.sidebar input[type=checkbox]').forEach(cb=>cb.checked=true);
    refilter();
}}

function filterCell(sym,sl){{
    // Uncheck all, then check only this sym+sl
    document.querySelectorAll('.sidebar input[type=checkbox]').forEach(cb=>cb.checked=false);
    document.querySelectorAll('.sidebar input[value="'+sym+'"]').forEach(cb=>cb.checked=true);
    document.querySelectorAll('.sidebar input[value="'+sl+'"]').forEach(cb=>cb.checked=true);
    document.querySelector('.sidebar input[value="LONG"]').checked=true;
    document.querySelector('.sidebar input[value="SHORT"]').checked=true;
    refilter();
    switchTab('picks');
}}

function updateCards(){{
    var f=getFiltered(),el=document.getElementById('summaryCards');
    if(!f.length){{el.innerHTML='<div class="panel empty">无匹配数据</div>';return;}}
    var total=0,stopped=0,wtProfit=0,surv=0,bestSym='',bestSc=0,avgSL=0;
    f.forEach(x=>{{total+=x.total_signals;stopped+=x.stopped;surv+=x.survived;wtProfit+=x.avg_max_profit*x.survived;avgSL+=x.sl_pct;}});
    var rate=surv/total*100,avgP=surv>0?wtProfit/surv:0;
    // Composite score for best pick
    f.forEach(x=>{{var sc=x.survive_rate*x.avg_max_profit/100;if(sc>bestSc){{bestSc=sc;bestSym=x.symbol+' '+x.sl_pct.toFixed(3)*100;}}}});
    el.innerHTML='<div class="card"><div class="l">总信号</div><div class="v" style="color:var(--accent)">'+total.toLocaleString()+'</div><div class="s">'+f.length+' 组数据</div></div>'+
        '<div class="card"><div class="l">存活率</div><div class="v" style="color:'+(rate>=70?'var(--green)':rate>=45?'var(--yellow)':'var(--red)')+'">'+rate.toFixed(1)+'%</div><div class="s">'+surv+'/'+total+'</div></div>'+
        '<div class="card"><div class="l">均盈</div><div class="v" style="color:'+(avgP>=2?'var(--green)':avgP>=1?'var(--yellow)':'var(--muted)')+'">'+avgP.toFixed(2)+'%</div><div class="s">最佳组合: '+bestSym+'</div></div>'+
        '<div class="card"><div class="l">止损扫出</div><div class="v" style="color:var(--red)">'+stopped.toLocaleString()+'</div><div class="s">'+(stopped/total*100).toFixed(1)+'% 被扫</div></div>';
}}

// ── HEATMAP ──
function drawHeatmap(){{
    var f=getFiltered(),el=document.getElementById('heatmapContainer');
    if(!f.length){{el.innerHTML='<div class="empty">无数据</div>';return;}}
    var syms=[...new Set(f.map(d=>d.symbol))].sort();
    var sls=[...new Set(f.map(d=>d.sl_pct))].sort((a,b)=>a-b);
    // Build matrix
    var matrix={{}};
    f.forEach(d=>{{if(!matrix[d.symbol])matrix[d.symbol]={{}};matrix[d.symbol][d.sl_pct]=d;}});
    var cols=sls.length+1;
    var html='<div class="heatmap" style="grid-template-columns:100px repeat('+sls.length+',1fr)">';
    html+='<div class="hdr">品种</div>';
    sls.forEach(s=>html+='<div class="hdr">'+(s*100).toFixed(1)+'%</div>');
    syms.forEach(sym=>{{
        html+='<div class="rowlabel">'+sym+'</div>';
        sls.forEach(sl=>{{
            var d=matrix[sym]?matrix[sym][sl]:null;
            if(!d){{html+='<div class="cell" style="background:var(--bg);color:var(--muted)">-</div>';return;}}
            var r=d.survive_rate;
            // Color: red(0) -> yellow(50) -> green(100)
            var h=(r/100)*120; // hue: 0=red, 60=yellow, 120=green
            var bg='hsl('+h.toFixed(0)+',70%,25%)';
            html+='<div class="cell" style="background:'+bg+'" title="'+sym+' '+sl*100+'% | 存活:'+r.toFixed(1)+'% | 均盈:'+d.avg_max_profit.toFixed(2)+'% | '+d.total_signals+'信号" onclick="filterCell(\''+sym+'\','+sl+')">'+r.toFixed(0)+'%</div>';
        }});
    }});
    html+='</div>';
    el.innerHTML=html;
}}

// ── OPTIMAL PICKS ──
function drawPicks(){{
    var f=getFiltered(),tb=document.querySelector('#picksTable tbody');
    tb.innerHTML='';
    var bySym={{}};
    f.forEach(d=>{{if(!bySym[d.symbol])bySym[d.symbol]=[];bySym[d.symbol].push(d);}});
    var rows=[];
    Object.entries(bySym).forEach(([sym,arr])=>{{
        arr.forEach(d=>{{
            // Composite: survival_rate% * avg_profit% / 100 = risk-adjusted return expectation
            var score=d.survive_rate*d.avg_max_profit/100;
            var grade=score>=1.5?'A':score>=0.8?'B':'C';
            var cls=grade==='A'?'rec-a':grade==='B'?'rec-b':'rec-c';
            var posPct=grade==='A'?'80-95%':grade==='B'?'50-70%':'<40%';
            rows.push({{sym:sym,sl:d.sl_pct,survive:d.survive_rate,profit:d.avg_max_profit,score:score,grade:grade,cls:cls,posPct:posPct}});
        }});
    }});
    rows.sort((a,b)=>b.score-a.score);
    rows.forEach(r=>tb.innerHTML+='<tr><td><strong>'+r.sym+'</strong></td><td>'+(r.sl*100).toFixed(1)+'%</td><td class="'+(r.survive>=70?'green':r.survive>=45?'yellow':'red')+'">'+r.survive.toFixed(1)+'%</td><td class="'+(r.profit>=2?'green':'')+'">'+r.profit.toFixed(2)+'%</td><td>'+r.score.toFixed(2)+'</td><td><span class="rec-badge '+r.cls+'">'+r.grade+'</span></td><td>'+r.posPct+'</td></tr>');
}}

// ── CHARTS ──
function destroyCharts(){{for(var k in charts)charts[k].destroy();charts={{}};}}

function mkChart(id,type,data,opt){{
    var ctx=document.getElementById(id).getContext('2d');
    charts[id]=new Chart(ctx,{{type:type,data:data,options:opt}});
}}

function redraw(){{
    destroyCharts();
    switch(curTab){{
        case'curve':drawCurve();break;
        case'distribution':drawDist();break;
        case'triggers':drawTrigStop();drawTrigProfit();break;
        case'stoptime':drawStopT();break;
    }}
}}

function drawCurve(){{
    var f=getFiltered();if(!f.length)return;
    var groups={{}};
    f.forEach(d=>{{var k=d.symbol+' '+d.direction;if(!groups[k])groups[k]={{}};groups[k][d.sl_pct]=d.survive_rate;}});
    var slVals=[...new Set(f.map(d=>d.sl_pct))].sort((a,b)=>a-b);
    mkChart('chartCurve','line',{{
        labels:slVals.map(s=>(s*100).toFixed(1)+'%'),
        datasets:Object.entries(groups).map(([k,v],i)=>({{label:k,data:slVals.map(s=>v[s]||null),borderColor:C[i%8],backgroundColor:'transparent',borderWidth:2.5,pointRadius:5,tension:.3}}))
    }},{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{labels:{{color:'#5e6d82',usePointStyle:true}}}},tooltip:{{backgroundColor:'#0f1623',callbacks:{{label:c=>c.dataset.label+': '+c.parsed.y.toFixed(1)+'%'}}}}}},scales:{{x:{{ticks:{{color:'#5e6d82'}},title:{{display:true,text:'止损宽度',color:'#5e6d82'}}}},y:{{min:0,max:100,ticks:{{color:'#5e6d82',callback:v=>v+'%'}},title:{{display:true,text:'存活率',color:'#5e6d82'}}}}}}}});
}}

function drawDist(){{
    var f=getFiltered();if(!f.length)return;
    var bks=['<0%','0-2%','2-5%','5-10%','>10%'];
    mkChart('chartDist','bar',{{
        labels:bks,
        datasets:f.map((d,i)=>({{label:d.symbol+'('+(d.sl_pct*100).toFixed(1)+'%)',data:bks.map(b=>d.profit_buckets[b]||0),backgroundColor:C[i%8]+'88',borderColor:C[i%8],borderWidth:1,borderRadius:4}}))
    }},{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{labels:{{color:'#5e6d82',usePointStyle:true}}}}}},scales:{{x:{{ticks:{{color:'#5e6d82'}}}},y:{{ticks:{{color:'#5e6d82'}},title:{{display:true,text:'交易数',color:'#5e6d82'}}}}}}}});
}}

function drawTrigStop(){{
    var f=getFiltered(),n={{dmi_flip:'DMI翻多',srsi_bounce:'超卖反弹',support_touch:'支撑触碰'}};
    if(!f.length||!f[0].trigger_stats)return;
    var tk=Object.keys(f[0].trigger_stats);
    mkChart('chartTrigStop','bar',{{labels:tk.map(t=>n[t]||t),datasets:f.map((d,i)=>({{label:d.symbol+'('+(d.sl_pct*100).toFixed(1)+'%)',data:tk.map(t=>d.trigger_stats[t]?d.trigger_stats[t].stop_rate:0),backgroundColor:C[i%8]+'88',borderColor:C[i%8],borderWidth:1,borderRadius:4}}))}},{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{labels:{{color:'#5e6d82',usePointStyle:true}}}},title:{{display:true,text:'止损率 %',color:'var(--text)',font:{{size:13}}}}}},scales:{{x:{{ticks:{{color:'#5e6d82'}}}},y:{{ticks:{{color:'#5e6d82',callback:v=>v+'%'}},min:0,max:100}}}}}});
}}

function drawTrigProfit(){{
    var f=getFiltered(),n={{dmi_flip:'DMI翻多',srsi_bounce:'超卖反弹',support_touch:'支撑触碰'}};
    if(!f.length||!f[0].trigger_stats)return;
    var tk=Object.keys(f[0].trigger_stats);
    mkChart('chartTrigProfit','bar',{{labels:tk.map(t=>n[t]||t),datasets:f.map((d,i)=>({{label:d.symbol+'('+(d.sl_pct*100).toFixed(1)+'%)',data:tk.map(t=>d.trigger_stats[t]?d.trigger_stats[t].avg_profit:0),backgroundColor:C[(i+4)%8]+'88',borderColor:C[(i+4)%8],borderWidth:1,borderRadius:4}}))}},{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{labels:{{color:'#5e6d82',usePointStyle:true}}}},title:{{display:true,text:'均盈 %',color:'var(--text)',font:{{size:13}}}}}},scales:{{x:{{ticks:{{color:'#5e6d82'}}}},y:{{ticks:{{color:'#5e6d82',callback:v=>v+'%'}}}}}}}});
}}

function drawStopT(){{
    var f=getFiltered(),m={{}};if(!f.length)return;
    f.forEach(d=>Object.entries(d.stop_bar_dist||{{}}).forEach(e=>m[e[0]]=(m[e[0]]||0)+e[1]));
    var s=Object.entries(m).sort((a,b)=>(parseInt(a[0].replace(/[^0-9]/g,''))||999)-(parseInt(b[0].replace(/[^0-9]/g,''))||999));
    mkChart('chartStopTime','bar',{{labels:s.map(e=>e[0]),datasets:[{{label:'次数',data:s.map(e=>e[1]),backgroundColor:s.map((_,i)=>i<s.length-1?'rgba(245,71,93,.5)':'rgba(245,166,35,.7)'),borderColor:s.map((_,i)=>i<s.length-1?'#f5475d':'#f5a623'),borderWidth:1,borderRadius:4}}]}},{{responsive:true,maintainAspectRatio:false,plugins:{{legend:{{display:false}}}},scales:{{x:{{ticks:{{color:'#5e6d82'}},title:{{display:true,text:'入场后第N根K线',color:'#5e6d82'}}}},y:{{ticks:{{color:'#5e6d82'}},title:{{display:true,text:'次数',color:'#5e6d82'}}}}}}}});
}}

// ── TAB ──
function switchTab(t){{
    document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
    event.target.classList.add('active');curTab=t;
    ['heatmap','picks','curve','distribution','triggers','stoptime','data'].forEach(t=>{{var e=document.getElementById('tab-'+t);if(e)e.style.display=t===curTab?'':'none';}});
    destroyCharts();
    if(curTab==='heatmap')drawHeatmap();
    else if(curTab==='picks')drawPicks();
    else if(curTab==='curve')drawCurve();
    else if(curTab==='distribution')drawDist();
    else if(curTab==='triggers'){{drawTrigStop();drawTrigProfit();}}
    else if(curTab==='stoptime')drawStopT();
    else if(curTab==='data')renderTable();
}}

// ── TABLE ──
function buildRows(){{
    var f=getFiltered(),rows=[],n={{dmi_flip:'DMI翻多',srsi_bounce:'超卖反弹',support_touch:'支撑触碰'}};
    f.forEach(d=>(d.sample_results||[]).forEach(r=>rows.push({{symbol:d.symbol,sl_pct:d.sl_pct,trigger:n[r.trigger]||r.trigger,trend1h:r.trend_1h||'-',trend4h:r.trend_4h||'-',trend1d:r.trend_1d||'-',srsi:(r.srs_k||0).toFixed(1),stopped:r.stopped,profit:r.max_profit||0}})));
    return rows;
}}

function sortTable(k){{if(sortK===k)sortAsc=!sortAsc;else{{sortK=k;sortAsc=true;}}renderTable();}}

function renderTable(){{
    var rows=buildRows(),s=document.getElementById('tblSearch').value.toLowerCase();
    if(s)rows=rows.filter(r=>JSON.stringify(r).toLowerCase().indexOf(s)>=0);
    if(sortK)rows.sort((a,b)=>{{var va=a[sortK],vb=b[sortK];if(typeof va==='string')va=va.toLowerCase();if(typeof vb==='string')vb=vb.toLowerCase();return va<vb?(sortAsc?-1:1):va>vb?(sortAsc?1:-1):0;}});
    var tb=document.querySelector('#dataTable tbody');tb.innerHTML='';
    var lim=Math.min(rows.length,300);
    for(var i=0;i<lim;i++){{var r=rows[i];tb.innerHTML+='<tr><td>'+r.symbol+'</td><td>'+(r.sl_pct*100).toFixed(1)+'%</td><td>'+r.trigger+'</td><td>'+r.trend1h+'</td><td>'+r.trend4h+'</td><td>'+r.trend1d+'</td><td>'+r.srsi+'</td><td class="'+(r.stopped?'red':'green')+'">'+(r.stopped?'✗止损':'✓存活')+'</td><td class="'+(r.profit>=2?'green':r.profit>=0?'':'red')+'">'+r.profit.toFixed(2)+'%</td></tr>';}}
    document.getElementById('tblInfo').textContent='显示 '+lim+'/'+rows.length+' 条';
}}

function exportCSV(){{
    var rows=buildRows(),csv='品种,止损%,触发,1H,4H,1D,SRSI_K,结果,最大浮盈%\\n';
    rows.forEach(r=>csv+=[r.symbol,(r.sl_pct*100).toFixed(1),r.trigger,r.trend1h,r.trend4h,r.trend1d,r.srsi,r.stopped?'止损':'存活',r.profit.toFixed(2)].join(',')+'\\n');
    var b=new Blob(['\\uFEFF'+csv],{{type:'text/csv;charset=utf-8;'}}),a=document.createElement('a');
    a.href=URL.createObjectURL(b);a.download='entry_analysis.csv';a.click();
}}
</script>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js">
</script>
</body>
</html>"""


if __name__ == "__main__":
    build_dashboard()
