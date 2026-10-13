(()=>{'use strict';
const node=document.getElementById('star-count');if(!node)return;
const key='video-rsi-github-stars';
try{const cached=JSON.parse(sessionStorage.getItem(key)||'null');if(cached&&Number.isInteger(cached.count)){node.textContent=cached.count.toLocaleString();if(Date.now()-cached.time<3600000)return;}}catch{}
fetch('https://api.github.com/repos/bingjunluo/Video-RSI',{credentials:'omit',headers:{Accept:'application/vnd.github+json'}})
.then(response=>response.ok?response.json():null).then(repo=>{if(!repo||!Number.isInteger(repo.stargazers_count))return;node.textContent=repo.stargazers_count.toLocaleString();node.title='Repository-wide stars';try{sessionStorage.setItem(key,JSON.stringify({count:repo.stargazers_count,time:Date.now()}));}catch{}}).catch(()=>{});
})();
