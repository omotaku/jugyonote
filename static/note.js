(function(){
  // Simple autosave + lightweight markdown preview
  const textarea = document.getElementById('note-content');
  if(!textarea) return;
  const preview = document.getElementById('preview-content');
  const form = textarea.closest('form');
  let lastSaved = '';
  let timeout = null;

  function simpleMarkdown(md){
    // very small subset: headings, bold, italics, line breaks, lists
    let html = md
      .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
      .replace(/^### (.*$)/gim, '<h3>$1</h3>')
      .replace(/^## (.*$)/gim, '<h2>$1</h2>')
      .replace(/^# (.*$)/gim, '<h1>$1</h1>')
      .replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/gim, '<em>$1</em>')
      .replace(/^(?:\*|-) (.*)$/gim, '<li>$1</li>')
      .replace(/(<li>.*<\/li>)/gim, '<ul>$1</ul>')
      .replace(/\n/g, '<br>');
    return html;
  }

  function renderPreview(){
    preview.innerHTML = simpleMarkdown(textarea.value || '');
  }

  function autosave(){
    if(!form) return;
    const formData = new FormData(form);
    const headers = {'X-Auto-Save':'1'};
    fetch(form.action || window.location.pathname, {method:'POST', body: formData, headers: headers, credentials: 'same-origin'})
      .then(resp => {
        if(!resp.ok) throw new Error('save failed');
        return resp.json().catch(()=>({status:'ok'}));
      })
      .then(data => {
        lastSaved = textarea.value;
        console.log('autosave ok', data);
      }).catch(err => {
        console.log('autosave err', err);
      });
  }

  textarea.addEventListener('input', ()=>{
    renderPreview();
    if(timeout) clearTimeout(timeout);
    timeout = setTimeout(()=>{
      if(textarea.value !== lastSaved){
        autosave();
      }
    }, 4000);
  });

  // initial render
  renderPreview();
})();
