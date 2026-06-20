"""
细节分析仪表盘生成器 — MAE分布 / 时段热力图 / 信号叠加 / 波动率影响
"""
import json
import os


def build_detail_dashboard(json_path: str = "results/detail_analysis.json",
                           output_path: str = "results/detail_dashboard.html"):
    if not os.path.exists(json_path):
        print(f"❌ 数据文件不存在: {json_path}")
        return

    with open(json_path) as f:
        data = json.load(f)

    if not data:
        print("No data")
        return

    # 瘦身：只保留摘要+前20条原始结果
    for d in data:
        d["_sample_results"] = d.pop("raw_results", [])[:30]

    data_json = json.dumps(data, ensure_ascii=False, default=str)
    data_json = data_json.replace("'", "\\'").replace("</", "<\\/")

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>交易细节分析 | Detail Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
:root{{--bg:#080d16;--card:#0f1623;--border:#1a2436;--text:#dce5f0;--muted:#5e6d82;--accent:#4da8f7;--green:#2dd47c;--red:#f5475d;--yellow:#f5a623;--purple:#9b6dff}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI','PingFang SC',sans-serif;background:var(--bg);color:var(--text);min-height:100vh}}
.header{{background:linear-gradient(135deg,#1e293b,#0f172a);border-bottom:1px solid var(--border);padding:16px 20px;display:flex;justify-content:space-between;align-items:center}}
.header h1{{font-size:18px}}
.header .badge{{font-size:11px;background:var(--accent);color:#080d16;padding:3px 10px;border-radius:10px;font-weight:600}}
.tabs{{display:flex;gap:4px;padding:0 20px;margin:12px 0 8px;flex-wrap:wrap}}
.tab{{padding:7px 14px;font-size:12px;cursor:pointer;border:1px solid var(--border);border-radius:6px;background:var(--bg);color:var(--muted);transition:.15s}}
.tab:hover{{color:var(--text)}}
.tab.active{{background:var(--card);color:var(--accent);font-weight:600;border-color:var(--accent)}}
.panel{{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:16px;margin:0 20px 14px}}
.panel h3{{font-size:14px;margin-bottom:10px}}
.chart-wrap{{position:relative;height:320px}}
.chart-wrap canvas{{width:100%!important}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}
.grid3{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px}}
@media(max-width:768px){{.grid2,.grid3{{grid-template-columns:1fr}}}}
table{{width:100%;border-collapse:collapse;font-size:12px}}
th{{background:var(--bg);padding:8px 10px;text-align:left;border-bottom:2px solid var(--border);color:var(--muted);font-weight:600}}
td{{padding:6px 10px;border-bottom:1px solid var(--border)}}
tr:hover{{background:rgba(77,168,247,.05)}}
.green{{color:var(--green)}}.red{{color:var(--red)}}.yellow{{color:var(--yellow)}}
select{{background:var(--bg);color:var(--text);border:1px solid var(--border);padding:5px 10px;border-radius:4px;font-size:12px;outline:none}}
select:focus{{border-color:var(--accent)}}
.heat-cell{{display:flex;align-items:center;justify-content:center;padding:6px;border-radius:4px;font-size:11px;font-weight:600}}
.key-finding{{background:var(--bg);border-left:3px solid var(--accent);padding:10px 14px;border-radius:0 6px 6px 0;font-size:13px;margin-bottom:10px;line-height:1.6}}
.key-finding strong{{color:var(--accent)}}
</style>
</head>
<body>
<div class="header">
    <h1>🔬 交易细节分析 <span class="badge">Detail</span></h1>
    <select id="symSelect" onchange="switchSymbol()" style="margin-left:auto"></select>
</div>

<div class="tabs">
    <div class="tab active" onclick="switchTab('mae')">📉 最大回撤 (MAE)</div>
    <div class="tab" onclick="switchTab('hour')">🕐 最佳时段</div>
    <div class="tab" onclick="switchTab('combos')">🔗 信号叠加</div>
    <div class="tab" onclick="switchTab('atr')">📊 波动环境</div>
    <div class="tab" onclick="switchTab('speed')">⏱ 盈利速度</div>
    <div class="tab" onclick="switchTab('checklist')">✅ 入场清单</div>
</div>

<div id="tab-mae" class="panel">
    <h3>📉 最大不利偏移 (MAE) — 交易离止损最近的时候有多近？</h3>
    <div id="maeInsight" class="key-finding"></div>
    <div class="chart-wrap"><canvas id="chartMAE"></canvas></div>
</div>
<div id="tab-hour" class="panel" style="display:none">
    <h3>🕐 入场时段热力图</h3>
    <div class="chart-wrap"><canvas id="chartHour"></canvas></div>
</div>
<div id="tab-combos" class="panel" style="display:none">
    <h3>🔗 信号叠加效果 — 哪些信号组合更可靠？</h3>
    <div class="grid2">
        <div class="chart-wrap"><canvas id="chartComboSurvive"></canvas></div>
        <div class="chart-wrap"><canvas id="chartComboProfit"></canvas></div>
    </div>
</div>
<div id="tab-atr" class="panel" style="display:none">
    <h3>📊 波动率环境 — 高波动时进场更危险吗？</h3>
    <div class="chart-wrap"><canvas id="chartATR"></canvas></div>
</div>
<div id="tab-speed" class="panel" style="display:none">
    <h3>⏱ 盈利速度 — 赚1%/2%/3%/5%要等多久？</h3>
    <div class="grid2">
        <div class="chart-wrap"><canvas id="chartSpeed"></canvas></div>
        <div class="chart-wrap"><canvas id="chartReachRate"></canvas></div>
    </div>
</div>
<div id="tab-checklist" class="panel" style="display:none">
    <h3>✅ 交易入场清单（基于数据分析）</h3>
    <div id="checklistContent"></div>
</div>

<script>
var D=JSON.parse('__DATA__');
var curSym,curTab='mae';
var charts={{}};

// Init
(function(){{
    if(!D.length)return;
    var sel=document.getElementById('symSelect');
    D.forEach(function(d,i){{
        sel.innerHTML+='<option value="'+i+'">'+d.symbol+' (信号:'+d.total_signals+')</option>';
    }});
    curSym=D[0];switchSymbol();
}})();

function switchSymbol(){{
    curSym=D[parseInt(document.getElementById('symSelect').value)];
    destroyCharts();renderTab();
}}
function switchTab(t){{
    document.querySelectorAll('.tab').forEach(function(x){{x.classList.remove('active');}});
    event.target.classList.add('active');
    curTab=t;
    ['mae','hour','combos','atr','speed','checklist'].forEach(function(x){{
        var e=document.getElementById('tab-'+x);if(e)e.style.display=x===t?'':'none';
    }});
    destroyCharts();renderTab();
}}
function renderTab(){{
    if(!curSym)return;
    switch(curTab){{
        case'mae':drawMAE();break;
        case'hour':drawHour();break;
        case'combos':drawCombos();break;
        case'atr':drawATR();break;
        case'speed':drawSpeed();break;
        case'checklist':drawChecklist();break;
    }}
}}
function destroyCharts(){{for(var k in charts){{if(charts[k]&&charts[k].destroy)charts[k].destroy();}}charts={{}};}}
function mkChart(id,type,data,opt){{
    if(typeof Chart==='undefined')return;
    var ctx=document.getElementById(id);if(!ctx)return;
    charts[id]=new Chart(ctx.getContext('2d'),{{type:type,data:data,options:opt}});
}}

// ── MAE ──
function drawMAE(){{
    var m=curSym,b=m.mae_buckets;
    var labels=['<0.5%','0.5-1%','1-1.5%','1.5-2%','止损出局'];
    var values=[b['<0.5%']||0,b['0.5-1%']||0,b['1-1.5%']||0,b['1.5-2%']||0,b['stopped']||0];
    var total=m.total_signals;
    document.getElementById('maeInsight').innerHTML=
        '<strong>📌 关键发现:</strong> '+
        '平均最大浮亏仅 <strong>'+m.avg_mae.toFixed(2)+'%</strong>，'+
        '说明大部分存活交易根本不需要2%止损，实际承受的最大压力远小于止损线。'+
        (b['<0.5%']+b['0.5-1%'])>total*0.6 ?
        '<strong>超过60%的交易最大回撤不到1%！</strong>' : '';
    mkChart('chartMAE','bar',{{
        labels:labels,
        datasets:[{{
            label:'交易数',data:values,
            backgroundColor:['rgba(45,212,124,.7)','rgba(45,212,124,.5)','rgba(245,166,35,.5)','rgba(245,166,35,.3)','rgba(245,71,93,.6)'],
            borderColor:['#2dd47c','#2dd47c','#f5a623','#f5a623','#f5475d'],
            borderWidth:1,borderRadius:4
        }}]
    }},{{
        responsive:true,maintainAspectRatio:false,
        plugins:{{legend:{{display:false}},tooltip:{{backgroundColor:'#0f1623',callbacks:{{label:function(c){{return c.raw+' 笔 ('+(c.raw/total*100).toFixed(1)+'%)';}}}}}}}},
        scales:{{x:{{ticks:{{color:'#5e6d82'}}}},y:{{ticks:{{color:'#5e6d82'}},title:{{display:true,text:'交易笔数',color:'#5e6d82'}}}}}}
    }});
}}

// ── Hour ──
function drawHour(){{
    var h=curSym.hour_data;
    var labels=[],surv=[],sigs=[];
    for(var i=0;i<24;i++){{labels.push(('0'+i).slice(-2)+':00');surv.push(h[i]?h[i].survive_rate:0);sigs.push(h[i]?h[i].signals:0);}}
    mkChart('chartHour','bar',{{
        labels:labels,
        datasets:[
            {{label:'存活率 %',data:surv,yAxisID:'y',
              backgroundColor:surv.map(function(s){{return s>=60?'rgba(45,212,124,.6)':s>=40?'rgba(245,166,35,.6)':'rgba(245,71,93,.6)';}}),
              borderColor:surv.map(function(s){{return s>=60?'#2dd47c':s>=40?'#f5a623':'#f5475d';}}),
              borderWidth:1,borderRadius:4}},
            {{label:'信号数',data:sigs,type:'line',yAxisID:'y1',
              borderColor:'#4da8f7',backgroundColor:'transparent',borderWidth:2,pointRadius:3,tension:.3}}
        ]
    }},{{
        responsive:true,maintainAspectRatio:false,
        plugins:{{legend:{{labels:{{color:'#5e6d82',usePointStyle:true}}}}}},
        scales:{{
            x:{{ticks:{{color:'#5e6d82',maxRotation:45}}}},
            y:{{type:'linear',position:'left',min:0,max:100,ticks:{{color:'#5e6d82',callback:function(v){{return v+'%';}}}},title:{{display:true,text:'存活率',color:'#5e6d82'}}}},
            y1:{{type:'linear',position:'right',ticks:{{color:'#4da8f7'}},title:{{display:true,text:'信号数',color:'#4da8f7'}},grid:{{display:false}}}}
        }}
    }});
}}

// ── Combos ──
function drawCombos(){{
    var c=curSym.combo_data,entries=Object.entries(c).sort(function(a,b){{return b[1].survive_rate-a[1].survive_rate;}});
    if(!entries.length)return;
    var nMap={{'dmi_flip':'DMI翻多','srsi_bounce':'超卖反弹','support_touch':'支撑触碰','dmi_flip_near_support':'DMI翻多+支撑','srsi_bounce_near_support':'超卖反弹+支撑','support_touch_near_support':'支撑触碰'}};
    mkChart('chartComboSurvive','bar',{{
        labels:entries.map(function(e){{return nMap[e[0]]||e[0];}}),
        datasets:[{{
            label:'存活率 %',data:entries.map(function(e){{return e[1].survive_rate;}}),
            backgroundColor:entries.map(function(e){{return e[1].survive_rate>=70?'rgba(45,212,124,.7)':e[1].survive_rate>=50?'rgba(245,166,35,.7)':'rgba(245,71,93,.7)';}}),
            borderWidth:1,borderRadius:4
        }}]
    }},{{
        indexAxis:'y',responsive:true,maintainAspectRatio:false,
        plugins:{{title:{{display:true,text:'存活率对比',color:'#dce5f0',font:{{size:13}}}},legend:{{display:false}}}},
        scales:{{x:{{ticks:{{color:'#5e6d82',callback:function(v){{return v+'%';}}}},min:0,max:100}},y:{{ticks:{{color:'#5e6d82'}}}}}}
    }});
    mkChart('chartComboProfit','bar',{{
        labels:entries.map(function(e){{return nMap[e[0]]||e[0];}}),
        datasets:[{{
            label:'均盈 %',data:entries.map(function(e){{return e[1].avg_profit;}}),
            backgroundColor:'rgba(77,168,247,.7)',borderColor:'#4da8f7',borderWidth:1,borderRadius:4
        }}]
    }},{{
        indexAxis:'y',responsive:true,maintainAspectRatio:false,
        plugins:{{title:{{display:true,text:'均盈对比',color:'#dce5f0',font:{{size:13}}}},legend:{{display:false}}}},
        scales:{{x:{{ticks:{{color:'#5e6d82',callback:function(v){{return v+'%';}}}}}},y:{{ticks:{{color:'#5e6d82'}}}}}}
    }});
}}

// ── ATR ──
function drawATR(){{
    var a=curSym.atr_data,entries=Object.entries(a);
    mkChart('chartATR','bar',{{
        labels:entries.map(function(e){{return e[0];}}),
        datasets:[
            {{label:'存活率 %',data:entries.map(function(e){{return e[1].survive_rate;}}),yAxisID:'y',
              backgroundColor:['rgba(45,212,124,.6)','rgba(245,166,35,.6)','rgba(245,71,93,.6)'],
              borderWidth:1,borderRadius:4}},
            {{label:'均盈 %',data:entries.map(function(e){{return e[1].avg_profit;}}),type:'line',yAxisID:'y1',
              borderColor:'#4da8f7',backgroundColor:'transparent',borderWidth:2,pointRadius:5,tension:.3}}
        ]
    }},{{
        responsive:true,maintainAspectRatio:false,
        plugins:{{legend:{{labels:{{color:'#5e6d82',usePointStyle:true}}}}}},
        scales:{{
            x:{{ticks:{{color:'#5e6d82'}}}},
            y:{{type:'linear',position:'left',min:0,max:100,ticks:{{color:'#5e6d82',callback:function(v){{return v+'%';}}}},title:{{display:true,text:'存活率',color:'#5e6d82'}}}},
            y1:{{type:'linear',position:'right',ticks:{{color:'#4da8f7',callback:function(v){{return v+'%';}}}},title:{{display:true,text:'均盈',color:'#4da8f7'}},grid:{{display:false}}}}
        }}
    }});
}}

// ── Speed ──
function drawSpeed(){{
    var s=curSym.speed_summary,entries=Object.entries(s);
    var labels=entries.map(function(e){{return e[0].replace('to_','+');}});
    function fmtTime(m){{return m>=60?Math.floor(m/60)+'h'+(m%60)+'m':m+'m';}}
    mkChart('chartSpeed','bar',{{
        labels:labels,
        datasets:[{{
            label:'平均耗时',data:entries.map(function(e){{return e[1].avg_minutes;}}),
            backgroundColor:'rgba(77,168,247,.6)',borderColor:'#4da8f7',borderWidth:1,borderRadius:4
        }}]
    }},{{
        responsive:true,maintainAspectRatio:false,
        plugins:{{legend:{{display:false}},title:{{display:true,text:'达到目标的平均耗时',color:'#dce5f0',font:{{size:13}}}},
                  tooltip:{{backgroundColor:'#0f1623',callbacks:{{label:function(c){{return '平均 '+fmtTime(c.raw);}}}}}}}},
        scales:{{x:{{ticks:{{color:'#5e6d82'}}}},y:{{ticks:{{color:'#5e6d82',callback:function(v){{return fmtTime(v);}}}},title:{{display:true,text:'耗时',color:'#5e6d82'}}}}}}
    }});
    mkChart('chartReachRate','bar',{{
        labels:labels,
        datasets:[{{
            label:'达成率 %',data:entries.map(function(e){{return e[1].reach_rate;}}),
            backgroundColor:['rgba(45,212,124,.7)','rgba(77,168,247,.7)','rgba(245,166,35,.7)','rgba(245,71,93,.5)'],
            borderWidth:1,borderRadius:4
        }}]
    }},{{
        responsive:true,maintainAspectRatio:false,
        plugins:{{legend:{{display:false}},title:{{display:true,text:'存活交易中多少比例能到达该目标',color:'#dce5f0',font:{{size:13}}}}}},
        scales:{{x:{{ticks:{{color:'#5e6d82'}}}},y:{{ticks:{{color:'#5e6d82',callback:function(v){{return v+'%';}}}},min:0,max:100,title:{{display:true,text:'达成率',color:'#5e6d82'}}}}}}
    }});
}}

// ── Checklist ──
function drawChecklist(){{
    var m=curSym;
    // Find best hour
    var bestH=null,bestHS=0;
    Object.entries(m.hour_data).forEach(function(e){{
        if(e[1].signals>=5&&e[1].survive_rate>bestHS){{bestH=e[0];bestHS=e[1].survive_rate;}}
    }});
    // Find best combo
    var bestComb='',bestCS=0;
    Object.entries(m.combo_data).forEach(function(e){{
        if(e[1].signals>=10&&e[1].survive_rate>bestCS){{bestComb=e[0];bestCS=e[1].survive_rate;}}
    }});
    // Find best ATR zone
    var bestAtr='',bestAS=0;
    Object.entries(m.atr_data).forEach(function(e){{
        if(e[1].signals>=10&&e[1].survive_rate>bestAS){{bestAtr=e[0];bestAS=e[1].survive_rate;}}
    }});
    document.getElementById('checklistContent').innerHTML=
        '<div class="key-finding"><strong>1️⃣ 入场时机:</strong> 优先在 '+(bestH||'?')+':00 前后入场 (存活率'+bestHS.toFixed(0)+'%)</div>'+
        '<div class="key-finding"><strong>2️⃣ 信号类型:</strong> 优先等待 <strong>'+(bestComb||'?')+'</strong> 触发 (存活率'+bestCS.toFixed(0)+'%)</div>'+
        '<div class="key-finding"><strong>3️⃣ 波动环境:</strong> 避开 '+(m.atr_data['高波(>2%)']&&m.atr_data['高波(>2%)'].survive_rate<50?'高波动时段':'低存活率时段')+'，优先在 <strong>'+bestAtr+'</strong> 交易 (存活率'+bestAS.toFixed(0)+'%)</div>'+
        '<div class="key-finding"><strong>4️⃣ 止损信心:</strong> 历史平均最大回撤仅 '+m.avg_mae.toFixed(2)+'%，2%止损提供了 <strong>'+(2-m.avg_mae).toFixed(2)+'%</strong> 的额外安全边际</div>'+
        '<div class="key-finding"><strong>5️⃣ 仓位建议:</strong> 综合存活率 '+m.survive_rate.toFixed(0)+'%，建议仓位控制在该品种可承受亏损的 <strong>'+(m.survive_rate*0.8).toFixed(0)+'%</strong> 以内</div>';
}}
</script>
</body>
</html>"""
    html = html.replace('__DATA__', data_json)
    with open(output_path, "w") as f:
        f.write(html)
    print(f"✅ 细节仪表盘: {output_path}")


if __name__ == "__main__":
    build_detail_dashboard()
