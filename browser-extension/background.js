chrome.runtime.onMessage.addListener((message,sender,respond)=>{
  if(message.kind!=='visible-text'||!sender.tab)return;
  chrome.storage.session.get(['token']).then(async({token})=>{
    if(!token)return respond({ok:false});
    try{const r=await fetch('http://127.0.0.1:17860/v1/text',{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+token},body:JSON.stringify(message.data)});respond({ok:r.ok})}catch{respond({ok:false})}
  });return true;
});
