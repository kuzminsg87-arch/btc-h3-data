#!/usr/bin/env python3
import json, urllib.parse, urllib.request
from datetime import datetime, timezone
BASE="https://api.bybit.com"; SYMBOL="BTCUSDT"; CATEGORY="linear"

def get(path,p):
    url=BASE+path+"?"+urllib.parse.urlencode(p)
    with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"H3-v3"}),timeout=15) as r:
        d=json.loads(r.read())
    if d.get("retCode")!=0: raise RuntimeError(d.get("retMsg"))
    return d["result"]

def ema(v,n):
    a=2/(n+1); o=[v[0]]
    for x in v[1:]: o.append(a*x+(1-a)*o[-1])
    return o

def candles(interval):
    x=get("/v5/market/kline",{"category":CATEGORY,"symbol":SYMBOL,"interval":interval,"limit":250})["list"]
    rows=[{"ts":int(r[0]),"o":float(r[1]),"h":float(r[2]),"l":float(r[3]),"c":float(r[4]),"v":float(r[5])} for r in reversed(x)]
    ms={"60":3600000,"240":14400000}[interval]; now=int(datetime.now(timezone.utc).timestamp()*1000)
    r=[x for x in rows if x["ts"]+ms<=now]; c=[x["c"] for x in r]
    e5,e10,e20=ema(c,5)[-1],ema(c,10)[-1],ema(c,20)[-1]
    e12,e26=ema(c,12),ema(c,26); ml=[a-b for a,b in zip(e12,e26)]; sig=ema(ml,9); hist=ml[-1]-sig[-1]
    tr=[max(r[i]["h"]-r[i]["l"],abs(r[i]["h"]-r[i-1]["c"]),abs(r[i]["l"]-r[i-1]["c"])) for i in range(1,len(r))]
    atr=sum(tr[-14:])/14
    avg20=sum(x["v"] for x in r[-21:-1])/20; rv=r[-1]["v"]/avg20
    return {"close":r[-1]["c"],"EMA5":e5,"EMA10":e10,"EMA20":e20,"MACD":ml[-1],"MACD_signal":sig[-1],"MACD_hist":hist,"ATR14":atr,"volume":r[-1]["v"],"RVOL20":rv,"high20":max(x["h"] for x in r[-20:]),"low20":min(x["l"] for x in r[-20:])}

def ticker():
    x=get("/v5/market/tickers",{"category":CATEGORY,"symbol":SYMBOL})["list"][0]
    return {k:float(x[k]) for k in ["lastPrice","markPrice","indexPrice","fundingRate","openInterest"]}

def oi(period):
    x=list(reversed(get("/v5/market/open-interest",{"category":CATEGORY,"symbol":SYMBOL,"intervalTime":period,"limit":24})["list"]))
    a,b=float(x[-2]["openInterest"]),float(x[-1]["openInterest"])
    return {"previous":a,"latest":b,"change_pct":(b/a-1)*100}

def ls(period):
    x=get("/v5/market/account-ratio",{"category":CATEGORY,"symbol":SYMBOL,"period":period,"limit":1})["list"][0]
    a,b=float(x["buyRatio"]),float(x["sellRatio"])
    return {"long":a,"short":b,"L_S":a/b if b else None}

def main():
    out={"generated_at":datetime.now(timezone.utc).isoformat(),"venue":"Bybit","symbol":SYMBOL}; ok={}
    jobs={"ticker":ticker,"1H":lambda:candles("60"),"4H":lambda:candles("240"),"OI_1H":lambda:oi("1h"),"OI_4H":lambda:oi("4h"),"LS_1H":lambda:ls("1h"),"LS_4H":lambda:ls("4h")}
    for k,f in jobs.items():
        try: out[k]=f(); ok[k]=True
        except Exception as e: out[k]={"error":str(e)}; ok[k]=False
    out["CoinGlass_Heatmap"]={"available":False,"note":"user screenshot recommended"}
    ok["CoinGlass_Heatmap"]=False; out["data_integrity"]=ok
    print(json.dumps(out,indent=2,ensure_ascii=False))
if __name__=="__main__": main()
