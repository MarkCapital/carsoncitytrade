from pathlib import Path
source = (Path(__file__).resolve().parents[1] / 'app.js').read_text()
code = source[source.index('const CONTACT_BACKEND_URL'):source.index('function money(')] + source[source.index('function setupContactForm()'):source.index('function setupMenu()')]
output = Path(__file__).resolve().parents[2] / 'browser-tests'
output.mkdir(exist_ok=True)
(output / 'fixture.html').write_text('''<!doctype html><meta charset="utf-8"><title>Isolated contact form mock tests</title><h1>Contact form mock tests</h1><p>No network requests or email sends. Actual contact-form functions extracted from app.js.</p><button id="run">Run tests</button><pre id="results">Ready</pre><div id="fixture"></div><script>'''+code+'''\n
const results = document.querySelector('#results');
let options, script, submitted, resetIds, scriptFail=false;
const originalAppend = document.head.appendChild.bind(document.head);
document.head.appendChild = element => {
  if (element.tagName === 'SCRIPT' && element.src.startsWith('https://challenges.cloudflare.com/')) {
    script=element;
    // Mock loading without attaching or fetching any third-party script.
    queueMicrotask(()=>scriptFail ? element.onerror() : element.onload());
    return element;
  }
  return originalAppend(element);
};
window.turnstile={
  render(container, opts) {options=opts; return 'mock-widget-1';},
  reset(id) {resetIds.push(id); document.querySelector('input[name="cf-turnstile-response"]').value='';}
};
const tick=()=>new Promise(resolve=>setTimeout(resolve,20));
function init(fail=false) {
  scriptFail=fail;options=null;script=null;submitted=[];resetIds=[];
  document.querySelector('#fixture').innerHTML=`<form id="contactForm"><input name="name" value="张三"><input name="email" value="customer@example.com"><input name="message" value="مرحبا"><input type="file" name="attachment_file"><input type="hidden" name="cf-turnstile-response"><div id="contactVerification" data-sitekey="mock-public-key"></div><button type="submit">Send request</button><p id="formNote"></p></form>`;
  const form=document.querySelector('#contactForm');
  form.submit=()=>submitted.push(Object.fromEntries(new FormData(form)));
  setupContactForm();
  return form;
}
function token(value='mock-valid') {
  document.querySelector('input[name="cf-turnstile-response"]').value=value;
  options.callback(value);
}
async function submit(form) {form.dispatchEvent(new Event('submit',{cancelable:true})); await tick();}
function assert(value,message) {if(!value) throw new Error(message);}
document.querySelector('#run').onclick=async()=>{
 const passed=[];results.textContent='Running';
 try {
  let form=init();await tick();
  assert(options.action==='contact' && options.sitekey==='mock-public-key','widget configuration');
  await submit(form);assert(submitted.length===0 && !form.querySelector('button').disabled,'missing token blocks and permits retry');passed.push('missing token blocks; submit button recovers');
  token();await submit(form);assert(submitted.length===1 && submitted[0]['cf-turnstile-response']==='mock-valid','valid submit');passed.push('valid token submitted with multilingual fields');
  form=init();await tick();token();options['expired-callback']();
  assert(resetIds[0]==='mock-widget-1','reset returned widget ID');await submit(form);assert(submitted.length===0,'expired blocked');
  token('fresh-token');await submit(form);assert(submitted.length===1,'fresh retry');passed.push('expiry resets widget ID; stale token blocked; fresh token retry succeeds');
  form=init();await tick();token();options['error-callback']();await submit(form);assert(submitted.length===0 && !form.querySelector('button').disabled,'challenge error');token('retry');await submit(form);assert(submitted.length===1,'error retry');passed.push('challenge error blocks stale token; callback restores retry');
  form=init(true);await tick();await submit(form);assert(submitted.length===0 && document.querySelector('#formNote').textContent.includes('email'),'script unavailable');passed.push('script load failure blocks sending and shows email fallback');
  form=init();await tick();token();
  const transfer=new DataTransfer();transfer.items.add(new File(['coin-photo'], 'coin.txt', {type:'text/plain'}));form.querySelector('input[type="file"]').files=transfer.files;
  await submit(form);const attachments=JSON.parse(submitted[0].attachments_json);assert(attachments[0].name==='coin.txt' && atob(attachments[0].base64)==='coin-photo','attachment');passed.push('optional attachment serialized with valid token');
  results.textContent='PASS: '+passed.length+' browser scenarios\\n'+passed.map(x=>'✓ '+x).join('\\n');
 } catch(error) {results.textContent='FAIL: '+error.message+'\\nPassed: '+passed.join('; ');}
};
</script>''')
