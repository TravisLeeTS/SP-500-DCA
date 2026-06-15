import bisect, numpy as np, pandas as pd, matplotlib.pyplot as plt
url='https://raw.githubusercontent.com/Habrador/Bitcoin-price-visualization/master/Bitcoin-price-USD.csv'
p=pd.read_csv(url); p['Date']=pd.to_datetime(p['Date'])
s=pd.Series(pd.to_numeric(p['Price'],errors='coerce').values,index=p['Date'],name='close').dropna().sort_index().asfreq('D').ffill()
def rsi(x,w=20):
    d=x.diff(); g=d.clip(lower=0); l=-d.clip(upper=0)
    ag=g.ewm(alpha=1/w,adjust=False,min_periods=w).mean(); al=l.ewm(alpha=1/w,adjust=False,min_periods=w).mean()
    return (100-100/(1+ag/al.replace(0,np.nan))).where(al!=0,100)
def prank(x,m=730):
    vals=[]; out=np.full(len(x),np.nan)
    for i,v in enumerate(x.to_numpy(float)):
        if np.isfinite(v): bisect.insort(vals,float(v))
        if len(vals)>=m and np.isfinite(v): out[i]=bisect.bisect_right(vals,float(v))/len(vals)
    return pd.Series(out,index=x.index)
def plres(x,mn=730):
    t=np.log((x.index-pd.Timestamp('2009-01-03')).days.astype(float)); y=np.log(x.to_numpy(float)); m=np.isfinite(t)&np.isfinite(y)
    n=pd.Series(m.astype(int),x.index).cumsum().shift(1); sx=pd.Series(np.where(m,t,0),x.index).cumsum().shift(1); sy=pd.Series(np.where(m,y,0),x.index).cumsum().shift(1)
    sxx=pd.Series(np.where(m,t*t,0),x.index).cumsum().shift(1); sxy=pd.Series(np.where(m,t*y,0),x.index).cumsum().shift(1)
    b=(n*sxy-sx*sy)/(n*sxx-sx*sx).replace(0,np.nan); a=(sy-b*sx)/n.replace(0,np.nan)
    return (pd.Series(y,x.index)-(b*pd.Series(t,x.index)+a)).where(n>=mn)
iss=pd.Series(7200.0,s.index); iss.loc[s.index>=pd.Timestamp('2012-11-28')]=3600; iss.loc[s.index>=pd.Timestamp('2016-07-09')]=1800; iss.loc[s.index>=pd.Timestamp('2020-05-11')]=900; iss.loc[s.index>=pd.Timestamp('2024-04-20')]=450
r=s.pct_change(); raw=pd.DataFrame({'ema_short_medium':np.log(s.ewm(span=5).mean()/s.ewm(span=50).mean()),'mayer_200d':np.log(s/s.rolling(200).mean()),'ema200_extension':np.log(s/s.ewm(span=200).mean()),'ema400_extension':np.log(s/s.ewm(span=400).mean()),'rsi20':rsi(s),'sharpe365':r.rolling(365).mean()/r.rolling(365).std()*np.sqrt(365),'powerlaw_resid':plres(s),'puell':np.log((iss*s)/(iss*s).rolling(365).mean())}).replace([np.inf,-np.inf],np.nan)
rank=pd.DataFrame({c:prank(raw[c]) for c in raw.columns})
w=pd.Series({'ema_short_medium':.10,'mayer_200d':.15,'ema200_extension':.12,'ema400_extension':.13,'rsi20':.08,'sharpe365':.08,'powerlaw_resid':.24,'puell':.10})
risk=(rank.mul(w,axis=1).sum(axis=1)/rank.notna().mul(w,axis=1).sum(axis=1).replace(0,np.nan)).where(rank.notna().sum(axis=1)>=5).ewm(span=5).mean().clip(0,1)
ts=pd.concat([s,risk.rename('risk')],axis=1).dropna()
v=ts.copy()
for d in [365,730,1460]: v[f'fwd_{d}d']=v.close.shift(-d)/v.close-1
v=v.dropna(); v['q']=pd.qcut(v.risk,5,labels=False,duplicates='drop')+1
q=v.groupby('q').agg(n=('risk','size'),median_risk=('risk','median'),median_fwd_1y=('fwd_365d','median'),median_fwd_2y=('fwd_730d','median'),median_fwd_4y=('fwd_1460d','median'),mean_fwd_1y=('fwd_365d','mean'),mean_fwd_2y=('fwd_730d','mean'),mean_fwd_4y=('fwd_1460d','mean')).reset_index()
sp=v[['risk','fwd_365d','fwd_730d','fwd_1460d']].corr(method='spearman').loc['risk']
rows=[]
for strat in ['static','risk_adjusted']:
    cash=btc=0.0
    for dt,row in ts.resample('MS').first().iterrows():
        cash+=1000; rr=row.risk; mult=1 if strat=='static' else (1.5 if rr<.2 else 1.25 if rr<.4 else 1 if rr<.6 else .5 if rr<.75 else .25)
        buy=min(cash,1000*mult); btc+=buy/row.close; cash-=buy; rows.append([dt,strat,cash,btc,cash+btc*row.close,buy])
d=pd.DataFrame(rows,columns='date strategy cash btc equity buy'.split())
ds=d.groupby('strategy').apply(lambda g:pd.Series({'months':len(g),'total_bought':g.buy.sum(),'ending_cash':g.cash.iloc[-1],'ending_btc':g.btc.iloc[-1],'terminal_wealth':g.equity.iloc[-1],'profit_vs_contribution':g.equity.iloc[-1]/(1000*len(g))-1,'max_drawdown':(g.equity/g.equity.cummax()-1).min()})).reset_index()
ev=[]
for name,dt in {'2013_top':'2013-12-04','2015_bottom':'2015-01-14','2017_top':'2017-12-17','2018_bottom':'2018-12-15','2021_top':'2021-11-10','2022_bottom':'2022-11-21','2024_halving':'2024-04-20'}.items():
    ix=ts.index[ts.index.get_indexer([pd.Timestamp(dt)],method='nearest')[0]]; ev.append([name,str(ix.date()),ts.loc[ix,'close'],ts.loc[ix,'risk']])
ev=pd.DataFrame(ev,columns='event date close risk'.split())
ts.to_csv('btc_risk_proxy_timeseries.csv'); q.to_csv('btc_risk_proxy_quintile_validation.csv',index=False); ds.to_csv('btc_risk_proxy_dca_validation.csv',index=False); ev.to_csv('btc_risk_proxy_event_validation.csv',index=False)
ax=ts.close.plot(logy=True,figsize=(12,6)); ax2=ax.twinx(); ts.risk.plot(ax=ax2); ax2.set_ylim(0,1); plt.savefig('btc_risk_proxy_chart.png',dpi=160)
print('LATEST'); print(ts.tail(1).to_string()); print('\nQUINTILE_VALIDATION'); print(q.to_string(index=False)); print('\nSPEARMAN'); print(sp.to_string()); print('\nDCA'); print(ds.to_string(index=False)); print('\nEVENTS'); print(ev.to_string(index=False))
