"""
入场精度可视化仪表盘生成器 — 数据与HTML分离版
"""
import json
import os
from typing import List, Dict


def build_dashboard(json_path: str = "results/entry_analysis.json",
                    output_dir: str = "results"):
    """生成交互式可视化仪表盘"""

    with open(json_path, "r") as f:
        data = json.load(f)

    if not data:
        print("No data found")
        return

    # 提取摘要数据
    summaries = []
    for item in data:
        s = {k: v for k, v in item.items() if k != "results"}
        s["sample_results"] = item.get("results", [])[:20]
        summaries.append(s)

    # 保存瘦身数据
    data_json_path = os.path.join(output_dir, "dashboard_data.json")
    with open(data_json_path, "w") as f:
        json.dump(summaries, f, ensure_ascii=False, default=str)
    print(f"📦 数据已保存: {data_json_path} ({len(summaries)} 条)")

    # 收集元信息
    symbols = sorted(set(s["symbol"] for s in summaries))
    sl_pcts = sorted(set(s["sl_pct"] for s in summaries))

    # 生成纯HTML（数据从外部JSON加载）
    html = _render_html(symbols, sl_pcts)

    output_path = os.path.join(output_dir, "dashboard.html")
    with open(output_path, "w") as f:
        f.write(html)

    print(f"✅ 仪表盘已生成: {output_path}")
    return output_path


def _render_html(symbols: List[str], sl_pcts: List[float]) -> str:
    sl_options = ''.join(f'<option value="{p}">{p:.1f}%</option>' for p in sl_pcts)
    sym_options = ''.join(f'<option value="{s}">{s}</option>' for s in symbols)

    return """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>入场精度分析仪表盘</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
:root { --bg:#0b1120; --card:#111827; --border:#1e293b; --text:#e2e8f0; --muted:#64748b; --accent:#38bdf8; --green:#22c55e; --red:#ef4444; --yellow:#f59e0b; --purple:#a855f7; }
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', sans-serif; background:var(--bg); color:var(--text); min-height:100vh; }
.header { background:linear-gradient(135deg, #1e293b 0%, #0f172a 100%); border-bottom:1px solid var(--border); padding:16px 24px; position:sticky; top:0; z-index:100; display:flex; justify-content:space-between; align-items:center; }
.header h1 { font-size:18px; }
.header .sub { color:var(--muted); font-size:12px; }
.controls { display:flex; gap:12px; flex-wrap:wrap; padding:12px 24px; background:var(--card); border-bottom:1px solid var(--border); align-items:center; }
.control-group { display:flex; align-items:center; gap:6px; }
.control-group label { font-size:11px; color:var(--muted); white-space:nowrap; text-transform:uppercase; letter-spacing:.5px; }
select, .btn { background:#1e293b; color:var(--text); border:1px solid var(--border); padding:5px 10px; border-radius:5px; font-size:12px; cursor:pointer; outline:none; transition: border-color .2s; }
select:focus { border-color:var(--accent); }
.btn { font-size:11px; }
.btn:hover { background:#334155; }
.btn.export { background:var(--green); color:#0b1120; border-color:var(--green); font-weight:600; }
.metric-tabs { display:flex; gap:2px; padding:0 24px; margin:12px 0 8px; flex-wrap:wrap; }
.tab { padding:7px 14px; font-size:12px; cursor:pointer; border:1px solid var(--border); border-bottom:none; border-radius:6px 6px 0 0; background:#0f172a; color:var(--muted); transition:all .2s; }
.tab:hover { color:var(--text); }
.tab.active { background:var(--card); color:var(--accent); border-bottom-color:var(--card); }
.cards { display:grid; grid-template-columns:repeat(auto-fit, minmax(180px, 1fr)); gap:10px; padding:0 24px; margin-bottom:12px; }
.card { background:var(--card); border:1px solid var(--border); border-radius:8px; padding:14px; }
.card .label { font-size:11px; color:var(--muted); margin-bottom:2px; }
.card .value { font-size:26px; font-weight:700; }
.card .sub { font-size:11px; color:var(--muted); margin-top:2px; }
.main-content { padding:0 24px 24px; }
.chart-panel { background:var(--card); border:1px solid var(--border); border-radius:10px; padding:16px; margin-bottom:14px; }
.chart-panel h3 { font-size:14px; margin-bottom:10px; display:flex; align-items:center; gap:8px; }
.chart-wrap { position:relative; height:320px; }
.chart-wrap canvas { width:100% !important; }
.data-table { width:100%; border-collapse:collapse; font-size:12px; }
.data-table th { background:#0f172a; padding:8px 10px; text-align:left; border-bottom:2px solid var(--border); color:var(--muted); font-weight:600; position:sticky; top:0; cursor:pointer; user-select:none; }
.data-table th:hover { color:var(--accent); }
.data-table td { padding:6px 10px; border-bottom:1px solid var(--border); }
.data-table tr:hover { background:rgba(56,189,248,0.05); }
.pos { color:var(--green); }
.neg { color:var(--red); }
.grid-2 { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
@media (max-width:768px) { .grid-2 { grid-template-columns:1fr; } .controls { flex-direction:column; align-items:flex-start; } }
.empty { text-align:center; padding:40px; color:var(--muted); }
.toolbar { display:flex; gap:8px; margin-bottom:8px; align-items:center; }
.toolbar input { background:#1e293b; border:1px solid var(--border); color:var(--text); padding:5px 10px; border-radius:5px; font-size:12px; outline:none; width:200px; }
.toolbar input:focus { border-color:var(--accent); }
.page-info { font-size:11px; color:var(--muted); margin-left:auto; }
</style>
</head>
<body>

<div class="header">
    <div><h1>&#128202; 入场精度分析仪表盘</h1><p class="sub">15m 精确入场 &middot; 高位周期趋势确认 &middot; 多档位止损对比</p></div>
    <button class="btn export" onclick="exportCSV()">&#128229; 导出CSV</button>
</div>

<div class="controls">
    <div class="control-group">
        <label>止损</label>
        <select id="slSelect" onchange="filterData()">""" + sl_options + """</select>
    </div>
    <div class="control-group">
        <label>品种</label>
        <select id="symbolSelect" onchange="filterData()">
            <option value="all">全部</option>""" + sym_options + """</select>
    </div>
    <div class="control-group">
        <label>触发</label>
        <select id="triggerSelect" onchange="filterData()">
            <option value="all">全部</option>
            <option value="dmi_flip">DMI翻多</option>
            <option value="srsi_bounce">超卖反弹</option>
            <option value="support_touch">支撑触碰</option>
        </select>
    </div>
    <div class="control-group">
        <label>方向</label>
        <select id="dirSelect" onchange="filterData()">
            <option value="all">全部</option>
            <option value="LONG">做多</option>
            <option value="SHORT">做空</option>
        </select>
    </div>
</div>

<div class="metric-tabs">
    <div class="tab active" onclick="switchTab('survival')">存活率 &amp; 盈亏</div>
    <div class="tab" onclick="switchTab('curve')">存活率曲线</div>
    <div class="tab" onclick="switchTab('distribution')">盈利分布</div>
    <div class="tab" onclick="switchTab('triggers')">触发对比</div>
    <div class="tab" onclick="switchTab('stoptime')">止损时机</div>
    <div class="tab" onclick="switchTab('data')">明细</div>
</div>

<div class="cards" id="cardsRow"></div>

<div class="main-content">
    <div id="tab-survival" class="chart-panel">
        <h3>&#128200; 存活率 &amp; 均盈对比</h3>
        <div class="chart-wrap"><canvas id="chartSurvival"></canvas></div>
    </div>
    <div id="tab-curve" class="chart-panel" style="display:none">
        <h3>&#128201; 存活率 vs 止损宽度</h3>
        <div class="chart-wrap"><canvas id="chartCurve"></canvas></div>
    </div>
    <div id="tab-distribution" class="chart-panel" style="display:none">
        <h3>&#128202; 盈利区间分布</h3>
        <div class="chart-wrap"><canvas id="chartDistribution"></canvas></div>
    </div>
    <div id="tab-triggers" class="chart-panel" style="display:none">
        <h3>&#127919; 触发类型对比</h3>
        <div class="grid-2">
            <div class="chart-wrap"><canvas id="chartTriggerStop"></canvas></div>
            <div class="chart-wrap"><canvas id="chartTriggerProfit"></canvas></div>
        </div>
    </div>
    <div id="tab-stoptime" class="chart-panel" style="display:none">
        <h3>&#9201; 止损发生时间分布</h3>
        <div class="chart-wrap"><canvas id="chartStopTime"></canvas></div>
    </div>
    <div id="tab-data" class="chart-panel" style="display:none">
        <h3>&#128203; 信号明细</h3>
        <div class="toolbar">
            <input type="text" id="tableSearch" placeholder="搜索..." oninput="renderTable()">
            <span class="page-info" id="tableInfo"></span>
        </div>
        <div style="max-height:420px;overflow-y:auto;">
            <table class="data-table" id="dataTable">
                <thead><tr>
                    <th onclick="sortTable('symbol')">品种 &#8693;</th>
                    <th onclick="sortTable('price')">入场价 &#8693;</th>
                    <th onclick="sortTable('trigger')">触发 &#8693;</th>
                    <th onclick="sortTable('sl_pct')">止损 &#8693;</th>
                    <th>1H</th><th>4H</th><th>1D</th>
                    <th>SRSI K</th>
                    <th onclick="sortTable('stopped')">结果 &#8693;</th>
                    <th onclick="sortTable('profit')">最大浮盈 &#8693;</th>
                </tr></thead>
                <tbody></tbody>
            </table>
        </div>
    </div>
</div>

<script>
var ALL_DATA = [];
var currentTab = 'survival';
var charts = {};
var sortKey = '', sortAsc = true;
var tableRows = [];

fetch('dashboard_data.json').then(r=>r.json()).then(data=>{
    ALL_DATA = data;
    updateCards(); drawSurvivalChart();
}).catch(e=>{document.getElementById('cardsRow').innerHTML='<div class="empty" style="color:var(--red)">&#9888; 加载失败: '+e.message+'</div>';});

function getFilteredData(){
    var sl=parseFloat(document.getElementById('slSelect').value);
    var sym=document.getElementById('symbolSelect').value;
    var trig=document.getElementById('triggerSelect').value;
    var dir=document.getElementById('dirSelect').value;
    return ALL_DATA.filter(function(item){
        if(sl && item.sl_pct!==sl) return false;
        if(sym!=='all' && item.symbol!==sym) return false;
        if(dir!=='all' && item.direction!==dir) return false;
        return true;
    });
}

function filterData(){ updateCards(); refreshCharts(); if(currentTab==='data') renderTable(); }

function updateCards(){
    var f=getFilteredData(), row=document.getElementById('cardsRow');
    if(!f.length){ row.innerHTML='<div class="empty">无匹配数据</div>'; return; }
    var s=0, st=0, wp=0, sv=0, best='', bs=0, avgSL=0;
    f.forEach(function(x){
        s+=x.total_signals; st+=x.stopped; sv+=x.survived;
        wp+=x.avg_max_profit*x.survived; avgSL+=x.sl_pct;
        if(x.survive_rate>bs){ bs=x.survive_rate; best=x.symbol; }
    });
    var os=sv/s*100, ap=sv>0?wp/sv:0;
    var sc=os>=70?'var(--green)':(os>=50?'var(--yellow)':'var(--red)');
    var pc=ap>=2?'var(--green)':(ap>=1?'var(--yellow)':'var(--muted)');
    row.innerHTML='<div class="card"><div class="label">总信号</div><div class="value" style="color:var(--accent)">'+s.toLocaleString()+'</div><div class="sub">'+f.length+'组数据</div></div>'+
        '<div class="card"><div class="label">存活率</div><div class="value" style="color:'+sc+'">'+os.toFixed(1)+'%</div><div class="sub">'+sv+'/'+s+' 未止损</div></div>'+
        '<div class="card"><div class="label">均盈</div><div class="value" style="color:'+pc+'">'+ap.toFixed(2)+'%</div><div class="sub">最佳:'+best+'('+bs.toFixed(0)+'%)</div></div>'+
        '<div class="card"><div class="label">止损扫出</div><div class="value" style="color:var(--red)">'+st.toLocaleString()+'</div><div class="sub">'+(st/s*100).toFixed(1)+'%</div></div>';
}

function destroyCharts(){ for(var k in charts){ charts[k].destroy(); } charts={}; }

function refreshCharts(){
    destroyCharts();
    switch(currentTab){
        case'survival': drawSurvivalChart(); break;
        case'curve': drawCurveChart(); break;
        case'distribution': drawDistributionChart(); break;
        case'triggers': drawTriggerStopChart(); drawTriggerProfitChart(); break;
        case'stoptime': drawStopTimeChart(); break;
    }
}

function mkChart(id,type,data,opt){
    var ctx=document.getElementById(id).getContext('2d');
    charts[id]=new Chart(ctx,{type:type,data:data,options:opt});
}

var C=['#38bdf8','#22c55e','#f59e0b','#ef4444','#a855f7','#ec4899'];

function drawSurvivalChart(){
    var d=getFilteredData(); if(!d.length) return;
    d.sort(function(a,b){ return a.sl_pct-b.sl_pct||a.symbol.localeCompare(b.symbol); });
    mkChart('chartSurvival','bar',{
        labels:d.map(function(x){return x.symbol+' ('+x.direction+') '+x.sl_pct.toFixed(1)+'%';}),
        datasets:[
            {label:'存活率 %',data:d.map(function(x){return x.survive_rate;}), yAxisID:'y',
             backgroundColor:d.map(function(x){return x.survive_rate>=70?'rgba(34,197,94,.6)':(x.survive_rate>=50?'rgba(245,158,11,.6)':'rgba(239,68,68,.6)');}),
             borderColor:d.map(function(x){return x.survive_rate>=70?'#22c55e':(x.survive_rate>=50?'#f59e0b':'#ef4444');}),
             borderWidth:2,borderRadius:6},
            {label:'均盈 %',data:d.map(function(x){return x.avg_max_profit;}), type:'line', yAxisID:'y1',
             borderColor:'#38bdf8',backgroundColor:'rgba(56,189,248,.1)',borderWidth:2,pointRadius:4,pointBackgroundColor:'#38bdf8',tension:.3}
        ]
    },{responsive:true,maintainAspectRatio:false,
       plugins:{legend:{labels:{color:'#94a3b8',usePointStyle:true}},tooltip:{backgroundColor:'#1e293b'}},
       scales:{
           x:{ticks:{color:'#64748b',maxRotation:60,font:{size:10}}},
           y:{type:'linear',position:'left',min:0,max:100,ticks:{color:'#64748b',callback:function(v){return v+'%';}},title:{display:true,text:'存活率',color:'#64748b'}},
           y1:{type:'linear',position:'right',min:0,ticks:{color:'#38bdf8',callback:function(v){return v+'%';}},title:{display:true,text:'均盈',color:'#38bdf8'},grid:{display:false}}
       }});
}

function drawCurveChart(){
    var f=getFilteredData(); if(!f.length) return;
    // Group by symbol+dir, x=SL, y=survive_rate
    var groups={};
    f.forEach(function(x){
        var key=x.symbol+' '+x.direction;
        if(!groups[key]) groups[key]={label:key,data:{},profits:{}};
        groups[key].data[x.sl_pct]=x.survive_rate;
        groups[key].profits[x.sl_pct]=x.avg_max_profit;
    });
    var slValues=[0.005,0.01,0.015,0.02];
    var datasets=[];
    Object.keys(groups).forEach(function(g,i){
        var grp=groups[g];
        datasets.push({
            label:grp.label,data:slValues.map(function(s){return grp.data[s]||null;}),
            borderColor:C[i%C.length],backgroundColor:'transparent',borderWidth:2,pointRadius:5,tension:.3,
        });
    });
    mkChart('chartCurve','line',{
        labels:slValues.map(function(v){return (v*100).toFixed(1)+'%';}),
        datasets:datasets
    },{responsive:true,maintainAspectRatio:false,
       plugins:{legend:{labels:{color:'#94a3b8',usePointStyle:true}},tooltip:{backgroundColor:'#1e293b',callbacks:{label:function(ctx){return ctx.dataset.label+': '+ctx.parsed.y.toFixed(1)+'%存活';}}}},
       scales:{
           x:{ticks:{color:'#64748b'},title:{display:true,text:'止损宽度',color:'#64748b'}},
           y:{min:0,max:100,ticks:{color:'#64748b',callback:function(v){return v+'%';}},title:{display:true,text:'存活率',color:'#64748b'}}
       }});
}

function drawDistributionChart(){
    var d=getFilteredData(); if(!d.length) return;
    var buckets=['<0%','0-2%','2-5%','5-10%','>10%'];
    mkChart('chartDistribution','bar',{
        labels:buckets,
        datasets:d.map(function(x,i){return{
            label:x.symbol+' ('+x.sl_pct.toFixed(1)+'%)',data:buckets.map(function(b){return x.profit_buckets[b]||0;}),
            backgroundColor:C[i%C.length]+'99',borderColor:C[i%C.length],borderWidth:1,borderRadius:4
        };})
    },{responsive:true,maintainAspectRatio:false,
       plugins:{legend:{labels:{color:'#94a3b8',usePointStyle:true}},tooltip:{backgroundColor:'#1e293b'}},
       scales:{x:{ticks:{color:'#64748b'}},y:{ticks:{color:'#64748b'},title:{display:true,text:'交易数',color:'#64748b'}}}});
}

function drawTriggerStopChart(){
    var d=getFilteredData(),names={dmi_flip:'DMI翻多',srsi_bounce:'超卖反弹',support_touch:'支撑触碰'};
    if(!d.length) return;
    var triggers=Object.keys(d[0].trigger_stats||{});
    if(!triggers.length) return;
    mkChart('chartTriggerStop','bar',{
        labels:triggers.map(function(t){return names[t]||t;}),
        datasets:d.map(function(x,i){return{
            label:x.symbol+'('+x.sl_pct.toFixed(1)+'%)',data:triggers.map(function(t){return x.trigger_stats[t]?x.trigger_stats[t].stop_rate:0;}),
            backgroundColor:C[i%C.length]+'99',borderColor:C[i%C.length],borderWidth:1,borderRadius:4
        };})
    },{responsive:true,maintainAspectRatio:false,
       plugins:{legend:{labels:{color:'#94a3b8',usePointStyle:true}},title:{display:true,text:'止损率 %',color:'#e2e8f0',font:{size:13}}},
       scales:{x:{ticks:{color:'#64748b'}},y:{ticks:{color:'#64748b',callback:function(v){return v+'%';}},min:0,max:100}}});
}

function drawTriggerProfitChart(){
    var d=getFilteredData(),names={dmi_flip:'DMI翻多',srsi_bounce:'超卖反弹',support_touch:'支撑触碰'};
    if(!d.length) return;
    var triggers=Object.keys(d[0].trigger_stats||{});
    if(!triggers.length) return;
    mkChart('chartTriggerProfit','bar',{
        labels:triggers.map(function(t){return names[t]||t;}),
        datasets:d.map(function(x,i){return{
            label:x.symbol+'('+x.sl_pct.toFixed(1)+'%)',data:triggers.map(function(t){return x.trigger_stats[t]?x.trigger_stats[t].avg_profit:0;}),
            backgroundColor:C[(i+3)%C.length]+'99',borderColor:C[(i+3)%C.length],borderWidth:1,borderRadius:4
        };})
    },{responsive:true,maintainAspectRatio:false,
       plugins:{legend:{labels:{color:'#94a3b8',usePointStyle:true}},title:{display:true,text:'均盈 %',color:'#e2e8f0',font:{size:13}}},
       scales:{x:{ticks:{color:'#64748b'}},y:{ticks:{color:'#64748b',callback:function(v){return v+'%';}}},}});
}

function drawStopTimeChart(){
    var d=getFilteredData(),merged={};
    if(!d.length) return;
    d.forEach(function(x){Object.entries(x.stop_bar_dist||{}).forEach(function(e){merged[e[0]]=(merged[e[0]]||0)+e[1];});});
    var sorted=Object.entries(merged).sort(function(a,b){var na=parseInt(a[0].replace(/[^0-9]/g,''))||999,nb=parseInt(b[0].replace(/[^0-9]/g,''))||999;return na-nb;});
    mkChart('chartStopTime','bar',{
        labels:sorted.map(function(s){return s[0];}),
        datasets:[{label:'止损次数',data:sorted.map(function(s){return s[1];}),
            backgroundColor:sorted.map(function(_,i){return i<sorted.length-1?'rgba(239,68,68,.5)':'rgba(245,158,11,.7)';}),
            borderColor:sorted.map(function(_,i){return i<sorted.length-1?'#ef4444':'#f59e0b';}),
            borderWidth:1,borderRadius:4}]
    },{responsive:true,maintainAspectRatio:false,
       plugins:{legend:{display:false},tooltip:{backgroundColor:'#1e293b'}},
       scales:{x:{ticks:{color:'#64748b'},title:{display:true,text:'入场后第N根K线',color:'#64748b'}},y:{ticks:{color:'#64748b'},title:{display:true,text:'次数',color:'#64748b'}}}});
}

function switchTab(tab){
    document.querySelectorAll('.tab').forEach(function(t){t.classList.remove('active');});
    event.target.classList.add('active'); currentTab=tab;
    ['survival','curve','distribution','triggers','stoptime','data'].forEach(function(t){
        var el=document.getElementById('tab-'+t); if(el) el.style.display=t===tab?'':'none';
    });
    destroyCharts();
    if(tab==='survival') drawSurvivalChart();
    else if(tab==='curve') drawCurveChart();
    else if(tab==='distribution') drawDistributionChart();
    else if(tab==='triggers'){drawTriggerStopChart();drawTriggerProfitChart();}
    else if(tab==='stoptime') drawStopTimeChart();
    else if(tab==='data') renderTable();
}

// -- Table with sort+search --
function buildTableRows(){
    var f=getFilteredData(), rows=[], names={dmi_flip:'DMI翻多',srsi_bounce:'超卖反弹',support_touch:'支撑触碰'};
    f.forEach(function(item){
        (item.sample_results||[]).forEach(function(r){
            rows.push({
                symbol:item.symbol, price:r.price||0, trigger:names[r.trigger]||r.trigger||'',
                sl_pct:item.sl_pct, dir:item.direction||'LONG', trend1h:r.trend_1h||'-', trend4h:r.trend_4h||'-',
                trend1d:r.trend_1d||'-', srsi:(r.srs_k||0).toFixed(1), stopped:r.stopped, profit:r.max_profit||0
            });
        });
    });
    return rows;
}

function sortTable(key){
    if(sortKey===key) sortAsc=!sortAsc; else{sortKey=key;sortAsc=true;}
    renderTable();
}

function renderTable(){
    var rows=buildTableRows(), search=document.getElementById('tableSearch').value.toLowerCase();
    if(search) rows=rows.filter(function(r){return JSON.stringify(r).toLowerCase().indexOf(search)>=0;});
    if(sortKey){
        rows.sort(function(a,b){
            var va=a[sortKey],vb=b[sortKey];
            if(typeof va==='string') va=va.toLowerCase();
            if(typeof vb==='string') vb=vb.toLowerCase();
            if(va<vb) return sortAsc?-1:1; if(va>vb) return sortAsc?1:-1; return 0;
        });
    }
    var tbody=document.querySelector('#dataTable tbody');
    tbody.innerHTML='';
    var limit=Math.min(rows.length,200);
    for(var i=0;i<limit;i++){
        var r=rows[i], sc=r.stopped?'neg':'pos', pc=r.profit>=2?'pos':(r.profit>=0?'':'neg');
        tbody.innerHTML+='<tr><td>'+r.symbol+'</td><td>'+r.price.toFixed(2)+'</td><td>'+r.trigger+'</td><td>'+(r.sl_pct*100).toFixed(1)+'%</td><td>'+r.trend1h+'</td><td>'+r.trend4h+'</td><td>'+r.trend1d+'</td><td>'+r.srsi+'</td><td class="'+sc+'">'+(r.stopped?'&#10007; 止损':'&#10003; 存活')+'</td><td class="'+pc+'">'+r.profit.toFixed(2)+'%</td></tr>';
    }
    document.getElementById('tableInfo').textContent='显示 '+limit+'/'+rows.length+' 条';
}

function exportCSV(){
    var rows=buildTableRows(), csv='品种,入场价,触发,止损%,方向,1H,4H,1D,SRSI_K,结果,最大浮盈%\\n';
    rows.forEach(function(r){
        csv+=[r.symbol,r.price.toFixed(2),r.trigger,(r.sl_pct*100).toFixed(1),r.dir,r.trend1h,r.trend4h,r.trend1d,r.srsi,r.stopped?'止损':'存活',r.profit.toFixed(2)].join(',')+'\\n';
    });
    var blob=new Blob(['\\uFEFF'+csv],{type:'text/csv;charset=utf-8;'});
    var a=document.createElement('a'); a.href=URL.createObjectURL(blob); a.download='entry_analysis.csv'; a.click();
}
</script>
</body>
</html>"""


if __name__ == "__main__":
    build_dashboard()
