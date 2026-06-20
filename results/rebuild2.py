import json

with open('results/journal_trades.json') as f: trades = json.load(f)

total = len(trades)
wins = sum(1 for t in trades if t['pnl_usdt'] > 0)
total_pnl = sum(t['pnl_usdt'] for t in trades)

data = json.dumps(trades, ensure_ascii=False, separators=(',', ':'))

html = '''<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>交易日记</title>
<style>
body{font-family:-apple-system,sans-serif;background:#f8f9fa;padding:16px;max-width:1200px;margin:0 auto;color:#212529}
h1{font-size:20px}.s{color:#6c757d;font-size:13px;margin-bottom:12px}
.c{display:flex;gap:10px;margin-bottom:12px;flex-wrap:wrap}
.ca{background:#fff;border:1px solid #dee2e6;border-radius:8px;padding:12px 16px;text-align:center;flex:1;min-width:100px}
.ca .l{font-size:11px;color:#6c757d}.ca .v{font-size:20px;font-weight:700}
.g{color:#198754}.r{color:#dc3545}
table{width:100%;border-collapse:collapse;font-size:12px;background:#fff;border-radius:8px;overflow:hidden;border:1px solid #dee2e6}
th{background:#e9ecef;padding:8px 10px;text-align:left;font-weight:600;color:#6c757d;border-bottom:2px solid #0d6efd;font-size:11px}
td{padding:6px 10px;border-bottom:1px solid #dee2e6}
tr:nth-child(even) td{background:#f8f9fa}
.badge{display:inline-block;padding:1px 8px;border-radius:10px;font-size:10px;font-weight:600}
.bw{background:#d1e7dd;color:#198754}.bl{background:#f8d7da;color:#dc3545}
.tb{display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap;align-items:center}
.tb input,.tb select{padding:6px 12px;border:1px solid #dee2e6;border-radius:6px;font-size:12px;outline:none}
.btn{display:inline-block;padding:8px 18px;border-radius:6px;font-size:13px;font-weight:600;text-decoration:none;background:#198754;color:#fff;margin-bottom:12px}
</style></head>
<body>
<h1>6月交易记录</h1>
<div class="s">''' + str(total) + '''笔 | 胜''' + str(wins) + ''' | PnL ''' + ('%+.1f' % total_pnl) + '''U</div>
<div class="c">
<div class="ca"><div class="l">总交易</div><div class="v">''' + str(total) + '''</div></div>
<div class="ca"><div class="l">胜率</div><div class="v ''' + ('g' if wins/total>=0.5 else 'r') + '''">''' + str(round(wins/total*100)) + '''%</div></div>
<div class="ca"><div class="l">净盈亏</div><div class="v ''' + ('g' if total_pnl>0 else 'r') + '''">''' + ('%+.1f' % total_pnl) + '''U</div></div>
</div>
<a href="交易记录_06.xlsx" class="btn" download>下载 Excel</a>
<div class="tb">
<input type="date" id="df" onchange="R()" style="width:130px"> - <input type="date" id="dt" onchange="R()" style="width:130px">
<input type="text" id="sq" placeholder="搜索..." oninput="R()">
<select id="sd" onchange="R()"><option value="all">全部</option><option value="做多">做多</option><option value="做空">做空</option></select>
<select id="sr" onchange="R()"><option value="all">全部</option><option value="win">盈利</option><option value="lose">亏损</option></select>
<span style="font-size:11px;color:#6c757d" id="rc"></span>
</div>
<table><thead><tr><th>日期</th><th>币种</th><th>方向</th><th>趋势(1H/4H/1D)</th><th>SRSI</th><th>入场价</th><th>离场价</th><th>盈亏%</th><th>最大亏损</th><th>最大盈利</th><th>结果</th></tr></thead><tbody id="tb"></tbody></table>
<script>
var D=''' + data + ''';
R();
function R(){
var q=document.getElementById("sq").value.toLowerCase();
var d=document.getElementById("sd").value,r=document.getElementById("sr").value;
var df=document.getElementById("df").value,dt2=document.getElementById("dt").value;
var f=[];
for(var i=D.length-1;i>=0;i--){
var t=D[i];
if(df&&t.entry_time<df+" 00:00")continue;if(dt2&&t.entry_time>dt2+" 23:59")continue;
if(q&&t.coin.toLowerCase().indexOf(q)<0)continue;
if(d!=="all"&&t.direction!==d)continue;
if(r==="win"&&t.pnl_usdt<=0)continue;if(r==="lose"&&t.pnl_usdt>=0)continue;
f.push(t);
}
document.getElementById("rc").textContent=f.length+"/"+D.length+"笔";
var tb=document.getElementById("tb");tb.innerHTML="";
for(var i=0;i<f.length;i++){
var t=f[i];
var r=document.createElement("tr");
var c1=document.createElement("td");c1.textContent=t.entry_time.substr(0,16);r.appendChild(c1);
var c2=document.createElement("td");c2.innerHTML="<b>"+t.coin+"<\\/b>";r.appendChild(c2);
var c3=document.createElement("td");c3.innerHTML="<span class=badge "+(t.direction==="做多"?"bw":"bl")+">"+t.direction+"<\\/span>";r.appendChild(c3);
var c4=document.createElement("td");c4.textContent=t.trend_1h+"/"+t.trend_4h+"/"+t.trend_1d;r.appendChild(c4);
var c5=document.createElement("td");c5.textContent=t.srsi_1h+"/"+t.srsi_4h+"/"+t.srsi_1d;r.appendChild(c5);
var c6=document.createElement("td");c6.textContent=""+t.entry_price;r.appendChild(c6);
var c7=document.createElement("td");c7.textContent=""+t.exit_price;r.appendChild(c7);
var c8=document.createElement("td");c8.className=t.pnl_usdt>0?"g":"r";c8.textContent=t.pnl_pct.toFixed(1)+"%";r.appendChild(c8);
var c9=document.createElement("td");c9.className="r";c9.textContent=(t.mae_pct||0).toFixed(1)+"%";r.appendChild(c9);
var ca=document.createElement("td");ca.className="g";ca.textContent=(t.mfe_pct||0).toFixed(1)+"%";r.appendChild(ca);
var cb=document.createElement("td");cb.innerHTML="<span class=badge "+(t.pnl_usdt>0?"bw":"bl")+">"+(t.pnl_usdt>0?"赢":"亏")+"<\\/span>";r.appendChild(cb);
tb.appendChild(r);
}
}
</script>
</body></html>'''

with open('results/index.html', 'w') as f:
    f.write(html)

# Verify no </ in data
assert '</' not in data, 'FATAL: </ in data!'
assert len(html.split('\n')) < 100, 'HTML too many lines'
print(f'HTML: {len(html)} chars, safe')
