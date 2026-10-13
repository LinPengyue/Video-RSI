(()=>{'use strict';
const apiOrigin=document.currentScript?.dataset.analyticsApi||location.origin;
const remote=apiOrigin!==location.origin;
const api=path=>new URL(path,apiOrigin).href;
const requestCredentials=remote?'omit':'same-origin';
const key='video-rsi-visitor',sessionKey='video-rsi-session',optout='video-rsi-analytics-disabled';
try{if(new URL(location.href).searchParams.get('analytics')==='off'){localStorage.setItem(optout,'1');localStorage.removeItem(key);sessionStorage.removeItem(sessionKey);}}catch{}
function disabled(){try{return localStorage.getItem(optout)==='1'||navigator.doNotTrack==='1'||navigator.globalPrivacyControl===true}catch{return true}}
const privacy=document.getElementById('analytics-optout');
function privacyLabel(){if(privacy)privacy.textContent=disabled()?'Enable anonymous analytics':'Disable anonymous analytics';}privacyLabel();
privacy?.addEventListener('click',()=>{try{if(localStorage.getItem(optout)==='1')localStorage.removeItem(optout);else{localStorage.setItem(optout,'1');localStorage.removeItem(key);sessionStorage.removeItem(sessionKey)}privacyLabel();document.getElementById('privacy-status').textContent='Preference saved for this browser.';}catch{}});
fetch(api('/api/stars'),{credentials:requestCredentials,mode:'cors'}).then(r=>r.ok?r.json():null).then(data=>{if(data&&Number.isInteger(data.count)){const e=document.getElementById('star-count');e.textContent=data.count.toLocaleString();e.title='Repository-wide stars'+(data.stale?' · last available count':'');}}).catch(()=>{});
if(disabled())return;
let visitor,session;
try{const now=Date.now(),url=new URL(location.href),tag=url.searchParams.get('utm_source')||'',ref=document.referrer?new URL(document.referrer):null,external=ref&&ref.origin!==location.origin?ref.origin:'';
let saved=JSON.parse(localStorage.getItem(key)||'null');if(!saved||saved.expires<now){saved={id:crypto.randomUUID(),expires:now+30*86400000};localStorage.setItem(key,JSON.stringify(saved));}visitor=saved.id;
session=JSON.parse(sessionStorage.getItem(sessionKey)||'null');if(!session||now-session.last>30*60000||(tag&&tag!==session.source)){session={id:crypto.randomUUID(),source:tag.slice(0,40),referrer:external,last:now};}session.last=now;sessionStorage.setItem(sessionKey,JSON.stringify(session));
}catch{return;}
function track(kind,target=''){if(disabled())return;const now=Date.now();if(now-session.last>30*60000){session={id:crypto.randomUUID(),source:'',referrer:'',last:now};}session.last=now;try{sessionStorage.setItem(sessionKey,JSON.stringify(session));}catch{}const event={id:crypto.randomUUID(),visitor,session:session.id,source:session.source,referrer:session.referrer,kind,target};const body=JSON.stringify(event);const blob=new Blob([body],{type:'application/json'});if(remote){fetch(api('/api/events'),{method:'POST',mode:'cors',credentials:'omit',headers:{'Content-Type':'text/plain;charset=UTF-8'},body,keepalive:true}).catch(()=>{});}else if(!navigator.sendBeacon||!navigator.sendBeacon('/api/events',blob))fetch('/api/events',{method:'POST',headers:{'Content-Type':'application/json'},body,keepalive:true}).catch(()=>{});}
track('pageview','homepage-buttons-v1');
function trackLink(e){if(e.type==='auxclick'&&e.button!==1)return;const link=e.target instanceof Element?e.target.closest('a[href]'):null;if(!link)return;let url;try{url=new URL(link.href)}catch{return;}let target=link.dataset.analyticsTarget;if(!target){if(url.hostname==='github.com'&&url.pathname.startsWith('/bingjunluo/Video-RSI'))target='github';else if(url.hostname==='huggingface.co'&&url.pathname==='/papers/2609.37950')target='huggingface';else if(url.hostname==='arxiv.org'&&url.pathname.includes('2609.37950'))target='arxiv';}if(target)track('outbound',target);}
document.addEventListener('click',trackLink);document.addEventListener('auxclick',trackLink);
})();
