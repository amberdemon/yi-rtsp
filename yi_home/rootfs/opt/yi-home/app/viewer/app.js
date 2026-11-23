const grid=document.querySelector('#grid'), tiles=new Map();
let signingOut=false;
function stopTile(t){t.stopped=true;t.abort?.abort();clearTimeout(t.timer);t.video.pause();t.video.removeAttribute('src');t.video.srcObject=null;if(t.url){URL.revokeObjectURL(t.url);t.url=null}}
function requireLogin(){for(const t of tiles.values())stopTile(t);location.replace('/')}
document.querySelector('#logout').addEventListener('click',async()=>{
 signingOut=true;for(const t of tiles.values())stopTile(t);
 try{const response=await fetch('/auth/logout',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});if(!response.ok&&response.status!==401)throw new Error();location.replace('/')}
 catch{const m=document.querySelector('#service-message');m.textContent='Video stopped. Unable to sign out while the bridge is offline; try Sign out again when it reconnects.';m.hidden=false}
});
const layout=document.querySelector('#layout'), offline=document.querySelector('#offline');
layout.value=localStorage.getItem('yi-layout')||'2';
function setLayout(){grid.classList.toggle('single',layout.value==='1');localStorage.setItem('yi-layout',layout.value)}
layout.addEventListener('change',setLayout);setLayout();
const toggle=document.querySelector('#offline-toggle');
toggle.addEventListener('click',()=>{offline.hidden=!offline.hidden;toggle.setAttribute('aria-expanded',String(!offline.hidden));toggle.textContent=offline.hidden?'Show offline':'Hide offline'});
function tile(camera){
 const el=document.createElement('article');el.className='camera';el.dataset.camera=camera.id;
 el.innerHTML='<div class="video-wrap"><video muted autoplay playsinline></video><div class="placeholder"><strong>Connecting…</strong><span>Your live view will appear here.</span></div></div><div class="camera-bar"><div><h3></h3><p class="state">Connecting</p></div><div class="controls"><button class="audio" type="button" aria-pressed="false">Listen</button><button class="full" type="button">Fullscreen</button></div></div>';
 el.querySelector('h3').textContent=camera.name;
 const video=el.querySelector('video');video.muted=true;
 const t={el,video,camera,abort:null,timer:null,stopped:false,url:null,lastTime:0,lastAdvance:Date.now()};
 el.querySelector('.audio').addEventListener('click',()=>{
  const enable=video.muted;
  for(const other of tiles.values()){other.video.muted=true;other.el.querySelector('.audio').textContent='Listen';other.el.querySelector('.audio').setAttribute('aria-pressed','false')}
  video.muted=!enable;el.querySelector('.audio').textContent=enable?'Mute':'Listen';el.querySelector('.audio').setAttribute('aria-pressed',String(enable));video.play().catch(()=>{});
 });
 el.querySelector('.full').addEventListener('click',()=>{if(document.fullscreenElement)document.exitFullscreen();else if(el.requestFullscreen)el.requestFullscreen().catch(()=>{});else if(video.webkitEnterFullscreen)video.webkitEnterFullscreen()});
 video.addEventListener('playing',()=>{el.querySelector('.placeholder').hidden=true;const s=el.querySelector('.state');s.textContent='Live';s.className='state live'});
 grid.append(el);return t;
}
function append(buffer,data,signal){return new Promise((resolve,reject)=>{
 const done=()=>{clean();resolve()},bad=()=>{clean();reject(new Error('Media append failed'))};
 const clean=()=>{buffer.removeEventListener('updateend',done);buffer.removeEventListener('error',bad);signal.removeEventListener('abort',bad)};
 buffer.addEventListener('updateend',done,{once:true});buffer.addEventListener('error',bad,{once:true});signal.addEventListener('abort',bad,{once:true});
 try{buffer.appendBuffer(data)}catch(e){clean();reject(e)}
})}
async function connect(t){
 if(t.stopped||signingOut||document.hidden)return;t.abort?.abort();clearTimeout(t.timer);t.abort=new AbortController();const signal=t.abort.signal;t.lastAdvance=Date.now();t.lastTime=0;
 const label=t.el.querySelector('.state'),placeholder=t.el.querySelector('.placeholder');label.textContent='Connecting';label.className='state';placeholder.hidden=false;
 try{
  const Media=window.ManagedMediaSource||window.MediaSource;
  if(!Media)throw new Error('This browser needs Media Source support. Try an updated Chrome or Safari.');
  const response=await fetch('/media/'+t.camera.id,{signal,cache:'no-store'});if(response.status===401){requireLogin();return}if(!response.ok)throw new Error('Waiting for camera stream.');
  const mime=response.headers.get('Content-Type');if(!Media.isTypeSupported(mime))throw new Error('This browser does not support this video format.');
  const media=new Media();t.video.disableRemotePlayback=true;if(t.url)URL.revokeObjectURL(t.url);t.url=URL.createObjectURL(media);t.video.src=t.url;
  await new Promise((resolve,reject)=>{media.addEventListener('sourceopen',resolve,{once:true});signal.addEventListener('abort',()=>reject(new Error('Stopped')),{once:true})});
  const buffer=media.addSourceBuffer(mime),reader=response.body.getReader();
  while(!signal.aborted){const {done,value}=await reader.read();if(done)throw new Error('Stream interrupted. Reconnecting…');await append(buffer,value,signal);
   if(t.video.paused)t.video.play().catch(()=>{});
   if(buffer.buffered.length){const end=buffer.buffered.end(buffer.buffered.length-1);if(end-t.video.currentTime>3)t.video.currentTime=Math.max(0,end-.5);
    if(t.video.currentTime>30&&!buffer.updating){buffer.remove(0,t.video.currentTime-15);await new Promise(resolve=>buffer.addEventListener('updateend',resolve,{once:true}))}}
  }
 }catch(error){if(signal.aborted||t.stopped)return;t.abort.abort();label.textContent='Reconnecting';label.className='state';placeholder.hidden=false;placeholder.querySelector('strong').textContent='Reconnecting…';placeholder.querySelector('span').textContent=error.message;t.timer=setTimeout(()=>connect(t),4000)}
}
async function refresh(){
 if(signingOut||document.hidden)return;
 try{const r=await fetch('/api/cameras',{cache:'no-store'});if(r.status===401){requireLogin();return}if(!r.ok)throw new Error();const {cameras}=await r.json();
  document.querySelector('#service-message').hidden=true;const active=cameras.filter(c=>c.active);
  document.querySelector('#summary').textContent=`${active.length} streaming · ${cameras.length-active.length} unavailable`;
  for(const c of active){let t=tiles.get(c.id);if(!t){t=tile(c);tiles.set(c.id,t);connect(t)}else t.el.querySelector('h3').textContent=c.name}
  for(const [id,t] of tiles){if(!active.some(c=>c.id===id)){stopTile(t);t.el.remove();tiles.delete(id)}}
  const list=document.querySelector('#offline-list');list.replaceChildren();for(const c of cameras.filter(c=>!c.active)){const el=document.createElement('div');el.className='offline-card';const name=document.createElement('strong');name.textContent=c.name;const state=document.createElement('span');state.textContent=c.online?'Not streaming':'Offline';el.append(name,state);list.append(el)}
 }catch{const message=document.querySelector('#service-message');message.textContent='Reconnecting to your camera bridge…';message.hidden=false}
}
refresh();setInterval(refresh,5000);
function suspend(){for(const t of tiles.values())stopTile(t)}
function resume(){if(signingOut||document.hidden)return;for(const t of tiles.values()){t.stopped=false;t.video.muted=true;t.el.querySelector('.audio').textContent='Listen';t.el.querySelector('.audio').setAttribute('aria-pressed','false');connect(t)}refresh()}
window.addEventListener('pagehide',suspend);
window.addEventListener('pageshow',event=>{if(event.persisted)resume()});
document.addEventListener('visibilitychange',()=>document.hidden?suspend():resume());
window.addEventListener('online',resume);
setInterval(()=>{if(document.hidden||signingOut)return;for(const t of tiles.values()){
 if(t.stopped)continue;if(t.video.currentTime>t.lastTime+.05){t.lastTime=t.video.currentTime;t.lastAdvance=Date.now()}
 else if(Date.now()-t.lastAdvance>15000)connect(t);
}},5000);
