import bisect, json, urllib.request, numpy as np, pandas as pd, matplotlib.pyplot as plt
price_url='https://raw.githubusercontent.com/Habrador/Bitcoin-price-visualization/master/Bitcoin-price-USD.csv'
df=pd.read_csv(price_url); df['Date']=pd.to_datetime(df['Date'])
price=pd.Series(pd.to_numeric(df['Price'],errors='coerce').values,index=df['Date'],name='close').dropna().sort_index().asfreq('D').ffill()
def rank(s,m=730):
    vals=[]; out=np.full(len(s),np.nan)
    for i,v in enumerate(s.to_numpy(float)):
        if np.isfinite(v): bisect.insort(vals,float(v))
        if len(vals)>=m and np.isfinite(v): out[i]=bisect.bisect_right(vals,float(v))/len(vals)
    return pd.Series(out,index=s.index)
def rsi(x,w=20):
    d=x.diff(); g=d.clip(lower=0); l=-d.clip(upper=0)
    ag=g.ewm(alpha=1/w,adjust=False,min_periods=w).mean(); al=l.ewm(alpha=1/w,adjust=False,min_periods=w).mean()
    return (100-100/(1+ag/al.replace(0,np.nan))).where(al!=0,100)
def power_resid(x,mn=730):
    t=np.log((x.index-pd.Timestamp('2009-01-03')).days.astype(float)); y=np.log(x.to_numpy(float)); ok=np.isfinite(t)&np.isfinite(y)
    n=pd.Series(ok.astype(int),x.index).cumsum().shift(1); sx=pd.Series(np.where(ok,t,0),x.index).cumsum().shift(1); sy=pd.Series(np.where(ok,y,0),x.index).cumsum().shift(1)
    sxx=pd.Series(np.where(ok,t*t,0),x.index).cumsum().shift(1); sxy=pd.Series(np.where(ok,t*y,0),x.index).cumsum().shift(1)
    b=(n*sxy-sx*sy)/(n*sxx-sx*sx).replace(0,np.nan); a=(sy-b*sx)/n.replace(0,np.nan)
    return (pd.Series(y,x.index)-(b*pd.Series(t,x.index)+a)).where(n>=mn)
def get_coinmetrics():
    url='https://community-api.coinmetrics.io/v4/timeseries/asset-metrics?assets=btc&metrics=CapMrktCurUSD,CapRealUSD,FeeTotUSD,RevUSD,SplyCur&frequency=1d&start_time=2010-01-01&page_size=10000'
    try:
        raw=urllib.request.urlopen(url,timeout=40).read().decode('utf-8')
        js=json.loads(raw); cm=pd.DataFrame(js.get('data',[]))
        cm['time']=pd.to_datetime(cm['time']).dt.tz_localize(None).dt.normalize(); cm=cm.set_index('time').sort_index()
        for c in cm.columns: cm[c]=pd.to_numeric(cm[c],errors='coerce')
        return cm.reindex(price.index).ffill()
    except Exception as e:
        print('coinmetrics_fallback',repr(e))
        supply=pd.Series(0.0,index=price.index); daily=pd.Series(7200.0,index=price.index)
        daily.loc[price.index>=pd.Timestamp('2012-11-28')]=3600; daily.loc[price.index>=pd.Timestamp('2016-07-09')]=1800; daily.loc[price.index>=pd.Timestamp('2020-05-11')]=900; daily.loc[price.index>=pd.Timestamp('2024-04-20')]=450
        supply=(daily.cumsum()+2500000).clip(upper=21000000); cap=price*supply; rev=daily*price; fee=(abs(price.pct_change()).fillna(0)*rev*0.02)
        return pd.DataFrame({'CapMrktCurUSD':cap,'CapRealUSD':cap.ewm(span=730).mean(),'FeeTotUSD':fee,'RevUSD':rev+fee,'SplyCur':supply},index=price.index)
cm=get_coinmetrics(); cap=cm['CapMrktCurUSD'].fillna(price*cm['SplyCur'].ffill()); real=cm['CapRealUSD'].replace(0,np.nan); fee=cm['FeeTotUSD'].clip(lower=0); rev=cm['RevUSD'].clip(lower=0); supply=cm['SplyCur'].replace(0,np.nan)
resid=power_resid(price); ret=price.pct_change(); thermocap=rev.fillna(0).cumsum().replace(0,np.nan)
puell=rev/rev.rolling(365,min_periods=180).mean(); mvrv=cap/real; mvrvz=(cap-real)/(cap-real).rolling(1460,min_periods=365).std(); term_px=thermocap/supply; mctc=cap/thermocap; miner_proxy=(supply*price.rolling(365,min_periods=180).mean())/thermocap
btc_raw=pd.DataFrame({'mayer':np.log(price/price.rolling(200).mean()),'ema200':np.log(price/price.ewm(span=200).mean()),'ema400':np.log(price/price.ewm(span=400).mean()),'power':resid,'puell':np.log(puell)})
bitcoin_risk=btc_raw.apply(rank).mean(axis=1).ewm(span=5).mean()
price_metrics=pd.DataFrame({
 'total_market_cap_risk':rank(np.log(cap)),
 'bitcoin_risk':bitcoin_risk,
 'total_crypto_marketcap_trendline_risk':rank(resid.rolling(30,min_periods=1).mean()),
 'logarithmic_regression_risk':rank(resid),
 'cowen_corridor_risk':rank(np.log(price/price.rolling(365*2,min_periods=365).mean())),
 'fear_greed_proxy_risk':rank(rsi(price,20)/100)
})
onchain_metrics=pd.DataFrame({
 'puell_multiple_risk':rank(np.log(puell)),
 'mvrv_risk':rank(np.log(mvrv)),
 'mvrv_z_score_risk':rank(mvrvz),
 'transaction_fees_risk':rank(np.log((fee+1)/(fee+1).rolling(365,min_periods=180).mean())),
 'terminal_price_risk':rank(np.log(price/term_px)),
 'marketcap_to_thermocap_risk':rank(np.log(mctc)),
 'minercap_to_thermocap_risk':rank(np.log(miner_proxy))
})
social_metrics=pd.DataFrame({
 'google_trends_proxy_risk':rank(ret.rolling(30).sum()),
 'coinbase_app_proxy_risk':rank(ret.rolling(90).sum()),
 'youtube_subscribers_proxy_risk':rank(np.log(price/price.shift(365))),
 'youtube_views_proxy_risk':rank(abs(ret).rolling(30).sum()),
 'twitter_analysts_proxy_risk':rank(np.log(price/price.rolling(365).mean())),
 'twitter_exchanges_proxy_risk':rank(ret.rolling(180).sum()),
 'twitter_layer1s_proxy_risk':rank(np.log(cap/cap.rolling(365).mean()))
})
price_risk=price_metrics.mean(axis=1).rename('price_risk').clip(0,1); onchain_risk=onchain_metrics.mean(axis=1).rename('onchain_risk').clip(0,1); social_risk=social_metrics.mean(axis=1).rename('social_proxy_risk').clip(0,1)
summary=pd.concat([price_risk,onchain_risk,social_risk],axis=1).mean(axis=1).ewm(span=5).mean().rename('summary_risk').clip(0,1)
ts=pd.concat([price,summary,price_risk,onchain_risk,social_risk,bitcoin_risk.rename('bitcoin_risk')],axis=1).dropna()
v=ts.copy()
for d in [365,730,1460]: v[f'fwd_{d}d']=v.close.shift(-d)/v.close-1
v=v.dropna(); v['q']=pd.qcut(v.summary_risk,5,labels=False,duplicates='drop')+1
q=v.groupby('q').agg(n=('summary_risk','size'),median_summary_risk=('summary_risk','median'),median_fwd_1y=('fwd_365d','median'),median_fwd_2y=('fwd_730d','median'),median_fwd_4y=('fwd_1460d','median'),mean_fwd_1y=('fwd_365d','mean'),mean_fwd_2y=('fwd_730d','mean'),mean_fwd_4y=('fwd_1460d','mean')).reset_index()
sp=v[['summary_risk','fwd_365d','fwd_730d','fwd_1460d']].corr(method='spearman').loc['summary_risk']
rows=[]
for strat in ['static','summary_risk_adjusted']:
    cash=btc=0.0
    for dt,row in ts.resample('MS').first().iterrows():
        cash+=1000; rr=row.summary_risk; mult=1 if strat=='static' else (1.5 if rr<.20 else 1.25 if rr<.35 else 1 if rr<.50 else .5 if rr<.65 else .25)
        buy=min(cash,1000*mult); btc+=buy/row.close; cash-=buy; rows.append([dt,strat,cash,btc,cash+btc*row.close,buy])
dca=pd.DataFrame(rows,columns='date strategy cash btc equity buy'.split())
ds=dca.groupby('strategy').apply(lambda g:pd.Series({'months':len(g),'total_bought':g.buy.sum(),'ending_cash':g.cash.iloc[-1],'ending_btc':g.btc.iloc[-1],'terminal_wealth':g.equity.iloc[-1],'profit_vs_contribution':g.equity.iloc[-1]/(1000*len(g))-1,'max_drawdown':(g.equity/g.equity.cummax()-1).min()})).reset_index()
ev=[]
for name,dt in {'2013_top':'2013-12-04','2015_bottom':'2015-01-14','2017_top':'2017-12-17','2018_bottom':'2018-12-15','2021_top':'2021-11-10','2022_bottom':'2022-11-21','2024_halving':'2024-04-20'}.items():
    ix=ts.index[ts.index.get_indexer([pd.Timestamp(dt)],method='nearest')[0]]; ev.append([name,str(ix.date()),ts.loc[ix,'close'],ts.loc[ix,'summary_risk'],ts.loc[ix,'price_risk'],ts.loc[ix,'onchain_risk'],ts.loc[ix,'social_proxy_risk'],ts.loc[ix,'bitcoin_risk']])
ev=pd.DataFrame(ev,columns='event date close summary_risk price_risk onchain_risk social_proxy_risk bitcoin_risk'.split())
ts.to_csv('btc_summary_timeseries.csv'); q.to_csv('btc_summary_quintile_validation.csv',index=False); ds.to_csv('btc_summary_dca_validation.csv',index=False); ev.to_csv('btc_summary_event_validation.csv',index=False); price_metrics.to_csv('btc_summary_price_components.csv'); onchain_metrics.to_csv('btc_summary_onchain_components.csv'); social_metrics.to_csv('btc_summary_social_proxy_components.csv')
ax=ts.close.plot(logy=True,figsize=(12,6),title='BTC dashboard-summary proxy'); ax2=ax.twinx(); ts.summary_risk.plot(ax=ax2); ax2.set_ylim(0,1); plt.savefig('btc_summary_chart.png',dpi=160)
print('LATEST'); print(ts.tail(1).to_string()); print('\nQUINTILE_VALIDATION'); print(q.to_string(index=False)); print('\nSPEARMAN'); print(sp.to_string()); print('\nDCA'); print(ds.to_string(index=False)); print('\nEVENTS'); print(ev.to_string(index=False))
