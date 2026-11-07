/* The drills' behaviour, as on the original pages (commit 120473f): first-try scoring, retries, hints, Show answer,
   filters, shuffle and reset. Progress is saved in localStorage under CONF.key, keyed by question id, so it survives
   rebuilds. DATA and CONF are written into each page by tools/build.py. */
(function(){
  var KEY=CONF.key, LKEY=CONF.key+'-labels';
  /* Saved progress: an object of records by question id. Anything else is dropped; each record keeps only fields of
     the right type, so an old or damaged record can't stop the page (Start over always works). */
  function record(r){
    if(!r || typeof r!=='object' || Array.isArray(r)) return null;
    var o={};
    if(typeof r.tries==='number' && isFinite(r.tries) && r.tries>=0) o.tries=Math.floor(r.tries);
    if(typeof r.ok==='boolean') o.ok=r.ok;
    if(typeof r.first==='string') o.first=r.first;
    if(typeof r.last==='string') o.last=r.last;
    if(r.solved===true) o.solved=true;
    if(r.revealed===true) o.revealed=true;
    if(Array.isArray(r.wrong)) o.wrong=r.wrong.filter(function(x){ return typeof x==='string' });
    return o;
  }
  function load(){
    var raw; try{ raw=JSON.parse(localStorage.getItem(KEY)||'{}') }catch(e){ return {} }
    if(!raw || typeof raw!=='object' || Array.isArray(raw)) return {};
    var out={}; Object.keys(raw).forEach(function(id){ var r=record(raw[id]); if(r) out[id]=r });
    return out;
  }
  var st=load();
  function save(){ try{ localStorage.setItem(KEY, JSON.stringify(st)) }catch(e){} }
  var byId={}; DATA.forEach(function(q){ byId[q.id]=q });
  var activeCards=[], status='all';
  function accepted(q){ return q.acc || q.answer.split(/,\s+/).map(function(a){return a.trim()}) }
  /* A letter for multiple choice; a typed answer is graded exactly against the accepted values (js/grade.js). */
  function check(q,g){ g=String(g).trim(); if(!g) return null;
    return q.mc ? g.toUpperCase()===q.answer : SATGrade.check(accepted(q), g) }
  function el(id){ return document.getElementById('q-'+id) }

  /* MathJax. Hints and explanations carry the class mj-wait, which MathJax's first pass skips; each is typeset when
     first opened. Calls wait for MathJax's startup and run one after another; a failure puts mj-wait back, so opening
     the panel again retries. */
  var mjQueue=null;
  function mathjaxReady(){
    return new Promise(function(resolve,reject){ var tries=0;
      (function poll(){ var M=window.MathJax;
        if(M && M.startup && M.startup.promise && M.typesetPromise) return resolve(M.startup.promise);
        if(++tries>300) return reject(new Error('MathJax did not load'));
        setTimeout(poll,100) })() });
  }
  function typeset(node){
    if(!node.classList.contains('mj-wait') || node.getAttribute('data-mj')==='busy') return;
    if(!CONF.mathjax){ node.classList.remove('mj-wait'); return }
    node.setAttribute('data-mj','busy');
    var run=function(){ return mathjaxReady().then(function(){ node.classList.remove('mj-wait'); return MathJax.typesetPromise([node]) }) };
    mjQueue=(mjQueue||Promise.resolve()).then(run).then(
      function(){ node.removeAttribute('data-mj') },
      function(){ node.removeAttribute('data-mj'); node.classList.add('mj-wait');
        try{ if(window.MathJax && MathJax.typesetClear) MathJax.typesetClear([node]) }catch(e){} });
  }

  function paint(id){
    var q=byId[id], c=el(id), s=st[id]||{};
    c.classList.toggle('right', s.ok===true); c.classList.toggle('wrong', s.ok===false);
    c.querySelector('.mark').textContent = s.ok===true ? '✓ first try' : (s.ok===false ? (s.solved?'✗ → ✓':'✗') : '');
    var fb=c.querySelector('.fb'); fb.className='fb';
    if(q.mc){
      c.querySelectorAll('.mc').forEach(function(b){ var L=b.getAttribute('data-c');
        b.classList.toggle('no', (s.wrong||[]).indexOf(L)>=0);
        b.classList.toggle('yes', !!((s.solved||s.revealed) && L===q.answer));
        b.disabled = !!(s.solved||s.revealed) || (s.wrong||[]).indexOf(L)>=0; });
    } else {
      var inp=c.querySelector('input'); inp.classList.toggle('yes', !!s.solved);
      if(s.solved && !inp.value) inp.value=s.last||'';
      inp.disabled=!!(s.solved||s.revealed); c.querySelector('.chk').disabled=!!(s.solved||s.revealed);
    }
    if(s.solved){ fb.textContent = s.tries===1 ? 'Correct!' : 'Got it on try '+s.tries+'.'; fb.classList.add('ok') }
    else if(s.revealed){ fb.textContent = 'Answer: '+(q.mc ? q.answer : accepted(q)[0]); fb.classList.add('bad') }
    else if(s.tries){ fb.textContent = 'Not quite. Try again, or open a hint.'; fb.classList.add('bad') }
    else fb.textContent='';
    var rb=c.querySelector('.revbtn'); rb.textContent = (s.solved||s.revealed) ? (c.querySelector('.rat').hidden?'Explanation':'Hide explanation') : 'Show answer';
  }
  function attempt(id,g){
    var q=byId[id], s=st[id]||{}; if(s.solved||s.revealed) return;
    var ok=check(q,g); if(ok===null) return;
    if(!s.tries){ s.first=g; s.ok=ok }
    s.tries=(s.tries||0)+1; s.last=g;
    if(ok){ s.solved=true } else { s.wrong=s.wrong||[]; if(s.wrong.indexOf(g)<0) s.wrong.push(g) }
    st[id]=s; save(); paint(id); refresh();
  }
  DATA.forEach(function(q){
    var c=el(q.id);
    c.querySelectorAll('.mc').forEach(function(b){ b.addEventListener('click',function(){ attempt(q.id,b.getAttribute('data-c')) }) });
    var chk=c.querySelector('.chk');
    if(chk){ var inp=c.querySelector('input'); chk.addEventListener('click',function(){ attempt(q.id,inp.value) });
      inp.addEventListener('keydown',function(e){ if(e.key==='Enter'){ e.preventDefault(); attempt(q.id,inp.value) } }) }
    var hb=c.querySelector('.hintbtn'), hp=c.querySelector('.hint');
    if(hb && hp) hb.addEventListener('click',function(){ hp.hidden=!hp.hidden; hb.setAttribute('aria-expanded',String(!hp.hidden)); hb.textContent = hp.hidden?'Hint':'Hide hint'; if(!hp.hidden) typeset(hp) });
    var rb=c.querySelector('.revbtn'), rp=c.querySelector('.rat');
    rb.addEventListener('click',function(){ var s=st[q.id]||{};
      if(!(s.solved||s.revealed)){ if(!s.tries){ s.first='(shown)'; s.ok=false; s.tries=0 } s.revealed=true; st[q.id]=s; save(); rp.hidden=false }
      else { rp.hidden=!rp.hidden }
      rb.setAttribute('aria-expanded',String(!rp.hidden)); if(!rp.hidden) typeset(rp);
      paint(q.id); refresh(); });
    paint(q.id);
  });

  /* filters */
  var cardChips=document.querySelectorAll('[data-card]'), allChip=document.getElementById('c-all');
  function syncChips(){ allChip.setAttribute('aria-pressed', String(activeCards.length===0));
    cardChips.forEach(function(b){ b.setAttribute('aria-pressed', String(activeCards.indexOf(+b.getAttribute('data-card'))>=0)) }) }
  allChip.addEventListener('click',function(){ activeCards=[]; syncChips(); refresh() });
  cardChips.forEach(function(b){ b.addEventListener('click',function(){ var k=+b.getAttribute('data-card'), i=activeCards.indexOf(k);
    if(i>=0) activeCards.splice(i,1); else activeCards.push(k); syncChips(); refresh() }) });
  document.querySelectorAll('[data-status]').forEach(function(b){ b.addEventListener('click',function(){ status=b.getAttribute('data-status');
    document.querySelectorAll('[data-status]').forEach(function(x){ x.setAttribute('aria-pressed', String(x===b)) }); refresh() }) });

  function vis(q){ var s=st[q.id];
    if(activeCards.length && activeCards.indexOf(q.card)<0) return false;
    if(status==='todo') return !s || (!s.tries && !s.revealed);
    if(status==='missed') return !!s && s.ok===false;
    if(status==='right') return !!s && s.ok===true;
    return true }
  function refresh(){
    var shown=0, done=0, right=0, per={};
    DATA.forEach(function(q){ var v=vis(q); el(q.id).hidden=!v; if(v) shown++;
      var s=st[q.id]; per[q.card]=per[q.card]||{n:0,d:0,r:0}; per[q.card].n++;
      if(s && (s.tries||s.revealed)){ done++; per[q.card].d++; if(s.ok===true){ right++; per[q.card].r++ } } });
    document.getElementById('empty').hidden = shown>0;
    document.getElementById('shown').textContent='Showing '+shown+' of '+DATA.length;
    document.getElementById('score').firstChild.nodeValue = right+' / '+done+' ';
    document.getElementById('scoresub').textContent = 'right on the first try · '+done+' of '+DATA.length+' done';
    document.getElementById('prog').style.width = (100*done/DATA.length)+'%';
    Object.keys(per).forEach(function(k){ var r=document.getElementById('s-'+k); if(!r) return; var p=per[k];
      r.querySelector('.st').textContent = p.d+'/'+p.n+' done · '+p.r+' right first try';
      r.querySelector('.minibar i').style.width=(100*p.d/p.n)+'%'; });
  }
  document.querySelectorAll('[data-practice]').forEach(function(b){ b.addEventListener('click',function(){
    activeCards=[+b.getAttribute('data-practice')]; syncChips(); refresh(); document.getElementById('bar').scrollIntoView({behavior:'smooth'}) }) });

  /* labels toggle */
  var lt=document.getElementById('labelsToggle'); var lon=false; try{ lon=localStorage.getItem(LKEY)==='1' }catch(e){}
  lt.checked=lon; document.body.classList.toggle('labels',lon);
  lt.addEventListener('change',function(){ document.body.classList.toggle('labels',lt.checked); try{ localStorage.setItem(LKEY, lt.checked?'1':'0') }catch(e){} });

  /* order */
  var list=document.getElementById('list'), original=Array.prototype.slice.call(list.children);
  document.getElementById('shuffleBtn').addEventListener('click',function(){ var a=original.slice();
    for(var i=a.length-1;i>0;i--){ var j=Math.floor(Math.random()*(i+1)); var t=a[i]; a[i]=a[j]; a[j]=t }
    a.forEach(function(n){ list.appendChild(n) }) });
  document.getElementById('orderBtn').addEventListener('click',function(){ original.forEach(function(n){ list.appendChild(n) }) });
  var rs=document.getElementById('resetBtn'), armed=null;
  rs.addEventListener('click',function(){
    if(!armed){ rs.textContent='Tap again to erase all progress'; armed=setTimeout(function(){ rs.textContent='Start over'; armed=null },3500); return }
    clearTimeout(armed); armed=null; st={}; save();
    DATA.forEach(function(q){ var c=el(q.id), hp=c.querySelector('.hint'), hb=c.querySelector('.hintbtn'); c.querySelector('.rat').hidden=true;
      if(hp){ hp.hidden=true; hb.textContent='Hint'; hb.setAttribute('aria-expanded','false') } c.querySelector('.revbtn').setAttribute('aria-expanded','false');
      var inp=c.querySelector('input'); if(inp){ inp.value='' } paint(q.id) });
    rs.textContent='Start over'; refresh() });
  syncChips(); refresh();
})();
