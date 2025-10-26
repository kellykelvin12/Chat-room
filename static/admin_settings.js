document.addEventListener('DOMContentLoaded', function(){
  const btn = document.getElementById('toggle-active-users');
  if(!btn) return;
  btn.addEventListener('click', async function(){
    const currently = btn.getAttribute('data-show') === 'true';
    const newVal = !currently;
    try{
      const res = await fetch('/admin/toggle_active_users', {
        method: 'POST',
        headers: {'Content-Type':'application/json','X-Requested-With':'XMLHttpRequest'},
        body: JSON.stringify({show: newVal}),
        credentials: 'same-origin'
      });
      const data = await res.json();
      if(data.status === 'success'){
        btn.textContent = (data.show ? 'Hide' : 'Show') + ' Active Users';
        btn.setAttribute('data-show', data.show ? 'true' : 'false');
        location.reload();
      } else {
        alert('Failed to toggle setting');
      }
    }catch(e){ alert('Request failed'); }
  });
});
