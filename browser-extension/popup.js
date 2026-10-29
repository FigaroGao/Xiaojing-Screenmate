document.getElementById('start').onclick=async()=>{
 const token=document.getElementById('token').value.trim();if(token)await chrome.storage.session.set({token});
 const seconds=Number(document.getElementById('seconds').value);if(!Number.isFinite(seconds)||seconds<1||seconds>3600)return;
 const [tab]=await chrome.tabs.query({active:true,currentWindow:true});
 try{await chrome.scripting.executeScript({target:{tabId:tab.id},func:install,args:[seconds]});document.getElementById('status').textContent='已开启当前页；桌面端也须开启观看。'}catch{document.getElementById('status').textContent='此页面不允许读取。'}
};
document.getElementById('stop').onclick=async()=>{const [tab]=await chrome.tabs.query({active:true,currentWindow:true});await chrome.scripting.executeScript({target:{tabId:tab.id},func:()=>{clearInterval(window.__xiaojingTimer);window.__xiaojingTimer=null}});document.getElementById('status').textContent='已停止。'};
function install(seconds){
 clearInterval(window.__xiaojingTimer);
 function sample(){
  if(document.visibilityState!=='visible')return;
  const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);let node,parts=[],length=0;
  while((node=walker.nextNode())&&length<24000){const el=node.parentElement;if(!el||el.closest('script,style,noscript,input,textarea,[contenteditable]'))continue;const r=el.getBoundingClientRect(),s=getComputedStyle(el);if(r.bottom<=0||r.top>=innerHeight||r.right<=0||r.left>=innerWidth||s.display==='none'||s.visibility==='hidden'||s.opacity==='0')continue;const t=node.textContent.trim();if(t){parts.push(t);length+=t.length}}
  chrome.runtime.sendMessage({kind:'visible-text',data:{title:document.title,url:location.origin+location.pathname,text:parts.join('\n').slice(0,24000)}},()=>void chrome.runtime.lastError);
 }
 window.__xiaojingTimer=setInterval(sample,seconds*1000);sample();
}
