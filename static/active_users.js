(function(){
  const PING_INTERVAL = 20000; // 20s
  const COUNT_INTERVAL = 30000; // 30s

  async function ping(){
    try{
      await fetch('/api/ping', {method: 'POST', headers: {'X-Requested-With':'XMLHttpRequest'}, credentials: 'same-origin'});
    }catch(e){/* ignore */}
  }

  async function refreshCount(){
    try{
      const res = await fetch('/api/active_counts', {headers: {'X-Requested-With':'XMLHttpRequest'}, credentials: 'same-origin'});
      if(res.ok){
        const data = await res.json();
        if(data.status === 'success'){
          const el = document.getElementById('global-active-count');
          const badge = document.getElementById('global-active-badge');
          if(el) el.textContent = `Active now: ${data.global_active} users`;
          if(badge){
            if(data.global_active && data.global_active > 0){
              badge.classList.add('online'); badge.classList.remove('offline');
            } else {
              badge.classList.add('offline'); badge.classList.remove('online');
            }
          }
        }
      }
    }catch(e){/* ignore */}
  }

  // Initial ping and schedule
  setTimeout(ping, 1000);
  setInterval(ping, PING_INTERVAL);
  setTimeout(refreshCount, 1500);
  setInterval(refreshCount, COUNT_INTERVAL);
})();
